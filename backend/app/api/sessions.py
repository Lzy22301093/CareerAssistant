"""Sessions API — 会话管理 + SSE 流式消息。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Header
from fastapi.responses import Response, StreamingResponse
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
        # 增量编辑（v3）：输入版本与内容哈希
        "jd_input_version": 0,
        "profile_input_version": 0,
        "jd_input_hash": "",
        "resume_input_hash": "",
        "cover_letter_channel": "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _text_hash(text: str) -> str:
    """规范化文本后取 sha256 摘要（用于输入变化检测）。"""
    normalized = " ".join(text.split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


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
async def create_session(authorization: str | None = Header(None)):
    """创建新会话（可选绑定登录用户，用于跨会话记忆）。"""
    session_id = str(uuid.uuid4())
    store = await get_store()
    data = _new_session_data(session_id)
    # 可选绑定用户：带有效 token 时关联 user_id，否则匿名会话（记忆降级跳过）
    user_id = _resolve_user_id(authorization)
    if user_id:
        data["user_id"] = user_id
    await store.create(session_id, data)
    logger.info(f"Created session: {session_id} (user_id={user_id})")
    return SessionCreateResponse(session_id=session_id)


def _resolve_user_id(authorization: str | None) -> int | None:
    """从 Authorization header 解析用户 ID（无效返回 None）。"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    from app.services.auth_service import AuthService
    payload = AuthService.decode_token(parts[1])
    if not payload or not payload.get("sub"):
        return None
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        return None


class ExportRequest(BaseModel):
    format: str = "html"  # html | json | md


def _build_template_data(session: dict[str, Any]) -> dict[str, Any]:
    """从会话组装 HTML 模板数据（profile 结构化 + resume_content 兜底）。"""
    profile = session.get("profile") or {}
    sections = (session.get("resume_content") or {}).get("sections", [])

    def section_content(keyword: str) -> str:
        for sec in sections:
            if isinstance(sec, dict) and keyword in (sec.get("title") or ""):
                return sec.get("content") or ""
        return ""

    summary = profile.get("summary") or section_content("简介") or section_content("个人信息")
    data = {
        "name": profile.get("name") or "",
        "email": profile.get("email") or "",
        "phone": profile.get("phone") or "",
        "location": profile.get("location") or "",
        "summary": summary,
        "skills": [{"skill": s} for s in (profile.get("skills") or [])],
        "experience": [
            {
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "date": e.get("duration", ""),
                "description": "；".join(e.get("highlights") or []),
            }
            for e in (profile.get("experience") or [])
        ],
        "education": [
            {
                "school": e.get("school", ""),
                "date": str(e.get("year", "")),
                "degree": e.get("degree", ""),
                "major": e.get("major", ""),
            }
            for e in (profile.get("education") or [])
        ],
        "projects": [
            {
                "name": p.get("name", ""),
                "date": "",
                "description": p.get("description", "") or "；".join(p.get("highlights") or []),
            }
            for p in (profile.get("projects") or [])
        ],
    }
    return data


def _resume_to_markdown(session: dict[str, Any]) -> str:
    """把会话中的简历内容转换为 Markdown。"""
    lines: list[str] = []
    profile = session.get("profile") or {}
    content = session.get("resume_content") or {}

    if profile.get("name"):
        lines.append(f"# {profile['name']}")
        lines.append("")

    contact = " | ".join(
        x for x in (profile.get("email"), profile.get("phone"), profile.get("location")) if x
    )
    if contact:
        lines.append(contact)
        lines.append("")

    for section in content.get("sections", []):
        if not isinstance(section, dict):
            continue
        title = section.get("title", "")
        body = section.get("content", "")
        if title and body:
            lines.append(f"## {title}")
            lines.append("")
            lines.append(body)
            lines.append("")

    return "\n".join(lines)


