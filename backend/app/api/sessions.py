"""Sessions API — 会话管理 + SSE 流式消息。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.graph import get_graph
from app.llm import create_llm_provider
from app.tools.file_tools import FileParserTool
from app.models.schemas import (
    JDAnalysis,
    GapAnalysis,
    MessageRequest,
    Profile,
    ResumeContent,
    SessionCreateResponse,
    SessionStage,
)
from app.models.session_store import InMemorySessionStore, RedisSessionStore, SessionStore

logger = logging.getLogger(__name__)
router = APIRouter()

# === 会话存储（根据配置选择 Redis 或内存） ===

_store: SessionStore | None = None

# === 会话级并发锁 ===
# 同一会话的消息处理必须串行化，避免"读-改-写"竞态导致状态互相覆盖。
# 不同会话互不影响，可并行处理。

_session_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


async def _get_session_lock(session_id: str) -> asyncio.Lock:
    """获取指定会话的锁（每个会话一个，按需创建）。"""
    async with _locks_guard:
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            _session_locks[session_id] = lock
        return lock


async def get_store() -> SessionStore:
    """获取或初始化会话存储。"""
    global _store
    if _store is None:
        if settings.redis_url:
            try:
                import redis.asyncio as aioredis
                client = aioredis.from_url(settings.redis_url, decode_responses=True)
                # 测试连接
                await client.ping()
                _store = RedisSessionStore(client)
                logger.info("Using Redis session store")
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to in-memory: {e}")
                _store = InMemorySessionStore()
        else:
            _store = InMemorySessionStore()
    return _store


def _new_session_data(session_id: str) -> dict[str, Any]:
    """创建新会话的初始数据。"""
    return {
        "session_id": session_id,
        "stage": SessionStage.INIT,
        "messages": [],
        "jd_analysis": None,
        "profile": None,
        "gap_analysis": None,
        "resume_content": None,
        "render_config": None,
        "interview_questions": None,
        "uploaded_files": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _ensure_upload_dir() -> str:
    """确保上传目录存在。"""
    upload_dir = os.path.abspath(settings.upload_dir)
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


async def _parse_uploaded_files(session: dict[str, Any]) -> tuple[str | None, str | None]:
    """解析会话中上传的文件，返回 (jd_text, resume_text)。

    优先使用用户指定的 doc_type，否则根据文件名和会话状态推断。
    """
    file_parser = FileParserTool()
    jd_text = None
    resume_text = None
    parse_errors = []  # 收集解析错误

    uploaded_files = session.get("uploaded_files", [])
    logger.info(f"[ParseFiles] 会话有 {len(uploaded_files)} 个上传文件")

    for file_info in uploaded_files:
        file_path = file_info.get("file_path")
        filename = file_info.get("filename", "")
        doc_type = file_info.get("doc_type")  # 用户指定的类型

        if not file_path or not os.path.exists(file_path):
            error_msg = f"文件不存在: {file_path}"
            logger.warning(f"[ParseFiles] {error_msg}")
            parse_errors.append(f"{filename}: {error_msg}")
            continue

        # 解析文件
        try:
            result = await file_parser.execute(file_path=file_path)
            if not result.success:
                error_msg = f"文件解析失败: {result.error}"
                logger.error(f"[ParseFiles] {filename}: {error_msg}")
                parse_errors.append(f"{filename}: {error_msg}")
                continue

            text = result.data.get("text", "")
            if not text:
                error_msg = "文件解析结果为空"
                logger.error(f"[ParseFiles] {filename}: {error_msg}")
                parse_errors.append(f"{filename}: {error_msg}")
                continue

            logger.info(f"[ParseFiles] 成功解析文件 {filename}: {len(text)} 字符")
            logger.debug(f"[ParseFiles] 文件内容前 500 字符:\n{text[:500]}")

        except Exception as e:
            error_msg = f"文件解析异常: {e}"
            logger.error(f"[ParseFiles] {filename}: {error_msg}", exc_info=True)
            parse_errors.append(f"{filename}: {error_msg}")
            continue

        # 1. 优先使用用户指定的 doc_type
        if doc_type == "jd":
            jd_text = text
            logger.info(f"[ParseFiles] 使用为 JD（用户指定）: {filename}")
        elif doc_type == "resume":
            resume_text = text
            logger.info(f"[ParseFiles] 使用为简历（用户指定）: {filename}")
        else:
            # 2. 根据文件名推断
            filename_lower = filename.lower()
            if any(keyword in filename_lower for keyword in ["jd", "job", "职位", "岗位"]):
                jd_text = text
                logger.info(f"[ParseFiles] 使用为 JD（文件名匹配）: {filename}")
            elif any(keyword in filename_lower for keyword in ["resume", "简历", "cv"]):
                resume_text = text
                logger.info(f"[ParseFiles] 使用为简历（文件名匹配）: {filename}")
            else:
                # 3. 根据会话状态推断
                if session.get("jd_analysis"):
                    resume_text = text
                    logger.info(f"[ParseFiles] 使用为简历（会话已有 JD）: {filename}")
                elif session.get("profile"):
                    jd_text = text
                    logger.info(f"[ParseFiles] 使用为 JD（会话已有简历）: {filename}")
                else:
                    # 4. 默认：如果只有一个文件，尝试根据内容判断
                    # 简单启发式：包含"教育背景"或"工作经历"的更可能是简历
                    if any(keyword in text for keyword in ["教育背景", "工作经历", "项目经历", "实习经历"]):
                        resume_text = text
                        logger.info(f"[ParseFiles] 使用为简历（内容匹配）: {filename}")
                    else:
                        jd_text = text
                        logger.info(f"[ParseFiles] 使用为 JD（默认）: {filename}")

    # 记录解析结果摘要
    logger.info(f"[ParseFiles] 解析完成: jd_text={'有' if jd_text else '无'}({len(jd_text) if jd_text else 0}字符), resume_text={'有' if resume_text else '无'}({len(resume_text) if resume_text else 0}字符)")
    if parse_errors:
        logger.warning(f"[ParseFiles] 解析错误: {'; '.join(parse_errors)}")

    return jd_text, resume_text


# === API 端点 ===


@router.post("/", response_model=SessionCreateResponse)
async def create_session():
    """创建新会话。"""
    session_id = str(uuid.uuid4())
    store = await get_store()
    await store.create(session_id, _new_session_data(session_id))
    logger.info(f"Created session: {session_id}")
    return SessionCreateResponse(session_id=session_id)


@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取会话详情。"""
    store = await get_store()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@router.get("/{session_id}/status")
