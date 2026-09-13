"""WebSocket 消息协议定义。

客户端 → 服务端：audio / end_of_speech / interrupt / text / ping
服务端 → 客户端：asr_final / thinking / llm_token / tts_start / tts_end /
                 interrupted / done / error / pong + 二进制音频帧
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── 客户端 → 服务端 ──────────────────────────────────────

class ClientMsgType(str, Enum):
    AUDIO = "audio"
    END_OF_SPEECH = "end_of_speech"
    INTERRUPT = "interrupt"
    TEXT = "text"
    PING = "ping"
    START = "start"         # 启动面试（携带 jd_analysis + profile）
    RESUME = "resume"       # 断线重连恢复已有面试（携带 interview_id，不重放开场）


@dataclass
class ClientMsg:
    type: ClientMsgType
    data: str = ""          # audio: base64 PCM16; text: 文字内容
    content: str = ""       # text 类型的别名
    jd_analysis: dict[str, Any] = field(default_factory=dict)   # start: JD 分析结果
    profile: dict[str, Any] = field(default_factory=dict)       # start: 个人画像
    referenced_questions: list[str] = field(default_factory=list)  # start: 参考面试题
    max_turns: int = 10     # start: 最大轮数
    interview_id: str = ""  # resume: 恢复的面试 ID
    user_id: int | None = None  # start: 用户 ID（报告归属）
    voice: str = ""         # start: TTS 音色
    speed: float | None = None  # start: TTS 语速 0.7-1.6
    tts_style: str = ""     # start: professional | casual | concise
    resume: dict[str, Any] = field(default_factory=dict)  # start: 本场简历（主材料）
    use_profile_as_supplement: bool = True  # start: 画像是否作补充


# ── 服务端 → 客户端 ──────────────────────────────────────

class ServerMsgType(str, Enum):
    ASR_FINAL = "asr_final"
    THINKING = "thinking"
    LLM_TOKEN = "llm_token"
    TTS_START = "tts_start"
    TTS_END = "tts_end"
    INTERRUPTED = "interrupted"
    DONE = "done"
    ERROR = "error"
    PONG = "pong"
    STARTED = "started"     # 面试已启动，附带初始问题


@dataclass
class ServerMsg:
    type: ServerMsgType
    text: str = ""
    content: str = ""
    report: dict[str, Any] | None = None
    message: str = ""
    interview_id: str = ""


def parse_client_msg(raw: str) -> ClientMsg | None:
    """解析客户端 JSON 消息，格式错误返回 None。"""
    import json
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None

    msg_type = obj.get("type")
    if not msg_type:
        return None

    try:
        t = ClientMsgType(msg_type)
    except ValueError:
        return None

    return ClientMsg(
        type=t,
        data=obj.get("data", ""),
        content=obj.get("content", ""),
        jd_analysis=obj.get("jd_analysis", {}),
        profile=obj.get("profile", {}),
        referenced_questions=obj.get("referenced_questions", []),
        max_turns=obj.get("max_turns", 10),
        interview_id=obj.get("interview_id", "") or "",
        user_id=obj.get("user_id"),
        voice=obj.get("voice") or "",
        speed=obj.get("speed"),
        tts_style=obj.get("tts_style") or obj.get("style") or "",
        resume=obj.get("resume") or {},
        use_profile_as_supplement=bool(obj.get("use_profile_as_supplement", True)),
    )


def encode_server_msg(msg: ServerMsg) -> str:
    """编码服务端消息为 JSON 字符串。"""
    import json
    payload: dict[str, Any] = {"type": msg.type.value}
    if msg.text:
        payload["text"] = msg.text
    if msg.content:
        payload["content"] = msg.content
    if msg.report is not None:
        payload["report"] = msg.report
    if msg.message:
        payload["message"] = msg.message
    if msg.interview_id:
        payload["interview_id"] = msg.interview_id
    return json.dumps(payload, ensure_ascii=False)
