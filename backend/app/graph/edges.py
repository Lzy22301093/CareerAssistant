"""条件边 — 根据 GraphState 决定下一步走向。"""

from __future__ import annotations

import logging

from app.graph.reflection import reflect, MAX_ITERATIONS
from app.graph.state import GraphState

logger = logging.getLogger(__name__)

# === 用户消息关键词（用于检测用户直接粘贴的内容类型）===
_JD_KEYWORDS = ("职位", "岗位", "职责", "要求", "任职", "工作内容", "薪资", "招聘", "JD", "jd")
_RESUME_KEYWORDS = ("教育背景", "工作经历", "项目经历", "实习经历", "个人简历", "专业技能")


def _looks_like_jd(text: str) -> bool:
    """消息是否明显是 JD 内容。"""
    return bool(text) and any(kw in text for kw in _JD_KEYWORDS) and len(text) > 30


def _looks_like_resume(text: str) -> bool:
    """消息是否明显是简历内容。"""
    return bool(text) and any(kw in text for kw in _RESUME_KEYWORDS) and len(text) > 30


def _has_valid_data(data: dict | None) -> bool:
    """检查数据是否为有效的非空字典（排除错误状态）。"""
    if not data:
        return False
    if data.get("_error"):
        return False
    return bool(data)


def _version_aware_has(state: GraphState) -> tuple[bool, bool, bool, bool, bool, bool]:
    """版本感知的状态提取（增量编辑 v3）。

    - jd/profile：其分析基于的输入版本需等于当前输入版本，否则视为过期（输入已变）
    - gap/content/interview：其基于的 (jd, profile) 版本组合需等于当前组合
    - render_config 不依赖输入版本（模板/字号配置）
    - 旧会话（无版本字段）视为有效，避免兼容性问题触发全量重算
    """
    jiv = state.get("jd_input_version", 0)
    piv = state.get("profile_input_version", 0)

    def _matched(field: str, expected: int) -> bool:
        if field not in state:
            return True  # 旧数据无版本字段 → 视为有效
        return state[field] == expected

    has_jd = _has_valid_data(state.get("jd_analysis")) and _matched("jd_analyzed_version", jiv)
    has_profile = _has_valid_data(state.get("profile")) and _matched("profile_analyzed_version", piv)

    def _paired(base_jd: str, base_profile: str) -> bool:
        if base_jd not in state or base_profile not in state:
            return True
        return state[base_jd] == jiv and state[base_profile] == piv

    has_gap = (
        _has_valid_data(state.get("gap_analysis"))
        and _paired("gap_based_jd", "gap_based_profile")
    )
    has_content = (
        _has_valid_data(state.get("resume_content"))
        and _paired("content_based_jd", "content_based_profile")
    )
    has_interview = (
        _has_valid_data(state.get("interview_questions"))
        and _paired("interview_based_jd", "interview_based_profile")
    )
    has_render = _has_valid_data(state.get("render_config"))
    return has_jd, has_profile, has_gap, has_content, has_render, has_interview


