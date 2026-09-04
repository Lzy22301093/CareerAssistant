"""WebSocket 语音面试/对话网关。

双任务架构（参考 voice-chat 项目）：
- _receiver：读 WebSocket 消息，interrupt 立即拦截
- _processor：消费消息队列，执行 ASR → LLM → TTS 流水线

两种模式：
1. /ws/interview — 完整面试流程（evaluate → decide → ask_question）
2. /ws/voice-chat — 简单语音对话（纯 ASR → LLM → TTS 循环，LLM+TTS 并发流水线）

低延迟优化（voice-chat 模式）：
- LLM producer + TTS consumer 并发（asyncio.Queue + 句子级切分）
- LLM 禁用 thinking，跳过 reasoning_content
- TTS 逐 chunk yield，不缓冲整句
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.config import settings
from app.interview.handler import InterviewHandler
from app.llm.openai_provider import OpenAIProvider
from app.voice.asr_service import ASRService
from app.voice.audio_utils import pcm16_chunks_to_wav_b64
from app.voice.chat_handler import VoiceChatHandler
from app.voice.interview_handler import VoiceInterviewHandler
from app.voice.protocol import (
    ClientMsg,
    ClientMsgType,
    ServerMsg,
    ServerMsgType,
    encode_server_msg,
    parse_client_msg,
)
from app.voice.tts_service import TTSService

logger = logging.getLogger(__name__)

# 音频帧缓冲上限（约 30 秒 @ 16kHz / 512 samples per frame）
MAX_AUDIO_FRAMES = 500


class InterviewSession:
    """单次 WebSocket 连接的面试会话状态。"""

    def __init__(self, ws: WebSocket, interview_id: str = ""):
        self.ws = ws
        self.interview_id = interview_id
        self.interrupt_event = asyncio.Event()
        self.tts_playing = False

    def request_interrupt(self) -> None:
        self.interrupt_event.set()

    def is_interrupted(self) -> bool:
        return self.interrupt_event.is_set()

    def clear_interrupt(self) -> None:
        self.interrupt_event.clear()


# ── 全局服务实例（模块级单例） ──────────────────────────────

_asr: ASRService | None = None
_tts: TTSService | None = None
_interview_handler: InterviewHandler | None = None
_voice_handler: VoiceInterviewHandler | None = None
_chat_handler: VoiceChatHandler | None = None


def init_voice_services(handler: InterviewHandler) -> None:
    """在 main.py startup 中调用，注入 InterviewHandler 实例。"""
    global _asr, _tts, _interview_handler, _voice_handler, _chat_handler
    _asr = ASRService()
    _tts = TTSService()
    _interview_handler = handler
    _voice_handler = VoiceInterviewHandler(handler)

    # 初始化语音对话处理器（使用 LLM provider）
    provider = OpenAIProvider(
        api_key=settings.openai_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
    )
    _chat_handler = VoiceChatHandler(provider)


# ── WebSocket 端点 ──────────────────────────────────────

async def websocket_interview(ws: WebSocket) -> None:
    """WebSocket /ws/interview 入口。"""
    await ws.accept()
    session = InterviewSession(ws)
    queue: asyncio.Queue[ClientMsg | None] = asyncio.Queue()

    recv_task = asyncio.create_task(_receiver(ws, queue, session))
    proc_task = asyncio.create_task(_processor(ws, queue, session))

    try:
        await asyncio.gather(recv_task, proc_task)
    except Exception as e:
        logger.error(f"[WS] connection error: {e}")
    finally:
        recv_task.cancel()
        proc_task.cancel()


# ── 接收任务 ──────────────────────────────────────────────

async def _receiver(
    ws: WebSocket,
    queue: asyncio.Queue[ClientMsg | None],
    session: InterviewSession,
) -> None:
    """读 WebSocket 消息，interrupt 立即拦截。"""
    try:
        while True:
            raw = await ws.receive()

            # 二进制帧 → 当作音频
            if "bytes" in raw and raw["bytes"]:
                msg = ClientMsg(type=ClientMsgType.AUDIO,
                                data=base64.b64encode(raw["bytes"]).decode())
                await queue.put(msg)
                continue

            # 文本帧
            text = raw.get("text", "")
            if not text:
                continue

            msg = parse_client_msg(text)
            if msg is None:
                continue

            # interrupt 立即拦截，不进队列
            if msg.type == ClientMsgType.INTERRUPT:
                session.request_interrupt()
                continue

            # None 哨兵表示连接关闭
            await queue.put(msg)

    except WebSocketDisconnect:
        await queue.put(None)
    except Exception as e:
        logger.error(f"[WS] receiver error: {e}")
        await queue.put(None)


# ── 处理任务 ──────────────────────────────────────────────

async def _processor(
    ws: WebSocket,
    queue: asyncio.Queue[ClientMsg | None],
    session: InterviewSession,
) -> None:
    """消费消息队列，执行面试流水线。"""
    audio_buffer: list[bytes] = []

    while True:
        msg = await queue.get()
        if msg is None:
            break

        if msg.type == ClientMsgType.PING:
            await _send(ws, ServerMsg(type=ServerMsgType.PONG))
            continue

        if msg.type == ClientMsgType.AUDIO:
            frame = base64.b64decode(msg.data)
            audio_buffer.append(frame)
            if len(audio_buffer) > MAX_AUDIO_FRAMES:
                audio_buffer = audio_buffer[-MAX_AUDIO_FRAMES:]
            continue

        if msg.type == ClientMsgType.END_OF_SPEECH:
            if not audio_buffer:
                continue
            session.clear_interrupt()
            await _handle_speech(session, audio_buffer)
            audio_buffer = []
            continue

        if msg.type == ClientMsgType.TEXT:
            # 文字输入模式（调试用）
            session.clear_interrupt()
            await _handle_text(session, msg.content or msg.data)
            continue

        if msg.type == ClientMsgType.START:
            # 启动面试
            await _handle_start(session, msg)
            continue


async def _handle_start(session: InterviewSession, msg: ClientMsg) -> None:
    """处理 START 消息：创建面试并发送初始问题。"""
    ws = session.ws

    if not msg.jd_analysis:
        await _send(ws, ServerMsg(
            type=ServerMsgType.ERROR,
            message="缺少 JD 分析数据，请先上传或分析 JD",
        ))
        return

    try:
        result = await _interview_handler.start_interview(
            jd_analysis=msg.jd_analysis,
            profile=msg.profile,
            referenced_questions=msg.referenced_questions or None,
            max_turns=msg.max_turns,
        )
        interview_id = result["interview_id"]
        session.interview_id = interview_id

        question = result.get("question", "请介绍一下你自己。")
        await _tts_and_send(session, question)

        logger.info(f"[WS] interview started: {interview_id}")
    except Exception as e:
        logger.error(f"[WS] start interview failed: {e}")
        await _send(ws, ServerMsg(
            type=ServerMsgType.ERROR,
            message=f"启动面试失败: {e}",
        ))


async def _handle_speech(session: InterviewSession, audio_buffer: list[bytes]) -> None:
    """处理一段语音：ASR → Interview（可打断） → TTS。"""
    ws = session.ws

    # 1. ASR
    wav_b64 = pcm16_chunks_to_wav_b64(audio_buffer)
    text = await _asr.transcribe(wav_b64)

    if not text:
        await _send(ws, ServerMsg(type=ServerMsgType.ASR_FINAL, text=""))
        return

    await _send(ws, ServerMsg(type=ServerMsgType.ASR_FINAL, text=text))

    if session.is_interrupted():
        await _send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
        return

    # 2. Interview Handler（可打断）
    await _send(ws, ServerMsg(type=ServerMsgType.THINKING))

    # 将 graph 执行包装为 task，与 interrupt_event 竞争
    interview_task = asyncio.create_task(
        _voice_handler.process_answer_interruptible(
            session.interview_id, text, session.interrupt_event,
        )
    )

    # 等待 interview 完成或被打断
    done, pending = await asyncio.wait(
        [interview_task, asyncio.create_task(session.interrupt_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # 取消未完成的 task
    for p in pending:
        p.cancel()

    # 如果是 interrupt 先触发
    if session.interrupt_event.is_set():
        interview_task.cancel()
        await _send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
        return

    result = interview_task.result()
    if result is None:
        # 被打断（handler 内部检测到 interrupt）
        await _send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
        return

    # 3. TTS + 推送结果
    question = result.get("question") or ""
    is_complete = result.get("is_complete", False)

    if question:
        await _tts_and_send(session, question)

    if is_complete:
        report = result.get("report", {})
        await _send(ws, ServerMsg(type=ServerMsgType.DONE, report=report))
        session.interview_id = ""


async def _handle_text(session: InterviewSession, text: str) -> None:
    """处理文字输入（调试模式，跳过 ASR）。"""
    ws = session.ws

    await _send(ws, ServerMsg(type=ServerMsgType.ASR_FINAL, text=text))
    await _send(ws, ServerMsg(type=ServerMsgType.THINKING))

    # 可打断的 interview 执行
    interview_task = asyncio.create_task(
        _voice_handler.process_answer_interruptible(
            session.interview_id, text, session.interrupt_event,
        )
    )

    done, pending = await asyncio.wait(
        [interview_task, asyncio.create_task(session.interrupt_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for p in pending:
        p.cancel()

    if session.interrupt_event.is_set():
        interview_task.cancel()
        await _send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
        return

    result = interview_task.result()
    if result is None:
        await _send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
        return

    question = result.get("question") or ""
    is_complete = result.get("is_complete", False)

    if question:
        await _tts_and_send(session, question)

    if is_complete:
        report = result.get("report", {})
        await _send(ws, ServerMsg(type=ServerMsgType.DONE, report=report))
        session.interview_id = ""


# ── TTS 流式推送 ──────────────────────────────────────────

async def _tts_and_send(session: InterviewSession, text: str) -> None:
    """TTS 流式合成并推送音频帧。"""
    ws = session.ws
    session.tts_playing = True

    try:
        await _send(ws, ServerMsg(type=ServerMsgType.LLM_TOKEN, content=text))
        await _send(ws, ServerMsg(type=ServerMsgType.TTS_START))

        async for pcm_chunk in _tts.synthesize_stream(text):
            if session.is_interrupted():
                await _send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
                return
            await ws.send_bytes(pcm_chunk)

        await _send(ws, ServerMsg(type=ServerMsgType.TTS_END))
    except Exception as e:
        logger.error(f"[TTS] send failed: {e}")
    finally:
        session.tts_playing = False


# ── 辅助 ──────────────────────────────────────────────────

async def _send(ws: WebSocket, msg: ServerMsg) -> None:
    """发送 JSON 消息到客户端。"""
    try:
        await ws.send_text(encode_server_msg(msg))
    except Exception as e:
        logger.error(f"[WS] send failed: {e}")


# ── 面试创建端点（REST → WebSocket 前置） ─────────────────

async def start_interview_via_ws(
    session: InterviewSession,
    jd_analysis: dict,
    profile: dict,
    referenced_questions: list[str] | None = None,
    max_turns: int = 10,
    user_id: int | None = None,
) -> str:
    """通过 WebSocket 发起面试，返回 interview_id。

    注意：此函数供内部调用。前端通过 START 消息启动面试时，
    由 _handle_start 处理。
    """
    result = await _interview_handler.start_interview(
        jd_analysis=jd_analysis,
        profile=profile,
        referenced_questions=referenced_questions,
        max_turns=max_turns,
        user_id=user_id,
    )
    interview_id = result["interview_id"]
    session.interview_id = interview_id

    # 开场白 TTS
    question = result.get("question", "请介绍一下你自己。")
    await _tts_and_send(session, question)

    return interview_id


# ═══════════════════════════════════════════════════════════════
#  Voice Chat 模式 — 简单语音对话（LLM+TTS 并发流水线）
# ═══════════════════════════════════════════════════════════════


class VoiceChatSession:
    """单次语音对话的 WebSocket 会话状态。"""

    def __init__(self, ws: WebSocket, chat_session_id: str = ""):
        self.ws = ws
        self.chat_session_id = chat_session_id
        self.interrupt_event = asyncio.Event()
        self.tts_playing = False

    def request_interrupt(self) -> None:
        self.interrupt_event.set()

    def is_interrupted(self) -> bool:
        return self.interrupt_event.is_set()

    def clear_interrupt(self) -> None:
        self.interrupt_event.clear()


async def websocket_voice_chat(ws: WebSocket) -> None:
    """WebSocket /ws/voice-chat 入口（简单语音对话模式）。"""
    await ws.accept()
    session = VoiceChatSession(ws)
    queue: asyncio.Queue[ClientMsg | None] = asyncio.Queue()

    recv_task = asyncio.create_task(_vc_receiver(ws, queue, session))
    proc_task = asyncio.create_task(_vc_processor(ws, queue, session))

    try:
        await asyncio.gather(recv_task, proc_task)
    except Exception as e:
        logger.error(f"[VC-WS] connection error: {e}")
    finally:
        recv_task.cancel()
        proc_task.cancel()


async def _vc_receiver(
    ws: WebSocket,
    queue: asyncio.Queue[ClientMsg | None],
    session: VoiceChatSession,
) -> None:
    """Voice Chat 接收任务 — interrupt 立即拦截。"""
    try:
        while True:
            raw = await ws.receive()

            if "bytes" in raw and raw["bytes"]:
                msg = ClientMsg(
                    type=ClientMsgType.AUDIO,
                    data=base64.b64encode(raw["bytes"]).decode(),
                )
                await queue.put(msg)
                continue

            text = raw.get("text", "")
            if not text:
                continue

            msg = parse_client_msg(text)
            if msg is None:
                continue

            # interrupt 立即拦截
            if msg.type == ClientMsgType.INTERRUPT:
                session.request_interrupt()
                continue

            await queue.put(msg)

    except WebSocketDisconnect:
        await queue.put(None)
    except Exception as e:
        logger.error(f"[VC-WS] receiver error: {e}")
        await queue.put(None)


async def _vc_processor(
    ws: WebSocket,
    queue: asyncio.Queue[ClientMsg | None],
    session: VoiceChatSession,
) -> None:
    """Voice Chat 处理任务 — ASR → LLM+TTS 并发流水线。"""
    audio_buffer: list[bytes] = []

    while True:
        msg = await queue.get()
        if msg is None:
            break

        if msg.type == ClientMsgType.PING:
            await _vc_send(ws, ServerMsg(type=ServerMsgType.PONG))
            continue

        if msg.type == ClientMsgType.AUDIO:
            frame = base64.b64decode(msg.data)
            audio_buffer.append(frame)
            if len(audio_buffer) > MAX_AUDIO_FRAMES:
                audio_buffer = audio_buffer[-MAX_AUDIO_FRAMES:]
            continue

        if msg.type == ClientMsgType.END_OF_SPEECH:
            if not audio_buffer:
                continue
            # 如果 TTS 还在播放，先打断
            if session.tts_playing:
                session.request_interrupt()
                await asyncio.sleep(0.05)
                session.clear_interrupt()
            session.clear_interrupt()
            await _vc_handle_speech(session, audio_buffer)
            audio_buffer = []
            continue

        if msg.type == ClientMsgType.TEXT:
            if session.tts_playing:
                session.request_interrupt()
                await asyncio.sleep(0.05)
                session.clear_interrupt()
            session.clear_interrupt()
            await _vc_handle_text(session, msg.content or msg.data)
            continue

        if msg.type == ClientMsgType.START:
            await _vc_handle_start(session, msg)
            continue


async def _vc_handle_start(session: VoiceChatSession, msg: ClientMsg) -> None:
    """处理 START 消息：创建对话会话并发送开场白。"""
    ws = session.ws

    if not msg.jd_analysis:
        await _vc_send(ws, ServerMsg(
            type=ServerMsgType.ERROR,
            message="缺少 JD 分析数据，请先上传或分析 JD",
        ))
        return

    try:
        result = _chat_handler.start_chat(
            jd_analysis=msg.jd_analysis,
            profile=msg.profile,
            gap_analysis=None,
        )
        session.chat_session_id = result["session_id"]

        greeting = result.get("greeting", "你好，欢迎参加面试。")
        await _vc_tts_and_send(session, greeting)

        logger.info(f"[VC-WS] chat started: {session.chat_session_id}")
    except Exception as e:
        logger.error(f"[VC-WS] start chat failed: {e}")
        await _vc_send(ws, ServerMsg(
            type=ServerMsgType.ERROR,
            message=f"启动对话失败: {e}",
        ))


async def _vc_handle_speech(session: VoiceChatSession, audio_buffer: list[bytes]) -> None:
    """处理语音：ASR → LLM+TTS 并发流水线。"""
    ws = session.ws

    # 1. ASR
    wav_b64 = pcm16_chunks_to_wav_b64(audio_buffer)
    text = await _asr.transcribe(wav_b64)

    if not text:
        await _vc_send(ws, ServerMsg(type=ServerMsgType.ASR_FINAL, text=""))
        return

    await _vc_send(ws, ServerMsg(type=ServerMsgType.ASR_FINAL, text=text))

    if session.is_interrupted():
        await _vc_send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
        return

    # 2. LLM+TTS 并发流水线
    await _vc_run_pipeline(session, text)


async def _vc_handle_text(session: VoiceChatSession, text: str) -> None:
    """处理文字输入（调试模式，跳过 ASR）。"""
    ws = session.ws
    await _vc_send(ws, ServerMsg(type=ServerMsgType.ASR_FINAL, text=text))
    await _vc_run_pipeline(session, text)


async def _vc_run_pipeline(session: VoiceChatSession, user_text: str) -> None:
    """ASR → LLM+TTS 并发流水线（核心低延迟优化）。

    LLM producer 流式生成 token，按句子边界切分后推入 queue；
    TTS consumer 从 queue 读取句子，流式合成并推送音频。
    两者通过 asyncio.Queue 并发运行。
    """
    ws = session.ws

    sentence_queue: asyncio.Queue[str | None] = asyncio.Queue()
    session.clear_interrupt()
    session.tts_playing = False

    await _vc_send(ws, ServerMsg(type=ServerMsgType.THINKING))

    async def llm_producer():
        """流式 LLM token → 句子切分 → queue。"""
        nonlocal full_response
        full_response = ""
        sentence_buf = ""

        async for token in _chat_handler.process_message_stream(
            session.chat_session_id, user_text,
        ):
            if session.is_interrupted():
                logger.info("[VC-WS] LLM interrupted")
                break
            full_response += token
            sentence_buf += token
            await _vc_send(ws, ServerMsg(type=ServerMsgType.LLM_TOKEN, content=token))

            # 句子边界检测
            if _is_sentence_end(sentence_buf):
                await sentence_queue.put(sentence_buf)
                sentence_buf = ""

        # 剩余文本
        if sentence_buf.strip() and not session.is_interrupted():
            await sentence_queue.put(sentence_buf)

        # 通知 TTS consumer 结束
        await sentence_queue.put(None)
        logger.info(f"[VC-WS] LLM done, len={len(full_response)}")

    async def tts_consumer():
        """从 queue 读取句子，流式 TTS 并推送音频。"""
        first_sentence = True
        while True:
            sentence = await sentence_queue.get()
            if sentence is None:
                break
            if session.is_interrupted():
                # 清空队列
                while not sentence_queue.empty():
                    sentence_queue.get_nowait()
                break

            if first_sentence:
                await _vc_send(ws, ServerMsg(type=ServerMsgType.TTS_START))
                session.tts_playing = True
                first_sentence = False

            async for pcm_chunk in _tts.synthesize_stream(sentence):
                if session.is_interrupted():
                    logger.info("[VC-WS] TTS interrupted")
                    break
                await ws.send_bytes(pcm_chunk)

    # 并发执行 LLM producer + TTS consumer
    full_response = ""
    try:
        await asyncio.gather(llm_producer(), tts_consumer())
    except Exception as e:
        logger.error(f"[VC-WS] pipeline error: {e}")

    # 完成
    if session.is_interrupted():
        await _vc_send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
    else:
        await _vc_send(ws, ServerMsg(type=ServerMsgType.TTS_END))

    session.tts_playing = False


def _is_sentence_end(text: str) -> bool:
    """检测句子边界（参考 voice-chat 项目）。"""
    text = text.rstrip()
    if not text:
        return False
    last = text[-1]
    if last in '。！？.!?\n':
        return True
    if last in '，,' and len(text) > 20:
        return True
    return False


async def _vc_tts_and_send(session: VoiceChatSession, text: str) -> None:
    """Voice Chat 模式的 TTS 流式推送。"""
    ws = session.ws
    session.tts_playing = True

    try:
        await _vc_send(ws, ServerMsg(type=ServerMsgType.LLM_TOKEN, content=text))
        await _vc_send(ws, ServerMsg(type=ServerMsgType.TTS_START))

        async for pcm_chunk in _tts.synthesize_stream(text):
            if session.is_interrupted():
                await _vc_send(ws, ServerMsg(type=ServerMsgType.INTERRUPTED))
                return
            await ws.send_bytes(pcm_chunk)

        await _vc_send(ws, ServerMsg(type=ServerMsgType.TTS_END))
    except Exception as e:
        logger.error(f"[VC-WS] TTS send failed: {e}")
    finally:
        session.tts_playing = False


async def _vc_send(ws: WebSocket, msg: ServerMsg) -> None:
    """发送 JSON 消息到客户端。"""
    try:
        await ws.send_text(encode_server_msg(msg))
    except Exception as e:
        logger.error(f"[VC-WS] send failed: {e}")
