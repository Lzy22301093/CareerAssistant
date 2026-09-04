"""Interview Graph 条件路由。"""

from __future__ import annotations

from app.interview.state import InterviewState


def decide_next(state: InterviewState) -> str:
    """根据 Evaluator 的决策路由到下一个节点。"""
    turn = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 10)
    pending = state.get("pending_topics", [])
    action = state.get("next_action", "切换话题")

    # 检查是否应该结束
    if turn >= max_turns:
        return "finish"
    if action == "结束面试":
        return "finish"
    if not pending and action not in ("追问",):
        return "finish"

    # 根据动作路由
    if action == "追问":
        return "ask_question"
    elif action in ("切换话题",):
        return "ask_question"
    elif action in ("提高难度", "降低难度"):
        return "adjust_difficulty"
    else:
        return "ask_question"
