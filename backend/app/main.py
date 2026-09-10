"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.applications import router as applications_router
from app.api.health import router as health_router
from app.api.interview import router as interview_router
from app.api.matching import router as matching_router
from app.api.preferences import router as preferences_router
from app.api.profile import router as profile_router
from app.api.proposals import router as proposals_router
from app.api.resume_generation import router as resume_generation_router
from app.api.resume_library import router as resume_library_router
from app.api.sessions import router as sessions_router
from app.config import settings
from app.models.init_db import init_database

app = FastAPI(title=settings.app_title, debug=settings.debug)


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables on startup and initialize interview handler."""
    init_database()
    # 初始化 Interview Handler
    try:
        from app.agents import create_interview_agents
        from app.api.interview import set_handler
        from app.interview.handler import InterviewHandler
        from app.interview.session_service import InterviewSessionService, save_interview_report
        from app.llm import create_llm_provider
        from app.models.session_store import InMemorySessionStore, RedisSessionStore

        llm = create_llm_provider()
        agents = create_interview_agents(llm)

        # 生产环境用 Redis，开发环境用内存。
        # 注意：RedisSessionStore 的第一个参数必须是异步 redis 客户端对象，
        # 不能直接传 URL 字符串，否则其内部 .set() 会抛 "'str' object has no attribute 'set'"。
        # 这里与 api/sessions.py 的 get_store() 保持一致：用 aioredis.from_url 创建客户端，
        # 并在 Redis 不可用时回退到内存存储。
        if settings.redis_url:
            try:
                import redis.asyncio as aioredis
                store = RedisSessionStore(
                    aioredis.from_url(settings.redis_url, decode_responses=True)
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Redis unavailable for interview, using in-memory: {e}"
                )
                store = InMemorySessionStore()
        else:
            store = InMemorySessionStore()

        session_service = InterviewSessionService(store)

        async def _on_interview_complete(interview_id: str, state: dict) -> None:
            """面试完成时持久化报告到 MySQL + 写入跨会话记忆。"""
            from app.models.database import SessionLocal
            db = SessionLocal()
            try:
                await save_interview_report(interview_id, state, db)
            except Exception as e:
                logging.getLogger(__name__).error(f"Save interview report failed: {e}")
            finally:
                db.close()

            # 面试报告 → 画像更新提案（阶段1 指令1-1）
            user_id = state.get("user_id")
            if user_id:
                db2 = SessionLocal()
                try:
                    from app.services.proposal_service import build_proposals_from_state
                    proposals = build_proposals_from_state(db2, int(user_id), interview_id, state)
                    logging.getLogger(__name__).info(
                        f"[Proposal] user={user_id} 生成 {len(proposals)} 条画像更新提案"
                    )
                except Exception as mem_err:
                    logging.getLogger(__name__).warning(f"[Proposal] 提案生成失败: {mem_err}")
                finally:
                    db2.close()

        handler = InterviewHandler(agents, session_service, on_complete=_on_interview_complete)
        set_handler(handler)

        # 初始化语音服务
        from app.voice.gateway import init_voice_services, websocket_interview, websocket_voice_chat
        init_voice_services(handler)
        # WebSocket 路由需要在 startup 外注册，但 handler 依赖 startup，
        # 所以用 app.websocket_route 而非 router
        app.add_api_websocket_route("/ws/interview", websocket_interview)
        app.add_api_websocket_route("/ws/voice-chat", websocket_voice_chat)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Interview handler init failed: {e}")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(applications_router, prefix="/api/applications", tags=["applications"])
app.include_router(preferences_router, prefix="/api/preferences", tags=["preferences"])
app.include_router(profile_router, prefix="/api/profile", tags=["profile"])
app.include_router(proposals_router, prefix="/api/profile/proposals", tags=["proposals"])
app.include_router(resume_library_router, prefix="/api/resumes", tags=["resume-library"])
app.include_router(resume_generation_router, prefix="/api/resume-generation", tags=["resume-generation"])
app.include_router(matching_router, prefix="/api/matching", tags=["matching"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(interview_router, prefix="/api/interview", tags=["interview"])
