"""InterviewHandler — 驱动面试循环，桥接 Voice Layer 和 Interview Graph。"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from app.interview.graph import get_continue_graph, get_interview_graph
from app.interview.session_service import InterviewSessionService

logger = logging.getLogger(__name__)

# 面试完成时的回调类型：(interview_id, state) -> None
OnCompleteCallback = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]

# 默认初始状态
DEFAULT_STATE = {
    "difficulty_level": "medium",
    "interview_mode": "mixed",
    "phase": "opening",
    "current_question": "",
    "current_answer": "",
    "turn_count": 0,
    "max_turns": 10,
    "conversation_history": [],
    "dimension_scores": {},
    "current_evaluation": {},
    "strengths": [],
    "weaknesses": [],
    "next_action": "",
    "covered_topics": [],
    "pending_topics": [],
    "is_active": False,
    "is_complete": False,
    "completion_reason": "",
    "final_report": {},
    "referenced_questions": [],
}


class InterviewHandler:
    """驱动面试循环。

    使用方式：
        handler = InterviewHandler(agents, session_service)
        question = await handler.start_interview(jd_analysis, profile)
        next_q = await handler.process_answer(interview_id, "用户回答")
    """

    def __init__(
        self,
        agents: dict[str, Any],
        session_service: InterviewSessionService,
        on_complete: OnCompleteCallback | None = None,
    ):
        self.agents = agents
        self.session_service = session_service
        self.on_complete = on_complete
        self._start_graph = get_interview_graph(agents)
        self._continue_graph = get_continue_graph(agents)

    async def start_interview(
        self,
        jd_analysis: dict,
        profile: dict,
        referenced_questions: list[str] | None = None,
        max_turns: int = 10,
        user_id: int | None = None,
        resume: dict | None = None,
        use_profile_as_supplement: bool = True,
    ) -> dict[str, Any]:
        """开始新面试。JD+简历为主，画像可选补充。"""
        interview_id = str(uuid.uuid4())
        target_position = jd_analysis.get("job_title", "")

        from app.interview.context import compact_profile, compact_resume

        initial_state = {
            **DEFAULT_STATE,
            "session_id": interview_id,
            "interview_id": interview_id,
            "jd_analysis": jd_analysis or {},
            "profile": compact_profile(profile) if use_profile_as_supplement else {},
            "resume": compact_resume(resume),
            "use_profile_as_supplement": use_profile_as_supplement,
            "target_position": target_position,
            "referenced_questions": referenced_questions or [],
            "max_turns": max_turns,
            "user_id": user_id,
        }

        # 执行首次图：open_interview
        result = await self._start_graph.ainvoke(initial_state)

        # 保存状态
        await self.session_service.create(result)

        question = result.get("current_question", "请介绍一下你自己。")
        return {
            "interview_id": interview_id,
            "question": question,
            "state": result,
        }

    async def process_answer(
        self,
        interview_id: str,
        answer: str,
    ) -> dict[str, Any]:
        """处理用户回答。

        Returns:
            {"question": str, "is_complete": bool, "report": dict | None}
        """
        # 加载状态
        state = await self.session_service.load(interview_id)
        if not state:
            raise ValueError(f"Interview not found: {interview_id}")

        if state.get("is_complete"):
            return {
                "question": None,
                "is_complete": True,
                "report": state.get("final_report"),
            }

        # 注入用户回答
        state["current_answer"] = answer

        # 执行后续图：evaluate → decide_next → ask_question/finish
        result = await self._continue_graph.ainvoke(state)

        # 保存状态
        await self.session_service.save(interview_id, result)

        if result.get("is_complete"):
            # 持久化报告（回调由 API 层注入）
            if self.on_complete:
                try:
                    await self.on_complete(interview_id, result)
                except Exception as e:
                    logger.error(f"[InterviewHandler] on_complete callback failed: {e}")
            return {
                "question": None,
                "is_complete": True,
                "report": result.get("final_report"),
            }

        question = result.get("current_question", "请继续。")
        return {
            "question": question,
            "is_complete": False,
            "report": None,
        }

    async def get_state(self, interview_id: str) -> dict[str, Any] | None:
        """获取面试状态。"""
        return await self.session_service.load(interview_id)
