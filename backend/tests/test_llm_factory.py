"""Tests for the LLM provider factory."""

import pytest
from unittest.mock import patch

from app.llm import create_llm_provider, OpenAIProvider


def test_create_provider():
    """验证返回 OpenAIProvider 实例（密钥通过配置注入）。"""
    with patch("app.llm.settings.openai_api_key", "test-key"):
        provider = create_llm_provider()
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "mimo-v2.5-pro"
    # A3：SDK 客户端禁用内置重试（统一交给 with_retry），并设请求级超时
    assert provider.client.max_retries == 0
    assert provider.client.timeout == 110


def test_missing_api_key():
    """未设置 key，验证抛出 ValueError。"""
    with patch("app.llm.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            create_llm_provider()