async def get_session_status(session_id: str):
    """获取会话状态摘要。"""
    store = await get_store()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {
        "session_id": session_id,
        "stage": session["stage"],
        "has_jd": session["jd_analysis"] is not None,
        "has_profile": session["profile"] is not None,
        "has_gap_analysis": session["gap_analysis"] is not None,
        "has_resume_content": session["resume_content"] is not None,
        "message_count": len(session["messages"]),
        "file_count": len(session["uploaded_files"]),
    }


@router.post("/{session_id}/messages")
async def send_message(session_id: str, request: MessageRequest):
    """发送消息并触发 Graph 执行，通过 SSE 流式返回结果。"""
    store = await get_store()

    # 同一会话的消息串行处理（读-改-写 竞态保护），锁持有到 SSE 流结束
    lock = await _get_session_lock(session_id)
    await lock.acquire()
    try:
        session = await store.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # 记录用户消息
        session["messages"].append({
            "role": "user",
            "content": request.content,
            "timestamp": datetime.now().isoformat(),
        })
        session["updated_at"] = datetime.now().isoformat()
        await store.update(session_id, {"messages": session["messages"], "updated_at": session["updated_at"]})
    except Exception:
        lock.release()
        raise

    async def event_stream():
        """SSE 事件流。"""
        result = {}  # 初始化结果字典，用于异常处理时保存部分结果
        try:
            # 解析上传的文件
            jd_text, resume_text = await _parse_uploaded_files(session)

            # 构建初始状态
            # 注意：必须把澄清历史/就绪标记/上传文件等字段一并传入，
            # 否则 Clarifier 多轮决策和文件解析兜底逻辑都会"失忆"。
            graph_state = {
                "user_message": request.content,
                "session_id": session_id,
                "jd_text": jd_text or "",
                "resume_text": resume_text or "",
                "jd_analysis": session["jd_analysis"] or {},
                "profile": session["profile"] or {},
                "gap_analysis": session["gap_analysis"] or {},
                "resume_content": session["resume_content"] or {},
                "render_config": session["render_config"] or {},
                "interview_questions": session["interview_questions"] or {},
                "clarification_history": session.get("clarification_history", []),
                "clarification_question": session.get("clarification_question", ""),
                "ready_to_proceed": session.get("ready_to_proceed", False),
                "uploaded_files": session.get("uploaded_files", []),
                "content_iterations": session.get("content_iterations", 0),
                "messages": session["messages"],
            }

            # 记录关键状态信息
            logger.info(f"[SendMessage] 会话 {session_id} 状态:")
            logger.info(f"  - user_message: {len(request.content)} 字符")
            logger.info(f"  - jd_text: {'有' if jd_text else '无'}({len(jd_text) if jd_text else 0}字符)")
            logger.info(f"  - resume_text: {'有' if resume_text else '无'}({len(resume_text) if resume_text else 0}字符)")
            logger.info(f"  - has_jd_analysis: {bool(session['jd_analysis'])}")
            logger.info(f"  - has_profile: {bool(session['profile'])}")
            logger.info(f"  - uploaded_files: {len(session.get('uploaded_files', []))}")

            # 发送开始事件
            yield _sse_event("start", {"message": "正在处理..."})

            # 执行 Graph（复用全局缓存图，避免每条消息重建；加整图总超时兜底）
            llm = create_llm_provider()
            graph = get_graph(llm)
            result = await asyncio.wait_for(
                graph.ainvoke(graph_state),
                timeout=settings.graph_timeout,
            )

            # 更新会话状态
            updates = _build_session_updates(session, result)
            await store.update(session_id, updates)

            # 发送各阶段结果
            if result.get("route"):
                yield _sse_event("route", {
                    "route": result["route"],
                    "reason": result.get("route_reason", ""),
                })

            if result.get("jd_analysis"):
                yield _sse_event("jd_analysis", result["jd_analysis"])

            if result.get("profile"):
                yield _sse_event("profile", result["profile"])

            if result.get("gap_analysis"):
                yield _sse_event("gap_analysis", result["gap_analysis"])

            if result.get("resume_content"):
                yield _sse_event("resume_content", result["resume_content"])

            if result.get("render_config"):
                yield _sse_event("render_config", result["render_config"])

            if result.get("interview_questions"):
                yield _sse_event("interview_questions", result["interview_questions"])

            if result.get("clarification_question"):
                yield _sse_event("clarification", {
                    "question": result["clarification_question"],
                })

            # 记录助手回复
            assistant_content = _build_assistant_message(result)
            session["messages"].append({
                "role": "assistant",
                "content": assistant_content,
                "timestamp": datetime.now().isoformat(),
            })
            await store.update(session_id, {"messages": session["messages"]})

            # 发送完成事件
            yield _sse_event("done", {
                "stage": session["stage"],
                "message": assistant_content,
            })

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

            # 提供更详细的错误信息
            error_detail = str(e)
            error_hint = ""

            # 检查是否是文件解析相关的错误
            if "PDF" in error_detail or "pdf" in error_detail or "文件" in error_detail:
                error_hint = "文件解析失败，请确认：1) 文件是否为文字型 PDF（非扫描件）2) 文件是否损坏 3) 尝试复制文本直接粘贴"
            elif "timeout" in error_detail.lower() or "超时" in error_detail:
                error_hint = "处理超时，请稍后重试或简化输入内容"
            elif "json" in error_detail.lower() or "JSON" in error_detail:
                error_hint = "数据格式解析错误，请重试"

            yield _sse_event("error", {
                "detail": error_detail,
                "hint": error_hint,
            })

            # 尝试保存已处理的部分结果
            try:
                partial_updates = {}
                if result.get("jd_analysis"):
                    partial_updates["jd_analysis"] = result["jd_analysis"]
                if result.get("profile"):
                    partial_updates["profile"] = result["profile"]
                if partial_updates:
                    partial_updates["updated_at"] = datetime.now().isoformat()
                    await store.update(session_id, partial_updates)
                    logger.info(f"Saved partial results: {list(partial_updates.keys())}")
            except Exception as save_error:
                logger.error(f"Failed to save partial results: {save_error}")
        finally:
            # 释放会话锁（无论成功/失败/客户端断开）
            lock.release()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/upload")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    doc_type: str | None = None,  # 可选参数：'jd' 或 'resume'
):
    """上传文件（JD 或简历）。

    Args:
        doc_type: 文档类型，'jd' 或 'resume'。如果不提供，系统会尝试从文件名推断。
    """
    store = await get_store()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    upload_dir = _ensure_upload_dir()

    # 保存文件
    file_ext = os.path.splitext(file.filename or "unknown")[1]
    saved_name = f"{session_id}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(upload_dir, saved_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 验证 doc_type 参数
    if doc_type and doc_type not in ("jd", "resume"):
        doc_type = None  # 无效值，忽略

    # 记录上传信息
    file_info = {
        "filename": file.filename,
        "saved_name": saved_name,
        "file_path": file_path,
        "file_type": file_ext.lstrip(".").lower(),
        "doc_type": doc_type,  # 用户指定的文档类型
        "file_size": len(content),
        "uploaded_at": datetime.now().isoformat(),
    }
    session["uploaded_files"].append(file_info)
    session["updated_at"] = datetime.now().isoformat()
    await store.update(session_id, {
        "uploaded_files": session["uploaded_files"],
        "updated_at": session["updated_at"],
    })

    logger.info(f"File uploaded: {file.filename} -> {file_path} (doc_type={doc_type})")

    return {
        "message": "文件上传成功",
        "file": file_info,
        "hint": "请发送消息，系统会自动处理上传的文件。",
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话。"""
    store = await get_store()
    deleted = await store.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    logger.info(f"Deleted session: {session_id}")
    return {"message": f"Session {session_id} deleted"}


# === 辅助函数 ===


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """构造 SSE 事件字符串。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_session_updates(session: dict, result: dict) -> dict[str, Any]:
    """从 Graph 结果构建需要更新的字段。"""
    updates: dict[str, Any] = {}

    if result.get("jd_analysis"):
        session["jd_analysis"] = result["jd_analysis"]
        session["stage"] = SessionStage.HAS_JD
        updates["jd_analysis"] = result["jd_analysis"]
        updates["stage"] = session["stage"]

    if result.get("profile"):
        session["profile"] = result["profile"]
        if session["stage"] == SessionStage.HAS_JD:
            session["stage"] = SessionStage.HAS_JD_AND_RESUME
        updates["profile"] = result["profile"]
        updates["stage"] = session["stage"]

    if result.get("gap_analysis"):
        session["gap_analysis"] = result["gap_analysis"]
        updates["gap_analysis"] = result["gap_analysis"]

    if result.get("resume_content"):
        session["resume_content"] = result["resume_content"]
        updates["resume_content"] = result["resume_content"]

    if result.get("render_config"):
        session["render_config"] = result["render_config"]
        updates["render_config"] = result["render_config"]

    if result.get("interview_questions"):
        session["interview_questions"] = result["interview_questions"]
        session["stage"] = SessionStage.COMPLETED
        updates["interview_questions"] = result["interview_questions"]
        updates["stage"] = session["stage"]

    # 澄清状态与迭代计数也需要持久化（此前遗漏，导致多轮澄清失忆）
    if result.get("clarification_history") is not None:
        session["clarification_history"] = result["clarification_history"]
        updates["clarification_history"] = result["clarification_history"]

    if result.get("clarification_question"):
        session["clarification_question"] = result["clarification_question"]
        updates["clarification_question"] = result["clarification_question"]

    if result.get("ready_to_proceed") is not None:
        session["ready_to_proceed"] = result["ready_to_proceed"]
        updates["ready_to_proceed"] = result["ready_to_proceed"]

    if result.get("content_iterations"):
        session["content_iterations"] = result["content_iterations"]
        updates["content_iterations"] = result["content_iterations"]

    updates["updated_at"] = datetime.now().isoformat()
    return updates


def _build_assistant_message(result: dict) -> str:
    """从 Graph 结果构建助手回复文本。"""
    parts = []

    if result.get("clarification_question"):
        return result["clarification_question"]

    if result.get("route") == "jd_analyzer" and result.get("jd_analysis"):
        jd = result["jd_analysis"]
        parts.append(f"已分析职位：{jd.get('job_title', '未知')}")
        if jd.get("company"):
            parts.append(f"公司：{jd['company']}")
        req_count = len(jd.get("requirements", []))
        if req_count:
            parts.append(f"提取了 {req_count} 项要求")

    if result.get("gap_analysis"):
        gap = result["gap_analysis"]
        score = gap.get("overall_score", 0)
        parts.append(f"匹配度评分：{score}/100")

    if result.get("resume_content"):
        sections = result["resume_content"].get("sections", [])
        parts.append(f"已生成 {len(sections)} 个简历板块")

    if result.get("interview_questions"):
        questions = result["interview_questions"].get("questions", [])
        parts.append(f"已生成 {len(questions)} 道面试题")

    if not parts:
        parts.append("处理完成")

    return "。".join(parts) + "。"