def rule_based_route(state: GraphState) -> str:
    """路由决策（v3）— 意图优先 + 状态/版本兜底。

    设计原则：
    1. LLM 意图分类优先（ask_question / generate_cover_letter / export /
       gap_analysis / content_edit / render_edit 走专用路由）
    2. upload_jd / upload_profile / fallback 走状态推进（版本感知，支持换岗位/补经历）
    3. 严格版本检测：输入变化 → 下游产物过期 → 级联重算
    4. 用户消息内容仅在没有文件上传时作为 fallback
    """
    intent = state.get("intent") or "fallback"

    has_jd_text = bool(state.get("jd_text"))
    has_resume_text = bool(state.get("resume_text"))
    has_jd, has_profile, has_gap, has_content, has_render, has_interview = _version_aware_has(state)

    clarification_history = state.get("clarification_history", [])
    ready_to_proceed = state.get("ready_to_proceed", False)
    user_msg = state.get("user_message", "")

    # === 规则 1：多轮澄清中，且未完成 ===
    # 但若用户新消息是明确的 JD/简历（意图识别或关键词），视为新输入放行，
    # 否则会无限卡在澄清里（用户发 JD 被当澄清回答 → 流程乱，历史回归点）。
    if clarification_history and not ready_to_proceed:
        if intent in ("upload_jd", "upload_profile"):
            logger.info("[Rule] 澄清中但新消息是 JD/简历 → 放行处理")
        elif _looks_like_jd(user_msg) or _looks_like_resume(user_msg):
            logger.info("[Rule] 澄清中但消息含 JD/简历内容 → 放行处理")
        else:
            logger.info("[Rule] 多轮澄清中，等待用户回复")
            return "clarifier"

    # === 规则 2（前置）：文件/输入待处理（版本感知）优先级最高 ===
    # 防止意图误判（如把上传简历后的消息判成 ask_question）短路输入处理，
    # 导致简历/JD 不被提取、下游基于空数据胡编（历史回归点）。
    need_jd = has_jd_text and not has_jd
    need_profile = has_resume_text and not has_profile

    if need_jd and need_profile:
        logger.info("[Rule] JD 和简历都有待分析 → 并行处理")
        return "parallel_analysis"
    if need_jd:
        logger.info("[Rule] JD 待分析")
        return "jd_analyzer"
    if need_profile:
        logger.info("[Rule] 简历待提取")
        return "profile_extractor"

    # === 意图专用路由（v3）—— 仅在没有待处理输入时生效 ===
    if intent == "ask_question":
        logger.info("[Rule] 意图=ask_question → 自由问答")
        return "question"
    if intent == "generate_cover_letter":
        if not state.get("cover_letter_channel"):
            logger.info("[Rule] 意图=generate_cover_letter，渠道未选 → 澄清")
            return "clarifier"
        logger.info("[Rule] 意图=generate_cover_letter → 生成求职信")
        return "cover_letter"
    if intent == "record_interview":
        if state.get("ready_to_proceed"):
            logger.info("[Rule] 意图=record_interview 信息已收集 → 结束")
            return "end"
        logger.info("[Rule] 意图=record_interview → 面试记录追问")
        return "clarifier"
    if intent == "export":
        logger.info("[Rule] 意图=export → 对话结束（导出走独立 API）")
        return "end"
    if intent == "gap_analysis":
        if has_jd and has_profile:
            logger.info("[Rule] 意图=gap_analysis → 差距分析")
            return "gap_analyzer"
        logger.info("[Rule] 意图=gap_analysis 但数据不足 → 澄清")
        return "clarifier"
    if intent == "render_edit":
        if has_content:
            logger.info("[Rule] 意图=render_edit → 渲染配置")
            return "html_renderer"
        logger.info("[Rule] 意图=render_edit 但无简历内容 → 澄清")
        return "clarifier"
    if intent == "content_edit":
        if has_jd and has_profile:
            logger.info("[Rule] 意图=content_edit → 重新生成简历内容")
            return "content_generator"
        logger.info("[Rule] 意图=content_edit 但数据不足 → 澄清")
        return "clarifier"

    # === 状态推进（版本感知）===
    need_jd = has_jd_text and not has_jd
    need_profile = has_resume_text and not has_profile

    if need_jd and need_profile:
        logger.info("[Rule] JD 和简历都有待分析 → 并行处理")
        return "parallel_analysis"
    if need_jd:
        logger.info("[Rule] JD 待分析")
        return "jd_analyzer"
    if need_profile:
        logger.info("[Rule] 简历待提取")
        return "profile_extractor"

    # 规则 3：用户消息可能包含 JD 或简历内容（无文件上传时的 fallback）
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

    # 规则 4：JD 已分析但简历未提取
    if has_jd and not has_profile:
        if user_msg and any(kw in user_msg for kw in _RESUME_KEYWORDS):
            logger.info("[Rule] 已有 JD，用户消息可能是简历")
            return "profile_extractor"
        logger.info("[Rule] 已有 JD，需要简历")
        return "clarifier"

    # 规则 5：简历已提取但 JD 未分析
    if has_profile and not has_jd:
        if user_msg and any(kw in user_msg for kw in _JD_KEYWORDS):
            logger.info("[Rule] 已有简历，用户消息可能是 JD")
            return "jd_analyzer"
        logger.info("[Rule] 已有简历，需要 JD")
        return "clarifier"

    # 规则 6：两者都有了，做差距分析（版本过期会自然触发重算）
    if has_jd and has_profile and not has_gap:
        logger.info("[Rule] JD 和简历都有了 → 差距分析")
        return "gap_analyzer"

    # 规则 7：差距分析完成，生成简历内容
    if has_gap and not has_content:
        logger.info("[Rule] 差距分析完成 → 生成简历内容")
        return "content_generator"

    # 规则 8：简历内容完成 → 渲染（面试题在 parallel_post 阶段并行生成）
    if has_content:
        need_render = not has_render
        need_interview = not has_interview
        if need_render:
            logger.info("[Rule] 简历内容完成 → 渲染 HTML")
            return "html_renderer"
        if need_interview:
            logger.info("[Rule] 渲染完成 → 补生成面试题")
            return "interview_qa"

    # 规则 9：所有数据都齐全，询问用户是否需要调整
    if has_jd and has_profile and has_gap and has_content and has_render and has_interview:
        logger.info("[Rule] 所有数据齐全 → 澄清/完成")
        return "clarifier"

    # 兜底：需要澄清
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
        "question": "question",
        "cover_letter": "cover_letter",
        "end": "end",
    }
    return route_map.get(route, "clarifier")


