"""TTS 服务 — 调用 MiMo-V2.5-TTS 文字转语音。"""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# 面试官语调指令
DEFAULT_STYLE = "用自然、专业、略带鼓励的语调朗读"


class TTSService:
    """MiMo TTS 文字转语音服务（流式输出 PCM16 24kHz）。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.tts_model

    async def synthesize_stream(
        self,
        text: str,
        style: str = DEFAULT_STYLE,
    ) -> AsyncIterator[bytes]:
        """流式合成语音，逐块 yield PCM16 bytes。"""
        if not text:
            return

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": style},
                {"role": "assistant", "content": text},
            ],
            "audio": {
                "format": "pcm16",
                "voice": "mimo_default",
            },
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break

                        import json
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        audio_info = delta.get("audio", {})
                        audio_b64 = audio_info.get("data")
                        if audio_b64:
                            yield base64.b64decode(audio_b64)

        except Exception as e:
            logger.error(f"[TTS] synthesize failed: {e}")

    async def synthesize(self, text: str, style: str = DEFAULT_STYLE) -> bytes:
        """合成语音，返回完整 PCM16 bytes。"""
        chunks = []
        async for chunk in self.synthesize_stream(text, style):
            chunks.append(chunk)
        return b"".join(chunks)
