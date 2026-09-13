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
from app.llm.observability import MAX_SESSION_RECORDS, start_llm_capture, summarize_calls
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
        # 缓存解析后的文本（避免每次消息都重新解析文件）
        "jd_text": "",
        "resume_text": "",
        "cover_letter_channel": "",
        "interview_draft": {},
        "execution_plan": [],
        "triggered_agents": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _normalize_profile_dict(raw: dict[str, Any] | None) -> dict[str, Any]:
    """补齐画像数组字段，避免前端 ResultPanel 因缺 strengths/skills 等崩溃。"""
    if not raw or not isinstance(raw, dict):
        return {}
    out = dict(raw)
    for key in ("skills", "experience", "projects", "education", "certifications"):
        if not isinstance(out.get(key), list):
            out[key] = []
    return out


def _is_substantial_profile(profile: dict[str, Any] | None) -> bool:
    """画像是否具备可展示的实质内容（仅有姓名等零散字段不算）。"""
    if not profile or not isinstance(profile, dict):
        return False
    if profile.get("_error"):
        return False
    return bool(
        profile.get("skills")
        or profile.get("experience")
        or profile.get("projects")
        or profile.get("summary")
    )


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
    支持缓存：如果会话中已有解析后的文本且没有新文件上传，直接使用缓存。
    """
    file_parser = FileParserTool()
    jd_text = None
    resume_text = None
    parse_errors = []  # 收集解析错误

    uploaded_files = session.get("uploaded_files", [])
    logger.info(f"[ParseFiles] 会话有 {len(uploaded_files)} 个上传文件")

    # 检查是否有新上传的文件（通过比较 uploaded_files 数量与已解析的文件数量）
    # 如果没有新文件且已有缓存文本，直接使用缓存
    cached_jd = session.get("jd_text", "")
    cached_resume = session.get("resume_text", "")
    parsed_file_count = session.get("_parsed_file_count", 0)

    if len(uploaded_files) == parsed_file_count and (cached_jd or cached_resume):
        logger.info(f"[ParseFiles] 使用缓存文本: jd_text={len(cached_jd)}字符, resume_text={len(cached_resume)}字符")
        return cached_jd or None, cached_resume or None

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
            # 注意：先查简历关键字（"job-application"、"求职申请"等求职简历
            # 文件名常含 job/职位，若 JD 关键字优先会误判为 JD）
            filename_lower = filename.lower()
            if any(keyword in filename_lower for keyword in ["resume", "简历", "cv", "求职", "应聘", "application"]):
                resume_text = text
                logger.info(f"[ParseFiles] 使用为简历（文件名匹配）: {filename}")
            elif any(keyword in filename_lower for keyword in ["jd", "job", "职位", "岗位", "requirement"]):
                jd_text = text
                logger.info(f"[ParseFiles] 使用为 JD（文件名匹配）: {filename}")
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
                    # 改进的启发式：检查中英文简历关键词，更全面的匹配
                    resume_keywords = [
                        # 中文关键词
                        "教育背景", "工作经历", "项目经历", "实习经历", "个人简历",
                        "专业技能", "自我评价", "求职意向", "所获荣誉", "校园经历",
                        # 英文关键词
                        "education", "experience", "projects", "skills", "objective",
                        "summary", "qualifications", "employment", "work history",
                        "certifications", "awards", "references",
                    ]
                    jd_keywords = [
                        # 中文 JD 关键词
                        "职位描述", "岗位职责", "任职要求", "工作职责", "招聘要求",
                        "薪资待遇", "工作地点", "汇报对象", "下属人数",
                        # 英文 JD 关键词
                        "job description", "responsibilities", "requirements", "qualifications",
                        "we are looking for", "join our team", "about the role",
                    ]

                    text_lower = text.lower()
                    resume_score = sum(1 for kw in resume_keywords if kw in text_lower)
                    jd_score = sum(1 for kw in jd_keywords if kw in text_lower)

                    # 如果简历关键词匹配更多，识别为简历
                    if resume_score > jd_score:
                        resume_text = text
                        logger.info(f"[ParseFiles] 使用为简历（内容匹配，简历关键词 {resume_score} 个 vs JD 关键词 {jd_score} 个）: {filename}")
                    elif jd_score > resume_score:
                        jd_text = text
                        logger.info(f"[ParseFiles] 使用为 JD（内容匹配，JD 关键词 {jd_score} 个 vs 简历关键词 {resume_score} 个）: {filename}")
                    else:
                        # 关键词匹配相等或都没有匹配，使用长度和格式启发式
                        # 简历通常更长且包含更多个人信息
                        has_contact_info = any(kw in text_lower for kw in ["@", "电话", "手机", "email", "phone", "tel"])
                        if has_contact_info or len(text) > 2000:
                            resume_text = text
                            logger.info(f"[ParseFiles] 使用为简历（启发式判断：{'有联系方式' if has_contact_info else '文本较长'}）: {filename}")
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


@router.get("/{session_id}/trace")
async def get_session_trace(session_id: str):
    """会话 LLM 调用轨迹（C1 观测埋点）。

    返回最近 MAX_SESSION_RECORDS 条调用记录（agent/模型/延迟/token/重试/错误分类），
    用于事后排查耗时构成与成本，无需复跑请求。
    """
    store = await get_store()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {
        "session_id": session_id,
        "llm_calls": session.get("llm_calls") or [],
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

        # 如果有活跃面试，转发消息到面试处理器
        active_interview_id = session.get("active_interview_id")
        if active_interview_id:
            lock.release()
            return StreamingResponse(
                _interview_text_stream(active_interview_id, request.content, session, store, session_id),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
    except Exception:
        lock.release()
        raise

    async def event_stream():
        """SSE 事件流。"""
        result: dict[str, Any] = {}  # 初始化结果字典，用于异常处理时保存部分结果
        merged_updates: dict[str, Any] = {}  # 流式各节点的增量更新累计
        confirmed_only_profile = False  # 本轮是否仅注入已确认画像条目（非真正提取）
        try:
            # 解析上传的文件（支持缓存）
            jd_text, resume_text = await _parse_uploaded_files(session)

            # 缓存解析后的文本到会话（避免下次重新解析文件）
            session["jd_text"] = jd_text or ""
            session["resume_text"] = resume_text or ""
            session["_parsed_file_count"] = len(session.get("uploaded_files", []))
            # 立即持久化缓存文本（中断时也不丢失）
            await store.update(session_id, {
                "jd_text": session["jd_text"],
                "resume_text": session["resume_text"],
                "_parsed_file_count": session["_parsed_file_count"],
            })

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
                "uploaded_files": session.get("uploaded_files", []),
                "content_iterations": session.get("content_iterations", 0),
                "execution_plan": [],
                "jd_input_version": jd_input_version,
                "profile_input_version": profile_input_version,
                "jd_analyzed_version": session.get("jd_analyzed_version", -1),
                "profile_analyzed_version": session.get("profile_analyzed_version", -1),
                "gap_based_jd": session.get("gap_based_jd", -1),
                "gap_based_profile": session.get("gap_based_profile", -1),
                "content_based_jd": session.get("content_based_jd", -1),
                "content_based_profile": session.get("content_based_profile", -1),
                "interview_based_jd": session.get("interview_based_jd", -1),
                "interview_based_profile": session.get("interview_based_profile", -1),
                "cover_letter_channel": session.get("cover_letter_channel", ""),
                "interview_draft": session.get("interview_draft", {}),
                "memory_summary": memory_summary,
                "messages": session["messages"],
            }

            # 已确认画像条目 → 覆盖/增强 profile 上下文（阶段1 指令1-4）
            # 注意：这是给 agent 的上下文增强，不应被 SSE 当成「画像提取完成」推送
            if session.get("user_id"):
                try:
                    from app.models.database import SessionLocal as _SLocal
                    from app.services.profile_service import build_profile_context
                    _pdb = _SLocal()
                    try:
                        confirmed_profile = build_profile_context(_pdb, session["user_id"])
                    finally:
                        _pdb.close()
                    if confirmed_profile:
                        session_profile = session.get("profile") or {}
                        merged = _normalize_profile_dict({**session_profile, **confirmed_profile})
                        graph_state["profile"] = merged
                        # 会话尚无实质画像、本次只是注入已确认条目 → 标记，跳过产物 SSE
                        if not _is_substantial_profile(session_profile) and not _is_substantial_profile(merged):
                            confirmed_only_profile = True
                except Exception as _p_err:
                    logger.warning(f"[Profile] 读取已确认画像上下文失败: {_p_err}")

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

            # C1 调用级埋点：捕获本次请求全部 LLM 调用（含并行节点与图后 consolidate）
            llm_calls = start_llm_capture()
            llm_calls_sent = 0

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
                    # LLM 调用级埋点（C1）：推送此阶段新完成的调用记录
                    while llm_calls_sent < len(llm_calls):
                        yield _sse_event("llm_call", llm_calls[llm_calls_sent].to_dict())
                        llm_calls_sent += 1
                    # 实时推送该节点产出的关键数据
                    for key, event_name in _NODE_EVENT_MAP.items():
                        if updates.get(key):
                            payload = updates[key]
                            if key == "profile" and isinstance(payload, dict):
                                payload = _normalize_profile_dict(payload)
                            yield _sse_event(event_name, payload)
                    merged_updates.update(updates or {})

                    # 即时持久化该节点的结果字段（中断/刷新时已完成产物不丢）
                    persist = {
                        k: v for k, v in (updates or {}).items()
                        if k in _PERSIST_FIELDS and v is not None
                    }
                    if "profile" in persist and isinstance(persist["profile"], dict):
                        persist["profile"] = _normalize_profile_dict(persist["profile"])
                    if persist:
                        session.update(persist)
                        await store.update(session_id, persist)

            # updates 模式只返回增量，合并初始状态得到最终结果
            result = dict(graph_state)
            result.update(merged_updates)

            # 仅注入已确认条目、本轮未真正提取画像 → 不落库/不合并记忆
            if confirmed_only_profile and "profile" not in merged_updates:
                result.pop("profile", None)

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

            # consolidate 提炼（v3）：上传简历/内容编辑后，LLM 提炼长期档案增量
            if user_id and result.get("intent") in ("upload_profile", "content_edit"):
                try:
                    from app.services.memory_service import MemoryService
                    await MemoryService().consolidate(llm, user_id, request.content)
                    logger.info(f"[Memory] user={user_id} consolidate 完成")
                except Exception as mem_err:
                    logger.warning(f"[Memory] consolidate 失败 user={user_id}: {mem_err}")

            # 面试记录（M3）：多轮追问完成后入库 + 失败教训更新 gaps
            draft = result.get("interview_draft", {})
            if (
                result.get("intent") == "record_interview"
                and draft
                and draft.get("company")
                and draft.get("job_title")
                and draft.get("result")
            ):
                if user_id:
                    try:
                        from app.services.interview_memory import InterviewMemoryService
                        svc = InterviewMemoryService()
                        log = svc.record_interview(user_id, result["interview_draft"])
                        if log is not None:
                            logger.info(f"[Memory] user={user_id} 面试记录已入库 (result={log.result})")
                    except Exception as rec_err:
                        logger.warning(f"[Memory] 面试记录入库失败: {rec_err}")
                else:
                    logger.info("[Memory] 未登录用户，面试记录跳过入库")

            # 复习计划（M3）：新 JD 分析完成且有历史教训 → 生成针对性复习清单
            if (
                user_id
                and result.get("intent") == "upload_jd"
                and result.get("jd_analysis")
                and not result["jd_analysis"].get("_error")
            ):
                try:
                    from app.services.interview_memory import InterviewMemoryService
                    plan = await InterviewMemoryService().build_review_plan(
                        llm, user_id, result.get("jd_analysis", {}), result.get("gap_analysis")
                    )
                    if plan.get("items"):
                        yield _sse_event("review_plan", plan)
                except Exception as plan_err:
                    logger.warning(f"[Memory] 复习计划生成失败: {plan_err}")

            # LLM 埋点收尾（C1）：推送尾部调用记录（consolidate / review_plan 阶段），
            # 汇总随 done 事件下发；记录截断持久化到会话，供 /trace 接口回查
            while llm_calls_sent < len(llm_calls):
                yield _sse_event("llm_call", llm_calls[llm_calls_sent].to_dict())
                llm_calls_sent += 1
            llm_summary = summarize_calls(llm_calls)
            if llm_summary["total_calls"]:
                history = (session.get("llm_calls") or []) + [r.to_dict() for r in llm_calls]
                history = history[-MAX_SESSION_RECORDS:]
                session["llm_calls"] = history
                await store.update(session_id, {"llm_calls": history})

            # 发送路由信息（若本轮产生）
            if result.get("route"):
                yield _sse_event("route", {
                    "route": result["route"],
                    "reason": result.get("route_reason", ""),
                })

            # 兜底推送：若某结果没在流式阶段推送（如并行节点合并后字段缺失），这里补齐
            # 跳过「仅注入已确认画像条目」的 profile，避免前端误展示为画像提取完成
            for key, event_name in _NODE_EVENT_MAP.items():
                if key == "profile" and confirmed_only_profile:
                    continue
                if result.get(key) and not merged_updates.get(key):
                    yield _sse_event(event_name, result[key])

            # 记录助手回复（含执行轨迹）
            assistant_content = _build_assistant_message(result)
            trace_reply = _build_trace_reply(result)
            if trace_reply:
                assistant_content = assistant_content + "\n\n" + trace_reply
            session["messages"].append({
                "role": "assistant",
                "content": assistant_content,
                "timestamp": datetime.now().isoformat(),
            })
            await store.update(session_id, {"messages": session["messages"]})

            # 发送完成事件（附 LLM 调用汇总 + triggered_agents）
            done_payload: dict[str, Any] = {
                "stage": session["stage"],
                "message": assistant_content,
                "triggered_agents": session.get("triggered_agents", []),
            }
            if llm_summary["total_calls"]:
                done_payload["llm_summary"] = llm_summary
            yield _sse_event("done", done_payload)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

            # 错误分类（v3）：统一映射为 (category, hint)，前端可针对性展示
            category, error_hint = _classify_error(e)
            detail = str(e).strip() or error_hint or "处理失败"
            yield _sse_event("error", {
                "detail": detail,
                "hint": error_hint,
                "category": category,
            })

            # 失败路径同样推送/落盘已捕获的 LLM 调用记录（C1）：
            # 超时或异常时定位卡在哪次调用；图启动前失败则无记录可推（跳过）
            try:
                if llm_calls:
                    while llm_calls_sent < len(llm_calls):
                        yield _sse_event("llm_call", llm_calls[llm_calls_sent].to_dict())
                        llm_calls_sent += 1
                    history = (session.get("llm_calls") or []) + [
                        r.to_dict() for r in llm_calls
                    ]
                    await store.update(
                        session_id, {"llm_calls": history[-MAX_SESSION_RECORDS:]}
                    )
            except (NameError, UnboundLocalError):
                pass

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


@router.post("/{session_id}/voice-chat")
async def start_voice_chat(session_id: str):
    """启动 AI 模拟面试语音对话，返回 WebSocket URL。

    前端收到后连接 /ws/voice-chat 并发送 START 消息。
    """
    store = await get_store()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    jd_analysis = session.get("jd_analysis")
    if not jd_analysis:
        raise HTTPException(status_code=400, detail="请先上传或分析 JD 后再开始语音对话")

    return {
        "ws_url": "/ws/voice-chat",
        "session_id": session_id,
    }


@router.post("/{session_id}/voice-chat/feedback")
async def voice_chat_feedback(session_id: str, chat_session_id: str):
    """获取语音对话的反馈报告。"""
    from app.voice.gateway import _chat_handler
    if _chat_handler is None:
        raise HTTPException(status_code=503, detail="语音对话服务未初始化")

    try:
        report = await _chat_handler.get_feedback(chat_session_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Voice chat feedback failed: {e}")
        raise HTTPException(status_code=500, detail="反馈生成失败")


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
    "plan_advance": "推进执行计划",
    "jd_analyzer": "分析职位描述",
    "profile_extractor": "提取简历画像",
    "gap_analyzer": "进行匹配度分析",
    "content_generator": "生成简历内容",
    "interview_qa": "生成面试题",
    "html_renderer": "渲染简历 HTML",
    "question": "回答你的问题",
    "cover_letter": "生成求职文案",
    "clarifier": "记录面试信息",
}

# 节点更新字段 → SSE 事件名（节点产出即实时推送）
_NODE_EVENT_MAP = {
    "jd_analysis": "jd_analysis",
    "profile": "profile",
    "gap_analysis": "gap_analysis",
    "resume_content": "resume_content",
    "render_config": "render_config",
    "interview_questions": "interview_questions",
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
    "content_iterations",
    "cover_letter",
    "cover_letter_channel",
    "interview_draft",
    "execution_plan",
    # 缓存解析后的文本（避免每次消息都重新解析文件）
    "jd_text",
    "resume_text",
    "_parsed_file_count",
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


async def _interview_text_stream(
    interview_id: str,
    user_message: str,
    session: dict[str, Any],
    store: SessionStore,
    session_id: str,
):
    """文字模式面试消息流（面试激活时替代主图）。"""
    try:
        from app.api.interview import _get_handler
        handler = _get_handler()
    except Exception:
        yield _sse_event("error", {"detail": "面试服务未初始化", "category": "service"})
        return

    yield _sse_event("start", {"message": "正在处理回答..."})

    try:
        result = await handler.process_answer(interview_id, user_message)

        question = result.get("question") or ""
        is_complete = result.get("is_complete", False)
        report = result.get("report")

        if question:
            yield _sse_event("interview_question", {"question": question})

        if is_complete:
            # 面试结束，清除活跃面试 ID
            session.pop("active_interview_id", None)
            await store.update(session_id, {"active_interview_id": None})

            # 保存面试报告到跨会话记忆
            user_id = session.get("user_id")
            if user_id and report:
                try:
                    from app.services.interview_memory import InterviewMemoryService
                    svc = InterviewMemoryService()
                    draft = {
                        "company": report.get("target_position", ""),
                        "position": report.get("target_position", ""),
                        "source": "mock",
                        "result": "completed",
                        "feedback": report.get("summary", ""),
                        "lessons": report.get("suggestions", []),
                    }
                    svc.record_interview(user_id, draft)
                    logger.info(f"[Memory] user={user_id} 模拟面试结果已入库")
                except Exception as mem_err:
                    logger.warning(f"[Memory] 模拟面试结果入库失败: {mem_err}")

            yield _sse_event("interview_done", {"report": report})

        yield _sse_event("done", {
            "stage": "interview" if not is_complete else "complete",
            "message": question or "面试已结束",
        })

    except ValueError as e:
        yield _sse_event("error", {"detail": str(e), "category": "not_found"})
    except Exception as e:
        logger.error(f"[InterviewText] error: {e}", exc_info=True)
        yield _sse_event("error", {"detail": str(e), "category": "service"})


def _classify_error(exc: Exception) -> tuple[str, str]:
    """错误分类（v3）：返回 (category, hint)，供前端针对性提示。"""
    detail = str(exc)
    low = detail.lower()

    if "pdf" in low or "docx" in low or "文件" in detail:
        return (
            "file_parse",
            "文件解析失败，请确认：1) 文件是否为文字型 PDF（非扫描件）2) 文件是否损坏 3) 尝试复制文本直接粘贴",
        )
    if "timeout" in low or "超时" in detail:
        return ("timeout", "处理超时，请稍后重试或简化输入内容")
    if "json" in low or "schema" in low or "校验" in detail:
        return ("format", "数据格式解析错误，请重试")
    if isinstance(exc, TimeoutError):
        return ("timeout", "处理超时，请稍后重试或简化输入内容")

    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status == 429:
        return ("rate_limit", "请求过于频繁，请稍后再试")
    if status == 401 or status == 403:
        return ("auth", "认证失败，请检查 API 配置或登录状态")
    if status is not None and int(status) >= 500:
        return ("server", "服务暂时不可用，请稍后重试")

    if isinstance(exc, ValueError):
        return ("validation", "输入数据不合法，请检查后重试")

    return ("unknown", "处理失败，请重试")


def _build_session_updates(session: dict, result: dict) -> dict[str, Any]:
    """从 Graph 结果构建需要更新的字段。"""
    updates: dict[str, Any] = {}

    if result.get("jd_analysis"):
        session["jd_analysis"] = result["jd_analysis"]
        session["stage"] = SessionStage.HAS_JD
        updates["jd_analysis"] = result["jd_analysis"]
        updates["stage"] = session["stage"]

    if result.get("profile"):
        session["profile"] = _normalize_profile_dict(result["profile"])
        if session["stage"] == SessionStage.HAS_JD:
            session["stage"] = SessionStage.HAS_JD_AND_RESUME
        updates["profile"] = session["profile"]
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

    # 面试记录（M3）：多轮追问进度持久化
    if result.get("interview_draft") is not None:
        session["interview_draft"] = result["interview_draft"]
        updates["interview_draft"] = result["interview_draft"]

    # 缓存解析后的文本（避免每次消息都重新解析文件）
    if result.get("jd_text") is not None:
        session["jd_text"] = result["jd_text"]
        updates["jd_text"] = result["jd_text"]
    if result.get("resume_text") is not None:
        session["resume_text"] = result["resume_text"]
        updates["resume_text"] = result["resume_text"]
    if result.get("_parsed_file_count") is not None:
        session["_parsed_file_count"] = result["_parsed_file_count"]
        updates["_parsed_file_count"] = result["_parsed_file_count"]

    # triggered_agents（调试 Tab 用）
    if result.get("workflow_trace"):
        session["triggered_agents"] = [t.get("node", "?") for t in result["workflow_trace"] if t.get("node")]
        updates["triggered_agents"] = session["triggered_agents"]

    updates["updated_at"] = datetime.now().isoformat()
    return updates


def _build_trace_reply(state: dict) -> str:
    """从 workflow_trace 构建 markdown 执行过程。

    参考项目 _build_trace_reply 的等价实现：
    遍历 workflow_trace 列表，拼成 markdown 文本作为助手回复的一部分。
    """
    trace = state.get("workflow_trace", [])
    if not trace:
        return ""

    lines = ["", "**执行过程**"]
    for i, entry in enumerate(trace, 1):
        name = entry.get("node", "?")
        status = entry.get("status", "?")
        summary = entry.get("output_summary", "")
        latency = entry.get("latency_ms", 0)
        dur_str = f"（{int(latency)}ms）" if latency else ""
        status_icon = "✅" if status == "success" else "⏭️" if status == "skipped" else "❌"
        lines.append(f"{i}. {status_icon} {name}{dur_str}：{summary}")

    return "\n".join(lines)


def _build_assistant_message(result: dict) -> str:
    """从 Graph 结果构建助手回复文本。"""
    parts = []

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

    # 面试记录（M3）：收集完成给出确认，否则继续追问
    if result.get("intent") == "record_interview":
        draft = result.get("interview_draft", {})
        if draft.get("company") and draft.get("job_title") and draft.get("result"):
            return "已记录这次面试！失分点已加入你的求职档案，下次面试前我会帮你针对性复习。"
        return result.get("answer", "") or "正在记录面试信息，请继续补充。"

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
