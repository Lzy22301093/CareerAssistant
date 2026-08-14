"""状态管理工具：state_reader, state_writer。"""

from __future__ import annotations

from typing import Any

from .base import Tool, ToolResult


class StateReaderTool(Tool):
    """状态读取工具 — 读取会话状态和记忆。"""

    name = "state_reader"
    description = "读取会话状态、用户偏好、历史数据等。"
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "会话 ID",
            },
            "key": {
                "type": "string",
                "description": "要读取的状态键（如 'profile', 'jd_analysis', 'preferences'）",
            },
            "memory_type": {
                "type": "string",
                "enum": ["short_term", "working", "long_term"],
                "description": "记忆类型",
            },
        },
        "required": ["session_id", "key"],
    }

    def __init__(self, session_store=None, db_session=None):
        self._session_store = session_store
        self._db_session = db_session

    async def execute(
        self,
        session_id: str,
        key: str,
        memory_type: str = "working",
        **kwargs,
    ) -> ToolResult:
        """读取状态。"""
        try:
            if memory_type == "short_term":
                data = await self._read_short_term(session_id, key)
            elif memory_type == "long_term":
                data = await self._read_long_term(session_id, key)
            else:
                data = await self._read_working(session_id, key)

            return ToolResult.ok({"key": key, "value": data})
        except Exception as e:
            return ToolResult.fail(f"状态读取失败: {e}")

    async def _read_short_term(self, session_id: str, key: str) -> Any:
        """读取短期记忆（Redis）。"""
        if not self._session_store:
            return None

        session = await self._session_store.get_session(session_id)
        if not session:
            return None

        return session.get(key)

    async def _read_working(self, session_id: str, key: str) -> Any:
        """读取工作记忆（GraphState）。"""
        # 工作记忆通常在 GraphState 中，这里返回 None
        # 实际使用时会在 Agent 中直接访问 GraphState
        return None

    async def _read_long_term(self, session_id: str, key: str) -> Any:
        """读取长期记忆（MySQL）。"""
        if not self._db_session:
            return None

        # 查询用户偏好
        if key == "preferences":
            from ..models.orm import AnalysisSession

            session = self._db_session.query(AnalysisSession).filter(
                AnalysisSession.id == session_id
            ).first()

            if session and session.jd_analysis:
                return session.jd_analysis.get("preferences")

        return None


class StateWriterTool(Tool):
    """状态写入工具 — 写入会话状态和记忆。"""

    name = "state_writer"
    description = "写入会话状态、用户偏好、历史数据等。"
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "会话 ID",
            },
            "key": {
                "type": "string",
                "description": "要写入的状态键",
            },
            "value": {
                "description": "要写入的值",
            },
            "memory_type": {
                "type": "string",
                "enum": ["short_term", "working", "long_term"],
                "description": "记忆类型",
            },
        },
        "required": ["session_id", "key", "value"],
    }

    def __init__(self, session_store=None, db_session=None):
        self._session_store = session_store
        self._db_session = db_session

    async def execute(
        self,
        session_id: str,
        key: str,
        value: Any,
        memory_type: str = "working",
        **kwargs,
    ) -> ToolResult:
        """写入状态。"""
        try:
            if memory_type == "short_term":
                await self._write_short_term(session_id, key, value)
            elif memory_type == "long_term":
                await self._write_long_term(session_id, key, value)
            else:
                await self._write_working(session_id, key, value)

            return ToolResult.ok({"key": key, "written": True})
        except Exception as e:
            return ToolResult.fail(f"状态写入失败: {e}")

    async def _write_short_term(self, session_id: str, key: str, value: Any):
        """写入短期记忆（Redis）。"""
        if not self._session_store:
            return

        session = await self._session_store.get_session(session_id)
        if session:
            session[key] = value
            await self._session_store.update_session(session_id, session)

    async def _write_working(self, session_id: str, key: str, value: Any):
        """写入工作记忆（GraphState）。"""
        # 工作记忆通常在 GraphState 中，这里不做持久化
        pass

    async def _write_long_term(self, session_id: str, key: str, value: Any):
        """写入长期记忆（MySQL）。"""
        if not self._db_session:
            return

        # 更新用户偏好
        if key == "preferences":
            from ..models.orm import AnalysisSession

            session = self._db_session.query(AnalysisSession).filter(
                AnalysisSession.id == session_id
            ).first()

            if session:
                jd_analysis = session.jd_analysis or {}
                jd_analysis["preferences"] = value
                session.jd_analysis = jd_analysis
                self._db_session.commit()
