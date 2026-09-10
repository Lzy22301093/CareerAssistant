"""LLM 结构化输出 — ainvoke_json_with_schema（schema 校验 + 自动重试）。

给需要强结构输出的能力单元（consolidate 等）使用：
- 复用 BaseAgent 的超时/重试/参数传递
- 输出经 Pydantic schema 校验，失败自动重试一次
- 校验失败抛出 ValueError，由调用方决定降级策略
"""

from __future__ import annotations

import logging
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.agents.base import BaseAgent
from app.llm import LLMProvider, Message, Role

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class _StructuredCallAgent(BaseAgent):
    """内部结构化调用 Agent（无工具，单次调用）。"""

    name = "structured_call"

    def __init__(
        self,
        llm: LLMProvider,
        system_prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        super().__init__(llm, model=model)
        self._system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        # 强制 LLM 输出合法 JSON（response_format=json_object）。
        # 结构化能力单元只认 JSON；不开启时 MIMO 可能返回散文/markdown，
        # 导致 extract_json 找不到 JSON 对象而"校验失败"。见 agents/base.py。
        self.json_mode = True

    def build_messages(self, **kwargs) -> list[Message]:
        return [
            Message(role=Role.SYSTEM, content=self._system_prompt),
            Message(role=Role.USER, content=kwargs["user_content"]),
        ]

    def parse_response(self, content: str) -> dict:
        return {"_content": content}


async def ainvoke_json_with_schema(
    llm: LLMProvider,
    system_prompt: str,
    user_content: str,
    schema: Type[T],
    *,
    max_attempts: int = 2,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> T:
    """调用 LLM 并返回通过 schema 校验的对象。

    Args:
        llm: LLMProvider 实例。
        system_prompt: 系统提示词。
        user_content: 用户消息内容。
        schema: Pydantic 输出模型。
        max_attempts: 最大尝试次数（含首次），解析/校验失败自动重试。
        model: 指定模型（None 用 provider 默认）。
        temperature / max_tokens: 调用参数。

    Returns:
        校验通过的对象。

    Raises:
        ValueError: 所有尝试均未通过校验。
    """
    agent = _StructuredCallAgent(
        llm, system_prompt, model=model, temperature=temperature, max_tokens=max_tokens
    )
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            result = await agent.run(user_content=user_content)
            raw = result.get("_content", "")
            extracted = BaseAgent.extract_json(raw)
            if extracted is None:
                raise ValueError("输出中未找到 JSON 对象")
            return schema.model_validate(extracted)
        except ValidationError as e:
            last_error = e
            logger.warning(f"schema 校验失败 (attempt {attempt + 1}/{max_attempts}): {e}")
        except ValueError as e:
            last_error = e
            logger.warning(f"JSON 提取失败 (attempt {attempt + 1}/{max_attempts}): {e}")

    raise ValueError(f"LLM 输出无法通过 schema 校验: {last_error}")
