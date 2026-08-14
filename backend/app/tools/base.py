"""Tool 基类定义。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """工具执行结果。"""

    success: bool
    data: Any = None
    error: str | None = None

    @classmethod
    def ok(cls, data: Any = None) -> ToolResult:
        """成功结果。"""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> ToolResult:
        """失败结果。"""
        return cls(success=False, error=error)


class Tool(ABC):
    """工具基类。所有工具必须继承此类。"""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具。子类必须实现此方法。"""
        pass

    def to_dict(self) -> dict:
        """转换为字典格式（用于 LLM function calling）。"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
