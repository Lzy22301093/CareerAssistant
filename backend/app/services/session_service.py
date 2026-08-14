"""会话管理服务 — 负责会话 CRUD 和消息管理。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import AnalysisSession, UploadedFile
from app.models.redis_session import MemorySessionStore, RedisSessionStore
from app.models.schemas import SessionStage


class SessionService:
    """会话管理服务。

    职责：
    - 创建 / 查询 / 更新 / 删除会话
    - 管理会话消息（对话历史）
    - 同步 Redis 热存储和 MySQL 冷存储
    """

    def __init__(
        self,
        session_store: MemorySessionStore | RedisSessionStore,
        db_session: AsyncSession | None = None,
    ):
        self._store = session_store
        self._db = db_session

    # ---- 会话 CRUD ----

    async def create_session(self) -> dict[str, Any]:
        """创建新会话，返回会话信息。"""
        session_id = f"sess_{uuid.uuid4().hex[:16]}"

        # Redis 热存储
        session_data = self._store.create_session(session_id, {
            "stage": SessionStage.INIT.value,
        })

        # MySQL 持久化（异步，不阻塞）
        if self._db:
            try:
                db_session = AnalysisSession(
                    session_id=session_id,
                    stage=SessionStage.INIT.value,
                )
                self._db.add(db_session)
                await self._db.commit()
            except Exception:
                await self._db.rollback()
                # Redis 已创建，MySQL 失败不影响使用

        return {
            "session_id": session_id,
            "stage": SessionStage.INIT.value,
            "created_at": session_data.get("created_at"),
        }

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """获取会话信息（优先 Redis，fallback MySQL）。"""
        # 先查 Redis
        session_data = self._store.get_session(session_id)
        if session_data:
            return session_data

        # 再查 MySQL
        if self._db:
            result = await self._db.execute(
                select(AnalysisSession).where(AnalysisSession.session_id == session_id)
            )
            db_session = result.scalar_one_or_none()
            if db_session:
                return {
                    "session_id": db_session.session_id,
                    "stage": db_session.stage,
                    "jd_text": db_session.jd_text,
                    "jd_analysis_json": db_session.jd_analysis_json,
                    "profile_json": db_session.profile_json,
                    "gap_analysis_json": db_session.gap_analysis_json,
                    "created_at": db_session.created_at.isoformat(),
                    "updated_at": db_session.updated_at.isoformat(),
                }

        return None

    async def update_session(
        self, session_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """更新会话数据。"""
        # 更新 Redis
        updated = self._store.update_session(session_id, data)
        if not updated:
            return None

        # 同步关键字段到 MySQL
        if self._db:
            try:
                result = await self._db.execute(
                    select(AnalysisSession).where(AnalysisSession.session_id == session_id)
                )
                db_session = result.scalar_one_or_none()
                if db_session:
                    if "stage" in data:
                        db_session.stage = data["stage"]
                    if "jd_text" in data:
                        db_session.jd_text = data["jd_text"]
                    if "jd_analysis" in data:
                        db_session.jd_analysis_json = json.dumps(data["jd_analysis"], ensure_ascii=False)
                    if "profile" in data:
                        db_session.profile_json = json.dumps(data["profile"], ensure_ascii=False)
                    if "gap_analysis" in data:
                        db_session.gap_analysis_json = json.dumps(data["gap_analysis"], ensure_ascii=False)
                    if "render_config" in data:
                        db_session.render_config_json = json.dumps(data["render_config"], ensure_ascii=False)
                    await self._db.commit()
            except Exception:
                await self._db.rollback()

        return updated

    async def delete_session(self, session_id: str) -> bool:
        """删除会话。"""
        # 删除 Redis
        redis_ok = self._store.delete_session(session_id)

        # 删除 MySQL
        if self._db:
            try:
                result = await self._db.execute(
                    select(AnalysisSession).where(AnalysisSession.session_id == session_id)
                )
                db_session = result.scalar_one_or_none()
                if db_session:
                    await self._db.delete(db_session)
                    await self._db.commit()
            except Exception:
                await self._db.rollback()

        return redis_ok

    # ---- 消息管理 ----

    def add_message(
        self, session_id: str, role: str, content: str
    ) -> bool:
        """添加消息到对话历史。"""
        return self._store.append_message(session_id, {
            "role": role,
            "content": content,
        })

    def get_messages(
        self, session_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """获取对话历史。"""
        session = self._store.get_session(session_id)
        if not session:
            return []
        messages = session.get("messages", [])
        return messages[-limit:]

    # ---- 文件管理 ----

    async def save_uploaded_file(
        self,
        session_id: str,
        filename: str,
        file_type: str,
        file_path: str,
        file_size: int = 0,
    ) -> dict[str, Any]:
        """记录上传文件。"""
        if not self._db:
            return {"filename": filename, "file_type": file_type}

        try:
            uploaded = UploadedFile(
                session_id=session_id,
                filename=filename,
                file_type=file_type,
                file_path=file_path,
                file_size=file_size,
            )
            self._db.add(uploaded)
            await self._db.commit()
            return {
                "id": uploaded.id,
                "filename": filename,
                "file_type": file_type,
                "file_path": file_path,
            }
        except Exception:
            await self._db.rollback()
            return {"filename": filename, "file_type": file_type}

    # ---- 辅助方法 ----

    def get_stage(self, session_id: str) -> str:
        """获取会话当前阶段。"""
        session = self._store.get_session(session_id)
        if not session:
            return SessionStage.INIT.value
        return session.get("stage", SessionStage.INIT.value)

    def set_stage(self, session_id: str, stage: str) -> bool:
        """设置会话阶段。"""
        result = self._store.update_session(session_id, {"stage": stage})
        return result is not None
