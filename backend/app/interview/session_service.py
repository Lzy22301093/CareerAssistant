"""Interview Session Service — 面试会话持久化。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from app.models.session_store import SessionStore

logger = logging.getLogger(__name__)


class InterviewSessionService:
    """面试会话管理，复用 SessionStore 接口。"""

    KEY_PREFIX = "interview:"

    def __init__(self, store: SessionStore):
        self._store = store

    def _key(self, interview_id: str) -> str:
        return f"{self.KEY_PREFIX}{interview_id}"

    async def create(self, state: dict[str, Any]) -> str:
        """创建面试会话，返回 interview_id。"""
        interview_id = state.get("interview_id") or str(uuid.uuid4())
        state["interview_id"] = interview_id
        await self._store.create(self._key(interview_id), state)
        logger.info(f"[InterviewSession] created: {interview_id}")
        return interview_id

    async def save(self, interview_id: str, state: dict[str, Any]) -> None:
        """保存面试状态。"""
        state["interview_id"] = interview_id
        await self._store.update(self._key(interview_id), state)

    async def load(self, interview_id: str) -> dict[str, Any] | None:
        """加载面试状态。"""
        return await self._store.get(self._key(interview_id))

    async def delete(self, interview_id: str) -> bool:
        """删除面试会话。"""
        return await self._store.delete(self._key(interview_id))

    async def exists(self, interview_id: str) -> bool:
        """检查面试会话是否存在。"""
        return await self._store.exists(self._key(interview_id))


async def save_interview_report(
    interview_id: str,
    state: dict[str, Any],
    db_session=None,
) -> None:
    """将面试报告写入 MySQL。"""
    if db_session is None:
        return

    from app.models.orm import InterviewReport

    report = state.get("final_report", {})
    report_row = InterviewReport(
        interview_id=interview_id,
        session_id=state.get("session_id"),
        user_id=state.get("user_id"),
        target_position=state.get("target_position", ""),
        difficulty_level=state.get("difficulty_level", "medium"),
        turn_count=state.get("turn_count", 0),
        dimension_scores_json=json.dumps(state.get("dimension_scores", {}), ensure_ascii=False),
        strengths_json=json.dumps(state.get("strengths", []), ensure_ascii=False),
        weaknesses_json=json.dumps(state.get("weaknesses", []), ensure_ascii=False),
        conversation_history_json=json.dumps(state.get("conversation_history", []), ensure_ascii=False),
        final_report_json=json.dumps(report, ensure_ascii=False),
        completion_reason=state.get("completion_reason", ""),
    )
    db_session.add(report_row)
    await db_session.commit()
    logger.info(f"[InterviewSession] report saved to MySQL: {interview_id}")