@router.get("/")
async def list_sessions():
    """列出所有会话摘要（历史会话列表，按最近更新倒序）。

    会话 ID 索引由 SessionStore 维护（Redis set / 内存 keys），
    替代前端 localStorage 方案，避免刷新或清缓存后历史丢失。
    """
    store = await get_store()
    ids = await store.list_sessions()

    summaries = []
    for sid in ids:
        s = await store.get(sid)
        if s is None:
            continue
        summaries.append({
            "session_id": sid,
            "stage": s.get("stage", SessionStage.INIT.value),
            "message_count": len(s.get("messages", []) or []),
            "updated_at": s.get("updated_at", ""),
        })

    summaries.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return summaries


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
        result: dict[str, Any] = {}  # 初始化结果字典，用于异常处理时保存部分结果
        merged_updates: dict[str, Any] = {}  # 流式各节点的增量更新累计
        try:
            # 解析上传的文件
            jd_text, resume_text = await _parse_uploaded_files(session)

            # 增量编辑（v3）：检测输入变化 → 递增对应输入版本（级联重算的触发源）
            session_jiv = session.get("jd_input_version", 0)
            session_piv = session.get("profile_input_version", 0)
            jd_input_version = session_jiv
            profile_input_version = session_piv
            if jd_text:
                jd_hash = _text_hash(jd_text)
                if jd_hash != session.get("jd_input_hash"):
                    jd_input_version = session_jiv + 1
                    session["jd_input_hash"] = jd_hash
                    session["jd_input_version"] = jd_input_version
            if resume_text:
                resume_hash = _text_hash(resume_text)
                if resume_hash != session.get("resume_input_hash"):
                    profile_input_version = session_piv + 1
                    session["resume_input_hash"] = resume_hash
                    session["resume_input_version"] = profile_input_version

            # 跨会话记忆注入（v3）：登录用户时读取长期档案摘要供节点使用
            memory_summary: dict[str, Any] = {}
            if session.get("user_id"):
                try:
                    from app.services.memory_service import MemoryService
                    memory_summary = MemoryService().build_summary(session["user_id"])
                except Exception as mem_err:
                    logger.warning(f"[Memory] 读取档案失败: {mem_err}")

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
                "jd_input_version": jd_input_version,
                "profile_input_version": profile_input_version,
                # 下游基于版本（v3）：从会话读入，缺省 -1（从未分析）→ 强制重算
                "jd_analyzed_version": session.get("jd_analyzed_version", -1),
                "profile_analyzed_version": session.get("profile_analyzed_version", -1),
                "gap_based_jd": session.get("gap_based_jd", -1),
                "gap_based_profile": session.get("gap_based_profile", -1),
                "content_based_jd": session.get("content_based_jd", -1),
                "content_based_profile": session.get("content_based_profile", -1),
                "interview_based_jd": session.get("interview_based_jd", -1),
                "interview_based_profile": session.get("interview_based_profile", -1),
                "cover_letter_channel": session.get("cover_letter_channel", ""),
                "memory_summary": memory_summary,
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

            # 执行 Graph（流式：每完成一个节点立即推送进度与产物，带整图总超时兜底）
            llm = create_llm_provider()
            graph = get_graph(llm)

            async for chunk in _graph_stream(graph, graph_state, settings.graph_timeout):
                # chunk 形如 {"node_name": {字段: 值, ...}}
                for node_name, updates in chunk.items():
                    label = _NODE_LABELS.get(node_name, node_name)
                    yield _sse_event("progress", {
                        "node": node_name,
                        "message": f"正在{label}…",
                    })
                    # 意图事件（planner 产出）
                    if updates.get("intent"):
                        yield _sse_event("intent", {
                            "intent": updates["intent"],
                            "reason": updates.get("intent_reason", ""),
                            "plan": updates.get("execution_plan", []),
                        })
                    # 节点 trace
                    for tr in (updates.get("workflow_trace") or []):
                        yield _sse_event("trace", tr)
                    # 实时推送该节点产出的关键数据
                    for key, event_name in _NODE_EVENT_MAP.items():
                        if updates.get(key):
                            yield _sse_event(event_name, updates[key])
                    merged_updates.update(updates or {})

                    # 即时持久化该节点的结果字段（中断/刷新时已完成产物不丢）
                    persist = {
                        k: v for k, v in (updates or {}).items()
                        if k in _PERSIST_FIELDS and v is not None
                    }
                    if persist:
                        session.update(persist)
                        await store.update(session_id, persist)

            # updates 模式只返回增量，合并初始状态得到最终结果
            result = dict(graph_state)
            result.update(merged_updates)

            # 更新会话状态
            updates = _build_session_updates(session, result)
            await store.update(session_id, updates)

            # 跨会话记忆（v3）：新画像规则合并进 career_profile（零 LLM）
            user_id = session.get("user_id")
            if user_id and result.get("profile") and not result["profile"].get("_error"):
                try:
                    from app.services.memory_service import MemoryService
                    MemoryService().upsert_profile(user_id, result["profile"])
                    logger.info(f"[Memory] user={user_id} 档案已合并")
                except Exception as mem_err:
                    logger.warning(f"[Memory] 合并失败 user={user_id}: {mem_err}")

            # 发送路由信息（若本轮产生）
            if result.get("route"):
                yield _sse_event("route", {
                    "route": result["route"],
                    "reason": result.get("route_reason", ""),
                })

            # 兜底推送：若某结果没在流式阶段推送（如并行节点合并后字段缺失），这里补齐
            for key, event_name in _NODE_EVENT_MAP.items():
                if result.get(key) and not merged_updates.get(key):
                    yield _sse_event(event_name, result[key])

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

            # 兜底保存已处理的部分结果（流式循环已即时持久化节点产物，
            # 这里再覆盖一次澄清/状态字段，双保险幂等无害）
            try:
                partial_updates = {
                    k: v for k, v in merged_updates.items()
                    if k in _PERSIST_FIELDS and v is not None
                }
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


