"""Interview Graph — 模拟面试 LangGraph 子图构建。"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.interview.edges import decide_next
from app.interview.nodes import (
    adjust_difficulty_node,
    ask_question_node,
    evaluate_node,
    finish_node,
    generate_report_node,
    open_interview_node,
)
from app.interview.state import InterviewState

logger = logging.getLogger(__name__)

_compiled_graph = None


def build_interview_graph(agents: dict[str, Any]):
    """构建 Interview LangGraph 子图。

    执行模式：每次 ainvoke 执行从当前状态到下一个等待点的路径。
    InterviewHandler 控制面试循环，不是图自己循环。

    首次调用：START → open_interview → ask_question → END
    后续调用：START → evaluate → decide_next → ask_question → END
    结束调用：START → evaluate → decide_next → finish → generate_report → END
    """
    graph = StateGraph(InterviewState)

    # 注入 agents 的闭包（必须是 async def）
    async def _open(state):
        return await open_interview_node(state, agents)

    async def _ask(state):
        return await ask_question_node(state, agents)

    # 添加节点
    graph.add_node("open_interview", _open)
    graph.add_node("ask_question", _ask)

    # 入口
    graph.set_entry_point("open_interview")

    # 首次流程：open_interview → ask_question → END
    graph.add_edge("open_interview", "ask_question")
    graph.add_edge("ask_question", END)

    return graph


def get_interview_graph(agents: dict[str, Any]):
    """获取编译后的 Interview Graph（懒加载单例）。"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_interview_graph(agents).compile()
        logger.info("Interview graph compiled")
    return _compiled_graph


def build_continue_graph(agents: dict[str, Any]):
    """构建后续轮次的图（evaluate → decide_next → ...）。"""
    graph = StateGraph(InterviewState)

    async def _evaluate(state):
        return await evaluate_node(state, agents)

    async def _ask(state):
        return await ask_question_node(state, agents)

    async def _adjust(state):
        return await adjust_difficulty_node(state, agents)

    async def _finish(state):
        return await finish_node(state, agents)

    async def _report(state):
        return await generate_report_node(state, agents)

    graph.add_node("evaluate", _evaluate)
    graph.add_node("ask_question", _ask)
    graph.add_node("adjust_difficulty", _adjust)
    graph.add_node("finish", _finish)
    graph.add_node("generate_report", _report)

    graph.set_entry_point("evaluate")

    # 条件路由
    graph.add_conditional_edges(
        "evaluate",
        decide_next,
        {
            "ask_question": "ask_question",
            "adjust_difficulty": "adjust_difficulty",
            "finish": "finish",
        },
    )

    graph.add_edge("adjust_difficulty", "ask_question")
    graph.add_edge("ask_question", END)
    graph.add_edge("finish", "generate_report")
    graph.add_edge("generate_report", END)

    return graph


_continue_graph = None


def get_continue_graph(agents: dict[str, Any]):
    """获取编译后的后续轮次图（懒加载单例）。"""
    global _continue_graph
    if _continue_graph is None:
        _continue_graph = build_continue_graph(agents).compile()
        logger.info("Interview continue graph compiled")
    return _continue_graph
