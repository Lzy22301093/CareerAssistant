"""ASR 服务单元测试（mock HTTP）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.voice.asr_service import ASRService


@pytest.fixture
def asr():
    return ASRService(
        base_url="https://test.api/v1",
        api_key="test-key",
        model="mimo-v2.5-asr",
    )


def _mock_client_post(response_json: dict, status_code: int = 200):
    """构造 mock httpx.AsyncClient，其 post 返回指定 JSON。"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_json

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_transcribe_success(asr):
    mock_client = _mock_client_post({
        "choices": [{"message": {"content": "你好世界"}}]
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await asr.transcribe("dGVzdA==")

    assert result == "你好世界"


@pytest.mark.asyncio
async def test_transcribe_empty_audio(asr):
    result = await asr.transcribe("")
    assert result == ""


@pytest.mark.asyncio
async def test_transcribe_api_error(asr):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await asr.transcribe("dGVzdA==")

    assert result == ""


@pytest.mark.asyncio
async def test_transcribe_empty_content(asr):
    mock_client = _mock_client_post({
        "choices": [{"message": {"content": ""}}]
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await asr.transcribe("dGVzdA==")

    assert result == ""
