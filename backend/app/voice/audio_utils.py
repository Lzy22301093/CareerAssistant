"""音频工具 — PCM16 / WAV 格式转换。"""

from __future__ import annotations

import base64
import struct

# 采样率常量
SAMPLE_RATE_INPUT = 16000   # 前端录音 → ASR
SAMPLE_RATE_OUTPUT = 24000  # TTS → 前端播放


def pcm16_chunks_to_wav_b64(chunks: list[bytes], sample_rate: int = SAMPLE_RATE_INPUT) -> str:
    """将多段 PCM16 拼接并封装为 WAV base64 字符串（data URL 前缀由调用方处理）。"""
    raw_pcm = b"".join(chunks)
    wav_bytes = pcm16_to_wav(raw_pcm, sample_rate)
    return base64.b64encode(wav_bytes).decode("ascii")


def pcm16_to_wav(pcm_data: bytes, sample_rate: int = SAMPLE_RATE_INPUT) -> bytes:
    """给裸 PCM16 数据加上 WAV 文件头。"""
    num_samples = len(pcm_data) // 2
    # RIFF header
    wav = struct.pack('<4sI4s', b'RIFF', 36 + len(pcm_data), b'WAVE')
    # fmt chunk
    wav += struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1,
                        sample_rate, sample_rate * 2, 2, 16)
    # data chunk
    wav += struct.pack('<4sI', b'data', len(pcm_data))
    return wav + pcm_data


def wav_b64_to_data_url(wav_b64: str) -> str:
    """确保 base64 WAV 以 data URL 前缀开头（ASR API 要求）。"""
    if wav_b64.startswith("data:"):
        return wav_b64
    return f"data:audio/wav;base64,{wav_b64}"


def float32_to_pcm16_int16(sample: float) -> int:
    """Float32 [-1.0, 1.0] → PCM16 Int16，带 clamp。"""
    if sample < 0:
        return max(-32768, int(sample * 32768))
    return min(32767, int(sample * 32767))


def pcm16_bytes_to_float32(pcm_bytes: bytes) -> list[float]:
    """PCM16 bytes → Float32 列表（用于前端播放）。"""
    import array
    samples = array.array('h', pcm_bytes)
    return [s / 32768.0 for s in samples]
