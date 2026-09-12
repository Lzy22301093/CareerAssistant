"""Interview Graph 条件路由。"""

from __future__ import annotations

from app.interview.state import InterviewState


def decide_next(state: InterviewState) -> str:
    """根据 Evaluator 的决策路由到下一个节点。

    约束：用户设定的 max_turns 优先——未满轮数时不因「结束面试」/话题耗尽提前结束，
    改为降低难度或继续出题，避免「我不会」一轮就被判结束。
    """
    turn = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 10)
    pending = state.get("pending_topics", [])
    action = state.get("next_action", "切换话题")

    # 达到最大轮数才允许结束
    if turn >= max_turns:
        return "finish"

    if action == "结束面试":
        # 轮数未满：降级为继续考察，而不是直接结束
        return "adjust_difficulty" if pending else "ask_question"

    if not pending and action not in ("追问",):
        # 话题耗尽但轮数未满：继续出题
        return "ask_question"

    if action == "追问":
        return "ask_question"
    elif action in ("切换话题",):
        return "ask_question"
    elif action in ("提高难度", "降低难度"):
        return "adjust_difficulty"
    else:
        return "ask_question"
