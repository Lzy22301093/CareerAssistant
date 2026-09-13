"""OpenAI-compatible LLM Provider (works with MIMO, DeepSeek, OpenAI, etc.)."""

from typing import AsyncIterator

from openai import AsyncOpenAI

from app.llm.base import (
    Chunk,
    Message,
    Response,
    Role,
    ToolCall,
    ToolDefinition,
    Usage,
)


class OpenAIProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = "mimo-v2.5-pro",
        timeout: float | None = None,
    ):
        # timeout + max_retries=0（A3）：SDK 默认 timeout 600s / 内置重试 2 次，
        # 会与 with_retry 装饰器叠加导致单次调用最坏拖数分钟；
        # 重试统一交给装饰器（错误类型感知），SDK 层快速失败。
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
        )
        self.model = model

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        result = []
        for msg in messages:
            # Role 是 str Enum；兼容误传纯 str 的情况，避免 `'str' has no attribute 'value'`
            role = msg.role
            m: dict = {"role": role.value if hasattr(role, "value") else str(role), "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            result.append(m)
        return result

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
        json_mode: bool = False,
    ) -> Response:
        kwargs: dict = {
            "model": model or self.model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        completion = await self.client.chat.completions.create(**kwargs)
        choice = completion.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                )
                for tc in choice.message.tool_calls
            ]

        usage = None
        if completion.usage:
            usage = Usage(
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                total_tokens=completion.usage.total_tokens,
            )

        return Response(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            usage=usage,
        )

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Chunk]:
        kwargs: dict = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        stream = await self.client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            yield Chunk(
                content=delta.content or "",
                finish_reason=chunk.choices[0].finish_reason,
            )

    async def generate(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096
    ) -> str:
        """便捷方法：发送单条 prompt，返回文本内容。"""
        messages = [Message(role=Role.USER, content=prompt)]
        resp = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return resp.content
