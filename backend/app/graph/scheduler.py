"""Scheduler（Track B / B2）— 按 Plan 动态构建子图并执行。

plan_executor_node 是注册在固定图中的一个节点，职责：
1. build_plan 构建裁剪后的任务计划（模板 + 版本裁剪，见 plan.py）
2. 按 Plan 的 depends_on 运行时组装 LangGraph 子图（无依赖任务自动并行），
   复用固定图的业务节点函数，行为等价
3. 质量反思：内容评审 join →（iterate 回 generate_content | proceed → render）；
   面试题评审 →（iterate 回面试题重生成 | END），语义与固定图一致
4. 返回增量 state 更新（含计划 trace 与 execution_plan 展示）

等价性保障：
- skipped 任务保留在图中作 no-op（trace 可见"跳过:输入未变"）
- generate_interview 带"已有效则跳过"守卫（镜像 parallel_post 的补生成判断）
- 面试题反思迭代走独立的 interview_revise 入口（无守卫，带反馈重生成），
  镜像固定图 interview_qa 节点的两条入边（planner 直达 / 评审迭代）
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph import plan as plan_mod
from app.graph.nodes import (
    content_generator_node,
    gap_analyzer_node,
    html_renderer_node,
    interview_qa_node,
    interview_reviewer_node,
    jd_analyzer_node,
    profile_extractor_node,
    reviewer_node,
)
from app.graph.reflection import reflect
from app.graph.state import GraphState
from app.graph.trace import trace_item

logger = logging.getLogger(__name__)

# 任务类型 → 业务节点函数（复用固定图实现）
TASK_NODE_FNS = {
    "analyze_jd": jd_analyzer_node,
    "extract_profile": profile_extractor_node,
    "gap_analysis": gap_analyzer_node,
    "generate_content": content_generator_node,
    "review_content": reviewer_node,
    "generate_interview": interview_qa_node,
    "render_html": html_renderer_node,
    "review_interview": interview_reviewer_node,
}

# 隐藏 join/修订节点 id（不与业务任务冲突）
_REFLECT_JOIN = "__reflect_content"
_INTERVIEW_REVISE = "interview_revise"


def _valid(data: Any) -> bool:
    if not isinstance(data, dict):
        return bool(data)
    if data.get("_error"):
        return False
    return bool(data)


async def plan_executor_node(state: GraphState, agents: dict) -> dict:
    """Plan 执行器节点：构建计划 → 动态子图执行 → 增量更新。"""
    built = plan_mod.build_plan(state)
    if built is None:
        # 第 4 层兜底：无法构建计划 → 交回规则路由（澄清）
        logger.warning("[PlanExecutor] 无法构建任务计划，回退澄清")
        return {
            "route": "clarifier",
            "route_reason": "无法构建任务计划",
            "workflow_trace": [trace_item(
                "plan_executor", "skipped",
                output_summary="计划构建失败，回退规则路由",
            )],
        }

    plan = built
    trace = [trace_item(
        "plan_executor", "success",
        input_summary=f"intent={plan.intent}, source={plan.source}",
        output_summary=(
            f"执行 {[t.type for t in plan.tasks if t.status == plan_mod.TASK_PENDING]}"
            if plan.executable() else "全部任务新鲜，无可执行任务"
        ),
        artifacts={"plan": plan.to_display(), "post_route": plan.post_route},
    )]

    if not plan.executable():
        return {
            "route": plan.post_route,
            "route_reason": "全部产物新鲜，无需重算",
            "execution_plan": [t.type for t in plan.tasks],
            "workflow_trace": trace,
        }

    # 动态子图执行
    subgraph = _build_dynamic_graph(plan, agents)
    initial_trace_len = len(state.get("workflow_trace") or [])
    final = await subgraph.ainvoke(state)

    # 提取增量：值变化字段 + workflow_trace 增量（避免 operator.add 重复累计）
    updates: dict[str, Any] = {
        k: v for k, v in final.items()
        if k != "workflow_trace" and state.get(k) != v
    }
    new_trace = (final.get("workflow_trace") or [])[initial_trace_len:]
    updates["route"] = plan.post_route
    updates["route_reason"] = f"计划执行完成（{len(plan.executed_types)} 个任务）"
    updates["execution_plan"] = [t.type for t in plan.tasks]
    updates["workflow_trace"] = trace + new_trace
    return updates


def _build_dynamic_graph(plan: plan_mod.Plan, agents: dict):
    """按 Plan 组装 LangGraph 子图：depends_on 决定边，质量反思用条件边。"""
    g = StateGraph(GraphState)
    executed_types = plan.executed_types

    for task in plan.tasks:
        g.add_node(task.id, _make_task_node(task, agents))

    # 依赖边：START → 无依赖任务；dep → task
    # render 的两条入边（review/interview）改走 reflect join，跳过直连
    for task in plan.tasks:
        if not task.depends_on:
            g.add_edge(START, task.id)
        for dep in task.depends_on:
            if task.id == "render_html" and dep in ("review_content", "generate_interview"):
                continue  # 由 reflect join 承接
            g.add_edge(dep, task.id)

    full_pipeline = any(t.id == "render_html" for t in plan.tasks)

    if full_pipeline:
        # 内容质量反思：review + interview 汇合 → reflect → iterate/proceed
        g.add_node(_REFLECT_JOIN, _noop_node(_REFLECT_JOIN))
        g.add_edge("review_content", _REFLECT_JOIN)
        g.add_edge("generate_interview", _REFLECT_JOIN)
        g.add_conditional_edges(
            _REFLECT_JOIN,
            _route_after_content_review(executed_types),
            {"iterate": "generate_content", "proceed": "render_html"},
        )

        # 面试题质量反思：ireview → iterate（带反馈重生成）/ END
        if "generate_interview" in executed_types:
            g.add_node(
                _INTERVIEW_REVISE,
                _make_bare_node("interview_qa", interview_qa_node, agents),
            )
            g.add_edge(_INTERVIEW_REVISE, "review_interview")
            iterate_target = _INTERVIEW_REVISE
        else:
            iterate_target = END  # 面试题未重生成时迭代无意义，直接放行
        g.add_conditional_edges(
            "review_interview",
            _route_after_interview_review(executed_types),
            {"iterate": iterate_target, "proceed": END},
        )
    else:
        # 部分计划（单边提取）：单任务直通 END，post_route 已由 build_plan 决定
        g.add_edge(plan.tasks[-1].id, END)

    return g.compile()


def _noop_node(node_name: str):
    async def _noop(state: GraphState) -> dict:
        return {}
    return _noop


def _make_task_node(task: plan_mod.Task, agents: dict):
    """任务节点包装：skipped → no-op + trace；generate_interview 带复跑守卫。"""
    node_fn = TASK_NODE_FNS[task.type]

    async def _run(state: GraphState) -> dict:
        if task.status == plan_mod.TASK_SKIPPED:
            return {"workflow_trace": [trace_item(
                plan_mod.TASK_NODE_NAME[task.type], "skipped",
                output_summary=f"跳过：{task.skip_reason}",
            )]}
        if (
            task.type == "generate_interview"
            and _valid(state.get("interview_questions"))
        ):
            # 复跑守卫：内容迭代重入时产物已有效 → 镜像 parallel_post 的补生成判断
            return {"workflow_trace": [trace_item(
                "interview_qa", "skipped",
                output_summary="跳过：面试题已存在（复跑保护）",
            )]}
        return await node_fn(state, agents)

    return _run


def _make_bare_node(node_name: str, node_fn, agents: dict):
    """无条件执行的业务节点（面试题修订入口，带反馈重生成）。"""
    async def _run(state: GraphState) -> dict:
        return await node_fn(state, agents)
    return _run


def _route_after_content_review(executed_types: set[str]):
    def _route(state: GraphState) -> str:
        if "generate_content" not in executed_types:
            return "proceed"  # 内容未重生成时无迭代意义（render_edit 等场景）
        result = reflect(state.get("review_result", {}), state.get("content_iterations", 0))
        return result.action
    return _route


def _route_after_interview_review(executed_types: set[str]):
    def _route(state: GraphState) -> str:
        if "generate_interview" not in executed_types:
            return "proceed"
        result = reflect(
            state.get("interview_review_result", {}),
            state.get("interview_iterations", 0),
        )
        return result.action
    return _route


# === 影子对比（4.5 S1）===


def shadow_compare(state: GraphState) -> None:
    """影子期对比：Plan 展开的能力集合 vs 旧路由逐步模拟。

    只告警不切换。已知刻意差异（换 JD 后面试题版本感知重生成）会如期出现，
    其余不一致说明裁剪语义与规则引擎出现漂移，需要人工介入。
    """
    try:
        built = plan_mod.build_plan(state)
        if built is None:
            return
        legacy_seq = plan_mod.simulate_legacy_sequence(state)
        legacy_caps = plan_mod._business_capability_set(legacy_seq, state)
        plan_caps = plan_mod.plan_capability_set(built)
        if legacy_caps != plan_caps:
            logger.warning(
                f"[Shadow] 路由能力集合不一致 legacy={sorted(legacy_caps)} "
                f"plan={sorted(plan_caps)}"
            )
    except Exception as e:  # 影子对比不允许影响主流程
        logger.warning(f"[Shadow] 对比失败: {e}")
