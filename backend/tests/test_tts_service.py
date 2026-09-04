"""TTS 服务单元测试（mock HTTP）。"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.voice.tts_service import TTSService


@pytest.fixture
def tts():
    return TTSService(
        base_url="https://test.api/v1",
        api_key="test-key",
        model="mimo-v2.5-tts",
    )


@pytest.mark.asyncio
async def test_synthesize_stream_success(tts):
    """模拟 SSE 流式响应，验证 yield 出 PCM bytes。"""
    chunk1_data = base64.b64encode(b"\x00\x01\x02\x03").decode()
    chunk2_data = base64.b64encode(b"\x04\x05\x06\x07").decode()

    sse_lines = [
        f'data: {{"choices":[{{"delta":{{"audio":{{"data":"{chunk1_data}"}}}}}}]}}',
        f'data: {{"choices":[{{"delta":{{"audio":{{"data":"{chunk2_data}"}}}}}}]}}',
        'data: [DONE]',
    ]

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = AsyncMock()

    async def mock_aiter_lines():
        for line in sse_lines:
            yield line

    mock_resp.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in tts.synthesize_stream("你好"):
            chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0] == b"\x00\x01\x02\x03"
    assert chunks[1] == b"\x04\x05\x06\x07"


@pytest.mark.asyncio
async def test_synthesize_stream_empty_text(tts):
    chunks = []
    async for chunk in tts.synthesize_stream(""):
        chunks.append(chunk)
    assert chunks == []


@pytest.mark.asyncio
async def test_synthesize_aggregates(tts):
    """synthesize() 应把所有 chunk 拼接成完整 bytes。"""
    chunk_data = base64.b64encode(b"\xAA\xBB").decode()
    sse_lines = [
        f'data: {{"choices":[{{"delta":{{"audio":{{"data":"{chunk_data}"}}}}}}]}}',
        f'data: {{"choices":[{{"delta":{{"audio":{{"data":"{chunk_data}"}}}}}}]}}',
        'data: [DONE]',
    ]

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = AsyncMock()

    async def mock_aiter_lines():
        for line in sse_lines:
            yield line

    mock_resp.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        result = await tts.synthesize("测试")

    assert result == b"\xAA\xBB\xAA\xBB"
