"""VoiceInterviewHandler — 可打断的面试执行器。

包装 InterviewHandler，将 process_answer 拆分为可中断的步骤：
1. evaluate（LLM 调用 ~3s）
2. decide_next（纯函数 <1ms）
3. ask_question（LLM 调用 ~3s）

每步 LLM 调用前检查 interrupt_event，被打断时保存中间状态。

恢复规则：
- evaluate 被打断 → 下轮重新 evaluate（current_answer 保留）
- evaluate 完成 + ask_question 被打断 → 下轮跳过 evaluate，直接 ask_question
- TTS 播放中被打断 → question 已生成，下轮直接用
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.interview.edges import decide_next
from app.interview.handler import InterviewHandler
from app.interview.nodes import adjust_difficulty_node, ask_question_node, evaluate_node, finish_node, generate_report_node

logger = logging.getLogger(__name__)


class VoiceInterviewHandler:
    """可打断的面试执行器。"""

    def __init__(self, handler: InterviewHandler):
        self._handler = handler

    async def process_answer_interruptible(
        self,
        interview_id: str,
        answer: str,
        interrupt_event: asyncio.Event,
    ) -> dict[str, Any] | None:
        """处理用户回答，支持中断。

        Returns:
            正常完成: {"question": str, "is_complete": bool, "report": dict}
            被打断: None（中间状态已保存）
        """
        # 加载状态
        state = await self._handler.session_service.load(interview_id)
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

        # 检查是否有未完成的打断恢复点
        checkpoint = state.get("interrupt_checkpoint")
        if checkpoint:
            state = await self._resume_from_checkpoint(state, checkpoint, interrupt_event)
            if state is None:
                return None
        else:
            # 正常流程：evaluate → decide → ask/finish
            state = await self._full_pipeline(state, interrupt_event)
            if state is None:
                return None

        # 保存状态
        await self._handler.session_service.save(interview_id, state)

        if state.get("is_complete"):
            # 持久化报告
            if self._handler.on_complete:
                try:
                    await self._handler.on_complete(interview_id, state)
                except Exception as e:
                    logger.error(f"on_complete callback failed: {e}")
            return {
                "question": None,
                "is_complete": True,
                "report": state.get("final_report"),
            }

        question = state.get("current_question", "请继续。")
        return {
            "question": question,
            "is_complete": False,
            "report": None,
        }

    async def _full_pipeline(
        self,
        state: dict[str, Any],
        interrupt_event: asyncio.Event,
    ) -> dict[str, Any] | None:
        """完整流水线：evaluate → decide_next → ask/finish。"""
        agents = self._handler.agents

        # ── 步骤1: evaluate ──
        if interrupt_event.is_set():
            state["interrupt_checkpoint"] = "pending_evaluate"
            await self._handler.session_service.save(state["interview_id"], state)
            logger.info(f"[Interrupt] before evaluate, saved checkpoint")
            return None

        try:
            eval_result = await asyncio.wait_for(
                evaluate_node(state, agents),
                timeout=30,
            )
            state.update(eval_result)
        except asyncio.TimeoutError:
            logger.warning("[Interrupt] evaluate timed out")
            state["interrupt_checkpoint"] = "pending_evaluate"
            await self._handler.session_service.save(state["interview_id"], state)
            return None
        except asyncio.CancelledError:
            state["interrupt_checkpoint"] = "pending_evaluate"
            await self._handler.session_service.save(state["interview_id"], state)
            logger.info("[Interrupt] evaluate cancelled")
            return None

        # 更新维度评分
        self._update_dimension_scores(state)

        # ── 步骤2: decide_next（纯函数，无需检查 interrupt）──
        next_action = decide_next(state)
        state["next_action"] = next_action

        # ── 步骤3: ask_question 或 finish ──
        if next_action in ("finish", "结束面试"):
            return await self._do_finish(state, agents)

        if next_action == "adjust_difficulty":
            diff_result = await adjust_difficulty_node(state, agents)
            state.update(diff_result)

        if interrupt_event.is_set():
            state["interrupt_checkpoint"] = "pending_ask_question"
            await self._handler.session_service.save(state["interview_id"], state)
            logger.info(f"[Interrupt] after evaluate, before ask_question")
            return None

        try:
            ask_result = await asyncio.wait_for(
                ask_question_node(state, agents),
                timeout=30,
            )
            state.update(ask_result)
        except asyncio.TimeoutError:
            logger.warning("[Interrupt] ask_question timed out")
            state["interrupt_checkpoint"] = "pending_ask_question"
            await self._handler.session_service.save(state["interview_id"], state)
            return None
        except asyncio.CancelledError:
            state["interrupt_checkpoint"] = "pending_ask_question"
            await self._handler.session_service.save(state["interview_id"], state)
            logger.info("[Interrupt] ask_question cancelled")
            return None

        # 清除 checkpoint
        state.pop("interrupt_checkpoint", None)
        return state

    async def _resume_from_checkpoint(
        self,
        state: dict[str, Any],
        checkpoint: str,
        interrupt_event: asyncio.Event,
    ) -> dict[str, Any] | None:
        """从打断断点恢复执行。"""
        agents = self._handler.agents

        if checkpoint == "pending_evaluate":
            # 重新执行完整流水线
            state.pop("interrupt_checkpoint", None)
            return await self._full_pipeline(state, interrupt_event)

        if checkpoint == "pending_ask_question":
            # 跳过 evaluate，直接 ask_question
            state.pop("interrupt_checkpoint", None)

            if interrupt_event.is_set():
                state["interrupt_checkpoint"] = "pending_ask_question"
                await self._handler.session_service.save(state["interview_id"], state)
                return None

            try:
                ask_result = await asyncio.wait_for(
                    ask_question_node(state, agents),
                    timeout=30,
                )
                state.update(ask_result)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                state["interrupt_checkpoint"] = "pending_ask_question"
                await self._handler.session_service.save(state["interview_id"], state)
                return None

            state.pop("interrupt_checkpoint", None)
            return state

        # 未知 checkpoint，重新走完整流程
        state.pop("interrupt_checkpoint", None)
        return await self._full_pipeline(state, interrupt_event)

    async def _do_finish(
        self,
        state: dict[str, Any],
        agents: dict[str, Any],
    ) -> dict[str, Any]:
        """执行结束流程。"""
        finish_result = await finish_node(state, agents)
        state.update(finish_result)

        report_result = await generate_report_node(state, agents)
        state.update(report_result)

        state["is_complete"] = True
        return state

    def _update_dimension_scores(self, state: dict[str, Any]) -> None:
        """更新维度评分（加权平均）。"""
        eval_data = state.get("current_evaluation", {})
        new_scores = eval_data.get("dimension_scores", {})
        if not new_scores:
            return

        old_scores = state.get("dimension_scores", {})
        turn = state.get("turn_count", 0)

        for dim, score in new_scores.items():
            if turn <= 1:
                old_scores[dim] = score
            else:
                old_scores[dim] = old_scores.get(dim, score) * 0.7 + score * 0.3

        state["dimension_scores"] = old_scores
