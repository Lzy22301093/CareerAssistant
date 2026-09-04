"""工作流编译 — 用 LangGraph 编排所有 Agent 节点。

v4 简化架构（对齐参考项目 ai-career-copilot）：
- Planner → plan_advance → 业务节点 → plan_advance → ... → END
- 线性流水线，无循环回 planner，无并行容器，无评审迭代
- execution_plan 驱动：plan_advance 弹出已完成节点，advance_plan 取下一个
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.agents import create_agents
from app.graph.nodes import (
    plan_advance_node,
    clarifier_node,
    content_generator_node,
    cover_letter_node,
    gap_analyzer_node,
    html_renderer_node,
    interview_qa_node,
    interview_sim_node,
    jd_analyzer_node,
    planner_node,
    profile_extractor_node,
    question_node,
)
from app.graph.state import GraphState
from app.llm import LLMProvider

logger = logging.getLogger(__name__)

# 编译后的工作流全局缓存
_compiled_graph = None


def get_graph(llm: LLMProvider):
    """获取编译后的工作流（全局缓存，懒加载只构建一次）。"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph(llm)
    return _compiled_graph


def build_graph(llm: LLMProvider) -> StateGraph:
    """构建并编译 LangGraph 工作流。

    v4 架构：
    1. planner 节点：LLM 意图分类 + 查表生成 execution_plan
    2. plan_advance 节点：弹出已完成节点，推进到下一个
    3. 业务节点：执行完后回到 plan_advance
    4. advance_plan 条件边：从 plan 取下一个节点，空则 END

    Args:
        llm: LLM Provider 实例。

    Returns:
        编译后的 StateGraph。
    """
    agents = create_agents(llm)

    # --- 创建节点函数（闭包注入 agents） ---
    async def _planner(state: GraphState):
        return await planner_node(state, agents)

    async def _plan_advance(state: GraphState):
        return await plan_advance_node(state, agents)

    async def _jd_analyzer(state: GraphState):
        return await jd_analyzer_node(state, agents)

    async def _profile_extractor(state: GraphState):
        return await profile_extractor_node(state, agents)

    async def _gap_analyzer(state: GraphState):
        return await gap_analyzer_node(state, agents)

    async def _content_generator(state: GraphState):
        return await content_generator_node(state, agents)

    async def _html_renderer(state: GraphState):
        return await html_renderer_node(state, agents)

    async def _interview_qa(state: GraphState):
        return await interview_qa_node(state, agents)

    async def _question(state: GraphState):
        return await question_node(state, agents)

    async def _cover_letter(state: GraphState):
        return await cover_letter_node(state, agents)

    async def _interview_sim(state: GraphState):
        return await interview_sim_node(state, agents)

    async def _clarifier(state: GraphState):
        return await clarifier_node(state, agents)

    # --- 构建图 ---
    graph = StateGraph(GraphState)

    # 注册节点
    graph.add_node("planner", _planner)
    graph.add_node("plan_advance", _plan_advance)
    graph.add_node("jd_analyzer", _jd_analyzer)
    graph.add_node("profile_extractor", _profile_extractor)
    graph.add_node("gap_analyzer", _gap_analyzer)
    graph.add_node("content_generator", _content_generator)
    graph.add_node("html_renderer", _html_renderer)
    graph.add_node("interview_qa", _interview_qa)
    graph.add_node("question", _question)
    graph.add_node("cover_letter", _cover_letter)
    graph.add_node("interview_sim", _interview_sim)
    graph.add_node("clarifier", _clarifier)

    # 入口：planner
    graph.set_entry_point("planner")

    # 路由函数：从 state.route 读取下一个节点名
    def route_to_node(state: GraphState) -> str:
        return state.get("route", "__end__")

    # planner → plan_advance（planner 写入 execution_plan，plan_advance 弹出第一个）
    graph.add_edge("planner", "plan_advance")

    # plan_advance → 条件分发（从 execution_plan 取下一个，空则 END）
    graph.add_conditional_edges(
        "plan_advance",
        route_to_node,
        {
            "jd_analyzer": "jd_analyzer",
            "profile_extractor": "profile_extractor",
            "gap_analyzer": "gap_analyzer",
            "content_generator": "content_generator",
            "html_renderer": "html_renderer",
            "interview_qa": "interview_qa",
            "question": "question",
            "cover_letter": "cover_letter",
            "interview_sim": "interview_sim",
            "clarifier": "clarifier",
            "__end__": END,
        },
    )

    # 所有业务节点完成后 → plan_advance（弹出当前，取下一个）
    for node_name in [
        "jd_analyzer", "profile_extractor", "gap_analyzer",
        "content_generator", "html_renderer", "interview_qa",
        "interview_sim", "clarifier",
    ]:
        graph.add_edge(node_name, "plan_advance")

    # question / cover_letter → END（单步完成，不经过 plan_advance）
    graph.add_edge("question", END)
    graph.add_edge("cover_letter", END)

    return graph.compile()
