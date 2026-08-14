"""LLM Protocol and data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Protocol


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON string


@dataclass
class Message:
    role: Role
    content: str
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class Response:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage | None = None


@dataclass
class Chunk:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None


class LLMProvider(Protocol):
    """LLM unified interface. All providers must implement this Protocol."""

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Response: ...

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Chunk]: ...

    async def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """便捷方法：发送单条 prompt，返回文本内容。"""
        messages = [Message(role=Role.USER, content=prompt)]
        resp = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return resp.content
