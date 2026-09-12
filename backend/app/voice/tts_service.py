"""TTS 服务 — 调用 MiMo-V2.5-TTS 文字转语音。

对齐官网 OpenAI 协议示例（https://mimo.mi.com/models/zh-CN/mimo-v2.5-tts）：
- messages: user=风格指令, assistant=待合成文本
- audio.voice: 精品音色名（如 Chloe）
- audio.format: wav / pcm16
- 非流式：choices[0].message.audio.data (base64)
- 流式：choices[].delta.audio.data (base64)，两种都兼容

语速/风格通过 user 侧风格指令控制（官网未提供独立 speed 字段）。
"""

from __future__ import annotations

import base64
import json
import logging
import struct
from collections.abc import AsyncIterator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# 官网示例及产品常用精品音色（英文 ID + 中文展示名）
VOICE_OPTIONS: list[dict[str, str]] = [
    {"id": "Chloe", "label": "Chloe · 明亮女声"},
    {"id": "Mia", "label": "Mia · 温暖女声"},
    {"id": "Milo", "label": "Milo · 阳光男声"},
    {"id": "Dean", "label": "Dean · 沉稳男声"},
]

DEFAULT_VOICE = "Chloe"

# 风格预设：用户可选，写入官网 messages[0].user
STYLE_PRESETS: dict[str, str] = {
    "professional": (
        "自然、专业、略带鼓励的语调，像资深技术面试官面对面交流；"
        "有起伏和停顿，不要机械匀速；中文普通话，吐字清晰。"
    ),
    "casual": (
        "轻松、亲切的聊天语调，像学长学姐在咖啡厅交流；"
        "语速自然，带一点口语感，中文普通话。"
    ),
    "concise": (
        "简洁干练的语调，重点清晰，不拖泥带水；"
        "适合技术面试快速推进，中文普通话。"
    ),
}

DEFAULT_STYLE = STYLE_PRESETS["professional"]

MIN_SPEED = 0.7
MAX_SPEED = 1.6

# 输出采样率（PCM 裸流播放用）
SAMPLE_RATE = 24000


def clamp_speed(speed: float | None, default: float | None = None) -> float:
    try:
        v = float(
            speed
            if speed is not None
            else (default if default is not None else settings.tts_default_speed)
        )
    except (TypeError, ValueError):
        v = float(settings.tts_default_speed)
    return max(MIN_SPEED, min(MAX_SPEED, v))


def resolve_style(style_key: str | None, speed: float = 1.0) -> str:
    """把风格 key + 语速映射为送给 TTS 的 user 风格指令。"""
    key = (style_key or "professional").strip().lower()
    base = STYLE_PRESETS.get(key, DEFAULT_STYLE)
    if speed >= 1.35:
        pace = "语速偏快、干脆利落"
    elif speed >= 1.15:
        pace = "语速略快、流畅"
    elif speed <= 0.85:
        pace = "语速稍慢、吐字清晰"
    else:
        pace = "语速自然适中"
    return f"{base}；{pace}。"


def normalize_voice(voice: str | None) -> str:
    v = (voice or settings.tts_default_voice or DEFAULT_VOICE).strip()
    if not v or v == "mimo_default":
        return DEFAULT_VOICE
    # 允许未知音色透传（官方可能扩充）
    return v


def wav_to_pcm(wav_bytes: bytes) -> bytes:
    """从 WAV 容器里抽出 PCM16 裸数据；若无标准头则原样返回。"""
    if len(wav_bytes) < 44 or wav_bytes[:4] != b"RIFF":
        return wav_bytes
    try:
        # 找 data chunk
        offset = 12
        while offset + 8 <= len(wav_bytes):
            chunk_id = wav_bytes[offset : offset + 4]
            chunk_size = struct.unpack_from("<I", wav_bytes, offset + 4)[0]
            if chunk_id == b"data":
                return wav_bytes[offset + 8 : offset + 8 + chunk_size]
            offset += 8 + chunk_size
            if chunk_size % 2 == 1:
                offset += 1
    except Exception:
        return wav_bytes[44:]
    return wav_bytes[44:]


class TTSService:
    """MiMo TTS 文字转语音服务。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.tts_model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        text: str,
        style_text: str,
        voice_id: str,
        *,
        stream: bool,
        audio_format: str,
    ) -> dict:
        return {
            "model": self.model,
            "messages": [
                {"role": "user", "content": style_text},
                {"role": "assistant", "content": text},
            ],
            "audio": {
                "format": audio_format,
                "voice": voice_id,
            },
            "stream": stream,
        }

    async def synthesize_stream(
        self,
        text: str,
        style: str | None = None,
        voice: str | None = None,
        speed: float | None = None,
    ) -> AsyncIterator[bytes]:
        """流式合成；失败时回退非流式，统一 yield PCM16 bytes。"""
        if not text:
            return

        speed_v = clamp_speed(speed)
        if style and style in STYLE_PRESETS:
            style_text = resolve_style(style, speed_v)
        elif style and len(style) > 20:
            style_text = f"{style}；语速按约 {speed_v:.1f} 倍自然控制。"
        else:
            style_text = resolve_style("professional", speed_v)

        voice_id = normalize_voice(voice)

        got_any = False
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=self._payload(
                        text, style_text, voice_id, stream=True, audio_format="pcm16"
                    ),
                    headers=self._headers(),
                ) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread())[:500]
                        logger.error(
                            "[TTS] stream HTTP %s: %s", resp.status_code, body
                        )
                    else:
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            audio_b64 = (delta.get("audio") or {}).get("data")
                            if audio_b64:
                                got_any = True
                                yield base64.b64decode(audio_b64)
        except Exception as e:
            logger.error(f"[TTS] stream failed: {e}")

        if got_any:
            return

        # 非流式回退（官网示例形态：message.audio.data）
        try:
            pcm = await self._synthesize_once(text, style_text, voice_id)
            if pcm:
                yield pcm
        except Exception as e:
            logger.error(f"[TTS] fallback failed: {e}")

    async def _synthesize_once(
        self, text: str, style_text: str, voice_id: str
    ) -> bytes:
        """非流式一次合成，返回 PCM16。"""
        payload = self._payload(
            text, style_text, voice_id, stream=False, audio_format="wav"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                logger.error(
                    "[TTS] non-stream HTTP %s: %s",
                    resp.status_code,
                    resp.text[:500],
                )
                return b""
            data = resp.json()
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            audio = msg.get("audio") or {}
            audio_b64 = audio.get("data")
            if not audio_b64:
                logger.error("[TTS] non-stream empty audio, body keys=%s", list(data))
                return b""
            raw = base64.b64decode(audio_b64)
            return wav_to_pcm(raw)

    async def synthesize(
        self,
        text: str,
        style: str | None = None,
        voice: str | None = None,
        speed: float | None = None,
    ) -> bytes:
        """合成完整 PCM16 bytes。"""
        chunks = []
        async for chunk in self.synthesize_stream(
            text, style=style, voice=voice, speed=speed
        ):
            chunks.append(chunk)
        return b"".join(chunks)
