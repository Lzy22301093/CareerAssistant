"""工作流编译 — 用 LangGraph 编排所有 Agent 节点。

图结构设计：
- 使用规则引擎进行路由决策（无需 LLM 调用）
- 支持并行执行：JD Analyzer + Profile Extractor（parallel_analysis）、
  简历评审 + 面试题生成（parallel_post）
- 只有当 jd_analysis 和 profile 都存在时，才能进入 gap_analyzer
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.agents import create_agents
from app.graph.edges import (
    route_after_planner,
    route_after_clarifier,
    route_after_parallel_analysis,
    route_after_parallel_post,
    route_after_interview_review,
)
from app.graph.nodes import (
    clarifier_node,
    content_generator_node,
    cover_letter_node,
    gap_analyzer_node,
    html_renderer_node,
    interview_qa_node,
    interview_reviewer_node,
    jd_analyzer_node,
    parallel_analysis_node,
    parallel_post_node,
    planner_node,
    profile_extractor_node,
    question_node,
)
from app.graph.state import GraphState
from app.llm import LLMProvider

logger = logging.getLogger(__name__)

# 编译后的工作流全局缓存：图结构是静态的，应用生命周期内只构建一次
_compiled_graph = None


def get_graph(llm: LLMProvider):
    """获取编译后的工作流（全局缓存，懒加载只构建一次）。

    Args:
        llm: LLM Provider 实例（仅在首次构建时使用）。

    Returns:
        编译后的 StateGraph（可直接 ainvoke）。
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph(llm)
    return _compiled_graph


def build_graph(llm: LLMProvider) -> StateGraph:
    """构建并编译 LangGraph 工作流。

    核心设计：
    1. 使用规则引擎路由，避免 Planner 的 LLM 调用开销
    2. JD Analyzer 和 Profile Extractor 可并行执行
    3. HTML Renderer 和 Interview Q&A 可并行执行
    4. 所有分析节点完成后回到 Planner 重新决策

    Args:
        llm: LLM Provider 实例。

    Returns:
        编译后的 StateGraph（可直接 invoke）。
    """
    agents = create_agents(llm)

    # --- 创建节点函数（闭包注入 agents） ---
    async def _planner(state: GraphState):
        return await planner_node(state, agents)

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

    async def _interview_reviewer(state: GraphState):
        return await interview_reviewer_node(state, agents)

    async def _parallel_analysis(state: GraphState):
        return await parallel_analysis_node(state, agents)

    async def _parallel_post(state: GraphState):
        return await parallel_post_node(state, agents)

    async def _clarifier(state: GraphState):
        return await clarifier_node(state, agents)

    async def _question(state: GraphState):
        return await question_node(state, agents)

    async def _cover_letter(state: GraphState):
        return await cover_letter_node(state, agents)

    # --- 构建图 ---
    graph = StateGraph(GraphState)

    # 注册节点
    graph.add_node("planner", _planner)
    graph.add_node("jd_analyzer", _jd_analyzer)
    graph.add_node("profile_extractor", _profile_extractor)
    graph.add_node("gap_analyzer", _gap_analyzer)
    graph.add_node("content_generator", _content_generator)
    graph.add_node("html_renderer", _html_renderer)
    graph.add_node("interview_qa", _interview_qa)
    graph.add_node("interview_reviewer", _interview_reviewer)
    graph.add_node("parallel_analysis", _parallel_analysis)
    graph.add_node("parallel_post", _parallel_post)
    graph.add_node("clarifier", _clarifier)
    graph.add_node("question", _question)
    graph.add_node("cover_letter", _cover_letter)

    # 入口
    graph.set_entry_point("planner")

    # Planner 之后的条件边：意图/规则引擎路由
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "jd_analyzer": "jd_analyzer",
            "profile_extractor": "profile_extractor",
            "gap_analyzer": "gap_analyzer",
            "content_generator": "content_generator",
            "html_renderer": "html_renderer",
            "interview_qa": "interview_qa",
            "parallel_analysis": "parallel_analysis",
            "clarifier": "clarifier",
            "question": "question",
            "cover_letter": "cover_letter",
            "end": END,
        },
    )

    # 单个分析节点完成后回到 Planner
    graph.add_edge("jd_analyzer", "planner")
    graph.add_edge("profile_extractor", "planner")
    graph.add_edge("gap_analyzer", "planner")

    # 并行分析完成后回到 Planner
    graph.add_conditional_edges(
        "parallel_analysis",
        route_after_parallel_analysis,
        {"planner": "planner"},
    )

    # Content Generator → Parallel Post（简历评审 ∥ 面试题生成）
    graph.add_edge("content_generator", "parallel_post")

    # Parallel Post 之后的条件边：评审通过 → HTML 渲染；不通过 → 迭代
    graph.add_conditional_edges(
        "parallel_post",
        route_after_parallel_post,
        {
            "iterate": "content_generator",
            "proceed": "html_renderer",
        },
    )

    # HTML Renderer → Interview Reviewer（面试题已在 parallel_post 生成）
    graph.add_edge("html_renderer", "interview_reviewer")

    # Interview Q&A → Interview Reviewer（评审循环 / 兜底补生成）
    graph.add_edge("interview_qa", "interview_reviewer")

    # Interview Reviewer 之后的条件边：评审通过 → 结束；不通过 → 迭代
    graph.add_conditional_edges(
        "interview_reviewer",
        route_after_interview_review,
        {
            "iterate": "interview_qa",
            "proceed": END,
        },
    )

    # Clarifier 之后的条件边：继续处理 or 等待用户回复
    graph.add_conditional_edges(
        "clarifier",
        route_after_clarifier,
        {
            "jd_analyzer": "jd_analyzer",
            "profile_extractor": "profile_extractor",
            "gap_analyzer": "gap_analyzer",
            "content_generator": "content_generator",
            "html_renderer": "html_renderer",
            "interview_qa": "interview_qa",
            "question": "question",
            "cover_letter": "cover_letter",
            "end": END,
        },
    )

    # Question → END（只读问答，不进入业务链路）
    graph.add_edge("question", END)

    # Cover Letter → END
    graph.add_edge("cover_letter", END)

    return graph.compile()
