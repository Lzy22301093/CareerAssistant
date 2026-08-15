"""LLM 结构化输出测试 — ainvoke_json_with_schema。"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field

from app.llm.structured import ainvoke_json_with_schema
from app.llm import Message, Response, Role


class DemoOutput(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)


class MockLLM:
    """可编程 Mock LLM：按调用序返回预设响应。"""

    def __init__(self, responses: list[str]):
        self._responses = responses
        self.call_count = 0

    async def chat(self, messages: list[Message], **kwargs) -> Response:
        resp = self._responses[min(self.call_count, len(self._responses) - 1)]
        self.call_count += 1
        return Response(content=resp)


class TestAinvokeJsonWithSchema:
    @pytest.mark.asyncio
    async def test_valid_first_try(self):
        llm = MockLLM([json.dumps({"name": "张三", "score": 80})])
        out = await ainvoke_json_with_schema(llm, "sys", "user", DemoOutput)
        assert out.name == "张三"
        assert out.score == 80
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_invalid_json(self):
        """首次输出非法，自动重试成功。"""
        llm = MockLLM(["不是 JSON", json.dumps({"name": "李四", "score": 90})])
        out = await ainvoke_json_with_schema(llm, "sys", "user", DemoOutput)
        assert out.name == "李四"
        assert llm.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_schema_violation(self):
        """首次通过 JSON 解析但校验失败（score 越界），重试成功。"""
        llm = MockLLM([
            json.dumps({"name": "王五", "score": 999}),
            json.dumps({"name": "王五", "score": 88}),
        ])
        out = await ainvoke_json_with_schema(llm, "sys", "user", DemoOutput)
        assert out.score == 88
        assert llm.call_count == 2

    @pytest.mark.asyncio
    async def test_all_attempts_fail_raises(self):
        llm = MockLLM(["坏数据", "更坏的数据"])
        with pytest.raises(ValueError):
            await ainvoke_json_with_schema(llm, "sys", "user", DemoOutput)
        assert llm.call_count == 2

    @pytest.mark.asyncio
    async def test_markdown_wrapped_json(self):
        """输出带 markdown 代码块也能解析。"""
        wrapped = '```json\n{"name": "赵六", "score": 75}\n```'
        llm = MockLLM([wrapped])
        out = await ainvoke_json_with_schema(llm, "sys", "user", DemoOutput)
        assert out.name == "赵六"
