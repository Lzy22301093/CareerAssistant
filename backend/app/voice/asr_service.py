"""ASR 服务 — 调用 MiMo-V2.5-ASR 语音转文字。"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ASRService:
    """MiMo ASR 语音转写服务。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.asr_model

    async def transcribe(self, wav_b64: str) -> str:
        """将 WAV base64 音频转写为文字。

        Args:
            wav_b64: base64 编码的 WAV 音频（不含 data URL 前缀）。

        Returns:
            转写文字，失败返回空字符串。
        """
        if not wav_b64:
            return ""

        data_url = f"data:audio/wav;base64,{wav_b64}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": data_url,
                                "format": "wav",
                            },
                        }
                    ],
                }
            ],
            "max_completion_tokens": 2048,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data["choices"][0]["message"]["content"]
            text = content.strip() if content else ""
            if text:
                logger.debug(f"[ASR] transcribed: {text[:80]}")
            return text

        except Exception as e:
            logger.error(f"[ASR] transcribe failed: {e}")
            return ""
