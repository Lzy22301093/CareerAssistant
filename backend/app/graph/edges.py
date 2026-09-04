"""条件边 — 意图查表 + 状态截断路由（v4 简化架构）。

设计原则（对齐参考项目 ai-career-copilot）：
1. LLM 意图分类 + 简单查表字典（替代 200 行规则引擎）
2. 状态截断：没有简历数据时砍掉下游生成节点（防编造）
3. 线性流水线：planner → plan_advance → 下一个节点 → ... → END
"""

from __future__ import annotations

import logging

from app.graph.state import GraphState

logger = logging.getLogger(__name__)


# === 意图 → 执行计划查表 ===

INTENT_PLAN: dict[str, list[str]] = {
    "upload_jd":            ["jd_analyzer", "profile_extractor", "gap_analyzer", "content_generator", "html_renderer", "interview_qa"],
    "upload_profile":       ["profile_extractor", "content_generator", "html_renderer", "interview_qa"],
    "gap_analysis":         ["gap_analyzer"],
    "content_edit":         ["content_generator", "html_renderer"],
    "render_edit":          ["html_renderer"],
    "export":               [],
    "ask_question":         ["question"],
    "generate_cover_letter": ["cover_letter"],
    "record_interview":     ["clarifier"],  # 面试记录仍需多轮追问
    "interview_sim":        ["interview_sim"],
}


def build_execution_plan(intent: str, state: GraphState) -> list[str]:
    """根据意图 + 状态生成执行计划。参考项目 _build_execution_plan 的等价实现。

    核心：状态截断 — 没有简历时只跑解析，不跑生成/面试题。
    依赖检查只针对编辑类意图（上游数据应已存在），输入类意图由节点 guard 处理。
    """
    base = list(INTENT_PLAN.get(intent, []))

    # === 输入类意图：只检查原始输入（resume_text/jd_text），不检查上游产出 ===
    # upload_jd 但没有 JD 文本 → 空计划（无法分析）
    if intent == "upload_jd" and not state.get("jd_text"):
        logger.info("[Plan] upload_jd + 无 JD 文本 → 空计划")
        return []

    # upload_jd 但没有简历 → 只解析 JD（不生成 profile/resume_content/interview_questions）
    if intent == "upload_jd" and not state.get("resume_content_json") and not state.get("profile"):
        if not state.get("resume_text"):
            logger.info("[Plan] upload_jd + 无简历 → 截断为 [jd_analyzer]")
            return ["jd_analyzer"]

    # upload_profile 但没有简历文本 → 空计划
    if intent == "upload_profile" and not state.get("resume_text"):
        logger.info("[Plan] upload_profile + 无简历文本 → 空计划")
        return []

    # upload_profile 但没有 JD → 只提取画像
    if intent == "upload_profile" and not state.get("jd_analysis"):
        if not state.get("jd_text"):
            logger.info("[Plan] upload_profile + 无 JD → 截断为 [profile_extractor]")
            return ["profile_extractor"]

    # === 编辑类意图：上游数据应已存在，缺失则截断 ===
    if intent == "content_edit":
        if not state.get("resume_content"):
            logger.info("[Plan] content_edit 但无 resume_content → 空计划")
            return []
        if not state.get("profile") or not state.get("jd_analysis"):
            logger.info("[Plan] content_edit 依赖缺失 → 截断到 content_generator")
            return ["content_generator", "html_renderer"]

    if intent == "render_edit":
        if not state.get("resume_content"):
            logger.info("[Plan] render_edit 但无 resume_content → 空计划")
            return []

    if intent == "gap_analysis":
        if not state.get("jd_analysis") or not state.get("profile"):
            logger.info("[Plan] gap_analysis 但数据不足 → 空计划")
            return []

    return base


def advance_plan(state: GraphState) -> str:
    """从 execution_plan 取下一个节点执行。plan 空了就 END。"""
    plan = state.get("execution_plan", [])
    if plan:
        next_node = plan[0]
        logger.info(f"[Edge] advance_plan → {next_node} (剩余 {len(plan)} 步)")
        return next_node
    logger.info("[Edge] advance_plan → END (计划完成)")
    return "__end__"
