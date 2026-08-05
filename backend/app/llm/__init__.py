"""LLM module: provider factory and unified exports."""

from app.config import settings
from app.llm.base import (
    Chunk,
    LLMProvider,
    Message,
    Response,
    Role,
    ToolCall,
    ToolDefinition,
    Usage,
)
from app.llm.openai_provider import OpenAIProvider
from app.llm.retry import with_retry


def create_llm_provider() -> LLMProvider:
    """根据配置创建 OpenAI-compatible Provider 实例。"""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        base_url=settings.llm_base_url or None,
        model=settings.llm_model,
    )


__all__ = [
    "LLMProvider", "Message", "Response", "Chunk", "ToolCall",
    "ToolDefinition", "Usage", "Role",
    "OpenAIProvider", "with_retry", "create_llm_provider",
]
