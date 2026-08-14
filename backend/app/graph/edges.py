"""条件边 — 根据 GraphState 决定下一步走向。"""

from __future__ import annotations

import logging

from app.graph.reflection import reflect, MAX_ITERATIONS
from app.graph.state import GraphState

logger = logging.getLogger(__name__)

# === 用户消息关键词（用于检测用户直接粘贴的内容类型）===
_JD_KEYWORDS = ("职位", "岗位", "职责", "要求", "任职", "工作内容", "薪资", "招聘", "JD", "jd")
_RESUME_KEYWORDS = ("教育背景", "工作经历", "项目经历", "实习经历", "个人简历", "专业技能")


def _has_valid_data(data: dict | None) -> bool:
    """检查数据是否为有效的非空字典（排除错误状态）。"""
    if not data:
        return False
    if data.get("_error"):
        return False
    return bool(data)


def rule_based_route(state: GraphState) -> str:
    """规则引擎路由 — 替代 Planner LLM 调用。

    设计原则：
    1. 严格按照 Pipeline 顺序检查状态，不跳步
    2. 识别可并行的节点，返回并行路由
    3. 不猜测用户意图，只基于已有状态判断
    4. 用户消息内容仅在没有文件上传时作为 fallback
    """
    # === 状态提取 ===
    has_jd_text = bool(state.get("jd_text"))
    has_resume_text = bool(state.get("resume_text"))
    has_jd = _has_valid_data(state.get("jd_analysis"))
    has_profile = _has_valid_data(state.get("profile"))
    has_gap = _has_valid_data(state.get("gap_analysis"))
    has_content = _has_valid_data(state.get("resume_content"))
    has_render = _has_valid_data(state.get("render_config"))
    has_interview = _has_valid_data(state.get("interview_questions"))

    clarification_history = state.get("clarification_history", [])
    ready_to_proceed = state.get("ready_to_proceed", False)
    user_msg = state.get("user_message", "")

    # === 规则 1：多轮澄清中，且未完成 ===
    if clarification_history and not ready_to_proceed:
        logger.info("[Rule] 多轮澄清中，等待用户回复")
        return "clarifier"

    # === 规则 2：有文件待解析（优先级最高）===
    need_jd = has_jd_text and not has_jd
    need_profile = has_resume_text and not has_profile

    if need_jd and need_profile:
        # 两者都有待分析 → 并行处理
        logger.info("[Rule] JD 和简历都有待分析 → 并行处理")
        return "parallel_analysis"
    if need_jd:
        logger.info("[Rule] JD 待分析")
        return "jd_analyzer"
    if need_profile:
        logger.info("[Rule] 简历待提取")
        return "profile_extractor"

    # === 规则 3：用户消息可能包含 JD 或简历内容（无文件上传时的 fallback）===
    if user_msg and not has_jd and not has_profile and not has_jd_text and not has_resume_text:
        has_jd_kw = any(kw in user_msg for kw in _JD_KEYWORDS)
        has_resume_kw = any(kw in user_msg for kw in _RESUME_KEYWORDS)

        if has_jd_kw and has_resume_kw:
            logger.info("[Rule] 用户消息包含 JD 和简历关键词 → 并行处理")
            return "parallel_analysis"
        if has_jd_kw:
            logger.info("[Rule] 用户消息包含 JD 关键词")
            return "jd_analyzer"
        if has_resume_kw:
            logger.info("[Rule] 用户消息包含简历关键词")
            return "profile_extractor"

    # === 规则 4：JD 已分析但简历未提取（用户只上传了 JD）===
    if has_jd and not has_profile:
        # 检查用户消息是否可能是简历内容
        if user_msg and any(kw in user_msg for kw in _RESUME_KEYWORDS):
            logger.info("[Rule] 已有 JD，用户消息可能是简历")
            return "profile_extractor"
        # 需要澄清
        logger.info("[Rule] 已有 JD，需要简历")
        return "clarifier"

    # === 规则 5：简历已提取但 JD 未分析（用户只上传了简历）===
    if has_profile and not has_jd:
        # 检查用户消息是否可能是 JD 内容
        if user_msg and any(kw in user_msg for kw in _JD_KEYWORDS):
            logger.info("[Rule] 已有简历，用户消息可能是 JD")
            return "jd_analyzer"
        # 需要澄清
        logger.info("[Rule] 已有简历，需要 JD")
        return "clarifier"

    # === 规则 6：两者都有了，做差距分析 ===
    if has_jd and has_profile and not has_gap:
        logger.info("[Rule] JD 和简历都有了 → 差距分析")
        return "gap_analyzer"

    # === 规则 7：差距分析完成，生成简历内容 ===
    if has_gap and not has_content:
        logger.info("[Rule] 差距分析完成 → 生成简历内容")
        return "content_generator"

    # === 规则 8：简历内容生成完成，渲染和面试题可以并行 ===
    if has_content:
        need_render = not has_render
        need_interview = not has_interview
        if need_render and need_interview:
            logger.info("[Rule] 简历内容完成 → 并行渲染和生成面试题")
            return "parallel_render"
        if need_render:
            logger.info("[Rule] 简历内容完成 → 渲染 HTML")
            return "html_renderer"
        if need_interview:
            logger.info("[Rule] 渲染完成 → 生成面试题")
            return "interview_qa"

    # === 规则 9：所有数据都齐全，询问用户是否需要调整 ===
    if has_jd and has_profile and has_gap and has_content and has_render and has_interview:
        logger.info("[Rule] 所有数据齐全 → 澄清/完成")
        return "clarifier"

    # === 兜底：需要澄清 ===
    logger.info("[Rule] 兜底 → 澄清")
    return "clarifier"


