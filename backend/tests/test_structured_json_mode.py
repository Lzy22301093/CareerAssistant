"""回归：结构化调用必须开启 json_mode（response_format=json_object）。

问题背景：画像方向推荐等结构化能力单元报
"LLM 输出无法通过 schema 校验: 输出中未找到 JSON 对象"——根因是
_StructuredCallAgent 未开启 json_mode，MIMO 返回散文/markdown 包裹，
extract_json 找不到 JSON 对象。此测试断言 json_mode 被透传给 provider。
"""

from __future__ import annotations

import json

import pytest

from app.llm.structured import ainvoke_json_with_schema
from app.llm import Message, Response, Role
from app.llm.structured import _StructuredCallAgent


class DemoOutput(__import__("pydantic").BaseModel):
    name: str


class CapturingLLM:
    """Mock：记录每次 chat 是否收到 json_mode=True。"""

    def __init__(self, content: str):
        self._content = content
        self.calls: list[dict] = []

    async def chat(self, messages: list[Message], **kwargs) -> Response:
        self.calls.append({k: v for k, v in kwargs.items() if k in ("json_mode", "response_format", "model", "max_tokens")})
        return Response(content=self._content)


@pytest.mark.asyncio
async def test_structured_agent_enables_json_mode():
    llm = CapturingLLM(json.dumps({"name": "张三"}, ensure_ascii=False))
    await ainvoke_json_with_schema(llm, "只输出 JSON", "用户", DemoOutput)
    assert llm.calls, "应至少有一次 LLM 调用"
    assert llm.calls[0].get("json_mode") is True, "结构化调用必须开启 json_mode"


@pytest.mark.asyncio
async def test_json_mode_survives_markdown_wrapped_output():
    """开了 json_mode 后，即便输出仍带 markdown 代码块也能解析。"""
    llm = CapturingLLM('```json\n{"name": "李四"}\n```')
    out = await ainvoke_json_with_schema(llm, "只输出 JSON", "用户", DemoOutput)
    assert out.name == "李四"


@pytest.mark.asyncio
async def test_structured_agent_instance_json_mode_true():
    """实例化后的 agent 其 json_mode 应为 True（在 __init__ 里开启）。"""
    from app.llm.structured import _StructuredCallAgent
    agent = _StructuredCallAgent(llm=CapturingLLM("{}"), system_prompt="sys")
    assert agent.json_mode is True