def route_after_parallel_analysis(state: GraphState) -> str:
    """并行分析之后的路由：回到 Planner 重新决策。"""
    logger.info("[Edge] Parallel Analysis → Planner")
    return "planner"


def route_after_parallel_post(state: GraphState) -> str:
    """parallel_post 之后的路由：评审通过 → HTML 渲染；不通过 → 回到内容生成迭代。"""
    review = state.get("review_result", {})
    iteration = state.get("content_iterations", 0)

    result = reflect(review, iteration)

    if result.action == "iterate":
        logger.info(
            f"[Edge] Post-review score {result.score}, iteration {iteration}, "
            f"iterating: {result.reason}"
        )
        return "iterate"

    logger.info(f"[Edge] Post-review score {result.score}, proceeding: {result.reason}")
    return "proceed"


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


def route_after_interview_review(state: GraphState) -> str:
    """Interview Reviewer 之后的路由：根据 Reflection 结果决定迭代或结束。

    - 评审通过（score >= 阈值）→ END
    - 评审不通过且未达最大迭代 → 回到 Interview Q&A 迭代
    - 达到最大迭代次数 → 强制结束
    """
    review = state.get("interview_review_result", {})
    iteration = state.get("interview_iterations", 0)

    result = reflect(review, iteration)

    if result.action == "iterate":
        logger.info(
            f"[Edge] Interview review score {result.score}, iteration {iteration}, "
            f"iterating: {result.reason}"
        )
        return "iterate"

    logger.info(f"[Edge] Interview review score {result.score}, proceeding: {result.reason}")
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
            "html_renderer": "html_renderer",
            "interview_qa": "interview_qa",
            "clarifier": "clarifier",
            "parallel_analysis": "jd_analyzer",  # 并行降级为单个
            "question": "question",
            "cover_letter": "cover_letter",
            "end": "end",
        }
        return route_map.get(route, "jd_analyzer")

    logger.info("[Edge] Clarifier → END (waiting for user response)")
    return "end"