@router.post("/{session_id}/export")
async def export_resume(session_id: str, request: ExportRequest):
    """导出简历（HTML / JSON / Markdown），直接返回文件下载。"""
    store = await get_store()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    content = session.get("resume_content")
    if not content:
        raise HTTPException(status_code=400, detail="尚未生成简历内容，请先生成简历")

    fmt = request.format
    filename = f"resume_{session_id[:8]}"

    if fmt == "html":
        from app.tools.render_tools import HtmlRendererTool
        renderer = HtmlRendererTool()
        template = (session.get("render_config") or {}).get("template", "modern")
        result = await renderer.execute(template_name=template, data=_build_template_data(session))
        if not result.success:
            raise HTTPException(status_code=500, detail=f"HTML 渲染失败: {result.error}")
        return Response(
            content=result.data["html"],
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename}.html"'},
        )

    if fmt == "json":
        return Response(
            content=json.dumps(content, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )

    if fmt == "md":
        return Response(
            content=_resume_to_markdown(session),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
        )

    raise HTTPException(status_code=400, detail="不支持的导出格式，可选 html / json / md")


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

# 节点 → 用户可见的进度文案（流式推送用）
_NODE_LABELS = {
    "planner": "理解意图并规划任务",
    "jd_analyzer": "分析职位描述",
    "profile_extractor": "提取简历画像",
    "gap_analyzer": "进行匹配度分析",
    "content_generator": "生成简历内容",
    "parallel_analysis": "并行分析 JD 与简历",
    "parallel_post": "评审简历并生成面试题",
    "reviewer": "评审简历质量",
    "interview_qa": "生成面试题",
    "interview_reviewer": "评审面试题",
    "html_renderer": "渲染简历 HTML",
    "clarifier": "澄清需求",
    "question": "回答你的问题",
    "cover_letter": "生成求职文案",
}

# 节点更新字段 → SSE 事件名（节点产出即实时推送）
_NODE_EVENT_MAP = {
    "jd_analysis": "jd_analysis",
    "profile": "profile",
    "gap_analysis": "gap_analysis",
    "resume_content": "resume_content",
    "render_config": "render_config",
    "interview_questions": "interview_questions",
    "clarification_question": "clarification",
    "answer": "answer",
    "cover_letter": "cover_letter",
}

# 需要即时持久化的结果字段（流式循环中每完成一个节点就落盘一次，
# 保证处理中断/页面刷新时已完成的分析结果不丢失）
_PERSIST_FIELDS = (
    "jd_analysis",
    "profile",
    "gap_analysis",
    "resume_content",
    "render_config",
    "interview_questions",
    "clarification_question",
    "clarification_history",
    "ready_to_proceed",
    "content_iterations",
    "cover_letter",
    "cover_letter_channel",
)


async def _graph_stream(graph, state: dict, total_timeout: float):
    """以整图总超时限制消费 graph.astream(updates)。

    逐块消费并检查剩余时间，超时抛出 asyncio.TimeoutError，
    由调用方转换为 SSE error 事件。
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + total_timeout
    stream = graph.astream(state, stream_mode="updates")
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise asyncio.TimeoutError(f"Graph 执行超过总超时 {total_timeout}s")
            try:
                chunk = await asyncio.wait_for(stream.__anext__(), timeout=remaining)
                yield chunk
            except StopAsyncIteration:
                return
    finally:
        await stream.aclose()


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

    # 增量编辑（v3）：输入版本与下游基于版本持久化（跨消息保持级联一致性）
    for field in (
        "jd_input_version", "profile_input_version",
        "jd_analyzed_version", "profile_analyzed_version",
        "gap_based_jd", "gap_based_profile",
        "content_based_jd", "content_based_profile",
        "interview_based_jd", "interview_based_profile",
    ):
        if result.get(field) is not None:
            session[field] = result[field]
            updates[field] = result[field]

    # 求职信（v3）
    if result.get("cover_letter"):
        session["cover_letter"] = result["cover_letter"]
        updates["cover_letter"] = result["cover_letter"]
    if result.get("cover_letter_channel"):
        session["cover_letter_channel"] = result["cover_letter_channel"]
        updates["cover_letter_channel"] = result["cover_letter_channel"]

    updates["updated_at"] = datetime.now().isoformat()
    return updates


def _build_assistant_message(result: dict) -> str:
    """从 Graph 结果构建助手回复文本。"""
    parts = []

    if result.get("clarification_question"):
        return result["clarification_question"]

    # 自由问答（v3）：直接返回答案
    if result.get("answer"):
        return result["answer"]

    # 求职信（v3）
    if result.get("cover_letter"):
        cl = result["cover_letter"]
        channel = cl.get("channel", "")
        label = "招聘软件打招呼" if channel == "linkedin_message" else "求职信"
        parts.append(f"已生成{label}文案")
        if cl.get("subject"):
            parts.append(f"主题：{cl['subject']}")

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