def route_after_planner(state: GraphState) -> str:
    """Planner 之后的路由：根据规则引擎决策选择下一个节点。"""
    route = rule_based_route(state)
    logger.info(f"[Edge] Planner → {route}")

    route_map = {
        "jd_analyzer": "jd_analyzer",
        "profile_extractor": "profile_extractor",
        "gap_analyzer": "gap_analyzer",
        "content_generator": "content_generator",
        "html_renderer": "html_renderer",
        "interview_qa": "interview_qa",
        "clarifier": "clarifier",
        "parallel_analysis": "parallel_analysis",
        "parallel_render": "parallel_render",
    }
    return route_map.get(route, "clarifier")


def route_after_parallel_analysis(state: GraphState) -> str:
    """并行分析之后的路由：回到 Planner 重新决策。"""
    logger.info("[Edge] Parallel Analysis → Planner")
    return "planner"


def route_after_parallel_render(state: GraphState) -> str:
    """并行渲染之后的路由：结束。"""
    logger.info("[Edge] Parallel Render → END")
    return "end"


def route_after_reviewer(state: GraphState) -> str:
    """Reviewer 之后的路由：根据 Reflection 结果决定迭代或继续。

    - 评审通过（score >= 阈值）→ 进入 HTML 渲染
    - 评审不通过且未达最大迭代 → 回到 Content Generator 迭代
    - 达到最大迭代次数 → 强制进入 HTML 渲染
    """
    review = state.get("review_result", {})
    iteration = state.get("content_iterations", 0)

    result = reflect(review, iteration)

    if result.action == "iterate":
        logger.info(
            f"[Edge] Review score {result.score}, iteration {iteration}, "
            f"iterating: {result.reason}"
        )
        return "iterate"

    logger.info(f"[Edge] Review score {result.score}, proceeding: {result.reason}")
    return "proceed"


def route_after_clarifier(state: GraphState) -> str:
    """Clarifier 之后的路由。

    - ready_to_proceed=True → 用规则引擎重新决策
    - 否则 → END（等待用户回复）
    """
    if state.get("ready_to_proceed"):
        route = rule_based_route(state)
        logger.info(f"[Edge] Clarifier → proceed to {route}")
        route_map = {
            "jd_analyzer": "jd_analyzer",
            "profile_extractor": "profile_extractor",
            "gap_analyzer": "gap_analyzer",
            "content_generator": "content_generator",
            "parallel_analysis": "jd_analyzer",  # 并行降级为单个
        }
        return route_map.get(route, "jd_analyzer")

    logger.info("[Edge] Clarifier → END (waiting for user response)")
    return "end"
