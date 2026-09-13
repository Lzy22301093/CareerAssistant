"""Interview Graph 节点实现。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.interview.state import InterviewState

logger = logging.getLogger(__name__)


async def open_interview_node(
    state: InterviewState, agents: dict[str, Any]
) -> dict[str, Any]:
    """生成面试开场白，初始化面试状态。"""
    from app.interview.context import (
        extract_resume_topics,
        format_profile_supplement,
        format_resume_for_prompt,
    )

    jd = state.get("jd_analysis", {})
    profile = state.get("profile", {})
    resume = state.get("resume") or {}
    target = state.get("target_position", jd.get("job_title", "该岗位"))

    # 从 JD + 简历提取待考察话题（简历为主补充项目名）
    pending_topics = _extract_topics(jd)
    for t in extract_resume_topics(resume):
        if t not in pending_topics:
            pending_topics.append(t)
    pending_topics = pending_topics[:15]

    dimension_scores = {
        "专业知识": 0.0,
        "问题分析": 0.0,
        "沟通表达": 0.0,
        "实践经验": 0.0,
        "学习能力": 0.0,
    }

    company = jd.get("company", "我们公司")
    opening = f"你好，我是{company}的面试官，今天面试{target}这个岗位。我们开始吧。"

    interviewer = agents.get("interviewer")
    if interviewer:
        result = await interviewer.run(
            target_position=target,
            difficulty_level=state.get("difficulty_level", "medium"),
            decision={"next_action": "切换话题", "reason": "面试开始"},
            pending_topics=pending_topics,
            covered_topics=[],
            referenced_questions=state.get("referenced_questions", []),
            resume_text=format_resume_for_prompt(resume),
            profile_supplement=format_profile_supplement(profile),
            jd_summary=str(jd.get("summary") or jd.get("job_title") or ""),
        )
        first_question = result.get("question", "请介绍一下你自己。")
        first_category = result.get("category", "behavioral")
    else:
        first_question = "请介绍一下你自己。"
        first_category = "behavioral"

    full_response = f"{opening}\n\n{first_question}"

    return {
        "phase": "opening",
        "current_question": full_response,
        "current_question_category": first_category,
        "pending_topics": pending_topics,
        "dimension_scores": dimension_scores,
        "is_active": True,
        "turn_count": 0,
        "conversation_history": [
            {"role": "assistant", "content": full_response, "timestamp": _now()},
        ],
    }


async def evaluate_node(
    state: InterviewState, agents: dict[str, Any]
) -> dict[str, Any]:
    """Evaluator 评价用户回答。"""
    evaluator = agents.get("evaluator")
    if not evaluator:
        logger.error("[evaluate] evaluator agent not found")
        return {"current_evaluation": {"score": 0, "next_action": "结束面试"}}

    result = await evaluator.run(
        current_question=state.get("current_question", ""),
        current_answer=state.get("current_answer", ""),
        difficulty_level=state.get("difficulty_level", "medium"),
        turn_count=state.get("turn_count", 0),
        max_turns=state.get("max_turns", 10),
        covered_topics=state.get("covered_topics", []),
        pending_topics=state.get("pending_topics", []),
        dimension_scores=state.get("dimension_scores", {}),
        conversation_history=state.get("conversation_history", []),
        referenced_questions=state.get("referenced_questions", []),
        resume_text=_resume_brief(state),
        target_position=state.get("target_position", ""),
    )

    # 更新维度评分（加权平均）
    old_scores = state.get("dimension_scores", {})
    new_dim_scores = result.get("dimension_scores", {})
    turn = state.get("turn_count", 0)
    updated_scores = {}
    all_dims = set(old_scores) | set(new_dim_scores)
    for dim in all_dims:
        old = old_scores.get(dim, 0)
        new = new_dim_scores.get(dim, 0)
        if turn > 0:
            updated_scores[dim] = round(old * 0.7 + new * 0.3, 1)
        else:
            updated_scores[dim] = new

    # 累积优势和薄弱点
    strengths = state.get("strengths", []) + result.get("strengths", [])
    weaknesses = state.get("weaknesses", []) + result.get("weaknesses", [])

    # 更新已覆盖话题
    covered = state.get("covered_topics", [])
    current_q = state.get("current_question", "")
    if current_q and current_q not in covered:
        covered = covered + [current_q]

    # 从 pending 中移除已覆盖的
    pending = state.get("pending_topics", [])
    next_topic = result.get("next_topic")
    if next_topic and next_topic in pending:
        pending = [t for t in pending if t != next_topic]

    return {
        "current_evaluation": result,
        "dimension_scores": updated_scores,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "next_action": result.get("next_action", "切换话题"),
        "covered_topics": covered,
        "pending_topics": pending,
        "turn_count": turn + 1,
        "conversation_history": _append_history(
            state.get("conversation_history", []),
            {"role": "user", "content": state.get("current_answer", ""), "timestamp": _now()},
        ),
        "interrupt_checkpoint": "evaluate",
    }


async def ask_question_node(
    state: InterviewState, agents: dict[str, Any]
) -> dict[str, Any]:
    """Interviewer 根据 Evaluator 决策生成问题。"""
    from app.interview.context import format_profile_supplement, format_resume_for_prompt

    interviewer = agents.get("interviewer")
    if not interviewer:
        logger.error("[ask_question] interviewer agent not found")
        return {"current_question": "请继续。"}

    evaluation = state.get("current_evaluation", {})

    result = await interviewer.run(
        target_position=state.get("target_position", ""),
        difficulty_level=state.get("difficulty_level", "medium"),
        decision=evaluation,
        pending_topics=state.get("pending_topics", []),
        covered_topics=state.get("covered_topics", []),
        referenced_questions=state.get("referenced_questions", []),
        current_question=state.get("current_question", ""),
        current_answer=state.get("current_answer", ""),
        resume_text=format_resume_for_prompt(state.get("resume")),
        profile_supplement=format_profile_supplement(state.get("profile")),
        jd_summary=str((state.get("jd_analysis") or {}).get("summary") or ""),
    )

    question = result.get("question", "请继续。")
    category = result.get("category", "technical")

    # 更新难度（如果 Evaluator 决定调整）
    new_difficulty = evaluation.get("new_difficulty")
    updates: dict[str, Any] = {
        "current_question": question,
        "current_question_category": category,
        "phase": "core_probing",
        "conversation_history": _append_history(
            state.get("conversation_history", []),
            {"role": "assistant", "content": question, "timestamp": _now()},
        ),
        "interrupt_checkpoint": "ask_question",
    }
    if new_difficulty and new_difficulty != state.get("difficulty_level"):
        updates["difficulty_level"] = new_difficulty

    return updates


async def adjust_difficulty_node(
    state: InterviewState, agents: dict[str, Any]
) -> dict[str, Any]:
    """调整面试难度（纯状态更新，不调 LLM）。"""
    evaluation = state.get("current_evaluation", {})
    new_difficulty = evaluation.get("new_difficulty", state.get("difficulty_level", "medium"))
    return {
        "difficulty_level": new_difficulty,
    }


async def finish_node(
    state: InterviewState, agents: dict[str, Any]
) -> dict[str, Any]:
    """标记面试结束。"""
    turn = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 10)
    pending = state.get("pending_topics", [])

    if turn >= max_turns:
        reason = "max_turns"
    elif not pending:
        reason = "all_topics_covered"
    else:
        reason = "evaluator_ended"

    return {
        "is_active": False,
        "is_complete": True,
        "completion_reason": reason,
    }


async def generate_report_node(
    state: InterviewState, agents: dict[str, Any]
) -> dict[str, Any]:
    """生成完整评价报告。"""
    evaluator = agents.get("evaluator")
    if not evaluator:
        return {"final_report": {"error": "evaluator not available"}}

    # 用 LLM 生成报告摘要（直接调用，不走 evaluator.build_messages 的评分 prompt）
    from app.llm import Message, Role
    from app.llm.retry import with_retry

    history_summary = _summarize_history(state.get("conversation_history", []))

    report_prompt = (
        f"请根据以下面试记录生成一份简洁的评价报告。\n\n"
        f"目标岗位：{state.get('target_position', '')}\n"
        f"面试轮数：{state.get('turn_count', 0)}\n"
        f"维度评分：{json.dumps(state.get('dimension_scores', {}), ensure_ascii=False)}\n"
        f"优势：{json.dumps(state.get('strengths', []), ensure_ascii=False)}\n"
        f"薄弱点：{json.dumps(state.get('weaknesses', []), ensure_ascii=False)}\n"
        f"结束原因：{state.get('completion_reason', '')}\n\n"
        f"对话摘要：\n{history_summary}\n\n"
        f"请输出 JSON：\n"
        f'{{"overall_score": 7.5, "summary": "总体评价（2-3句话）", "suggestions": ["建议1", "建议2"]}}'
    )

    try:
        async def _call_llm():
            return await evaluator.llm.generate(report_prompt, temperature=0.3, max_tokens=1024)
        response = await with_retry(_call_llm)
        report = evaluator.extract_json(response) or {}
    except Exception as e:
        logger.error(f"[generate_report] LLM call failed: {e}")
        report = {}

    final_report = {
        "overall_score": report.get("overall_score", state.get("dimension_scores", {}).values() and sum(state["dimension_scores"].values()) / len(state["dimension_scores"]) or 0),
        "summary": report.get("summary", ""),
        "suggestions": report.get("suggestions", []),
        "dimension_scores": state.get("dimension_scores", {}),
        "strengths": state.get("strengths", []),
        "weaknesses": state.get("weaknesses", []),
        "turn_count": state.get("turn_count", 0),
        "completion_reason": state.get("completion_reason", ""),
        "target_position": state.get("target_position", ""),
    }

    return {
        "final_report": final_report,
        "phase": "closing",
    }


# --- 辅助函数 ---

def _resume_brief(state: InterviewState) -> str:
    from app.interview.context import format_resume_for_prompt

    return format_resume_for_prompt(state.get("resume"))


def _append_history(history: list[dict] | None, entry: dict) -> list[dict]:
    """追加一条对话历史，避免整段替换导致上下文丢失。"""
    base = list(history or [])
    base.append(entry)
    # 防止异常场景下历史无限膨胀
    return base[-80:]


def _extract_topics(jd: dict) -> list[str]:
    """从 JD 分析结果提取待考察话题。"""
    topics = []
    requirements = jd.get("requirements", [])
    for req in requirements:
        if isinstance(req, dict):
            content = req.get("content", "")
        else:
            content = str(req)
        if content:
            topics.append(content)
    # 限制数量，避免话题过多
    return topics[:15]


def _summarize_history(history: list[dict]) -> str:
    """将对话历史压缩为摘要。"""
    lines = []
    for h in history[-20:]:  # 最多取最近 20 条
        role = h.get("role", "")
        content = h.get("content", "")
        if content:
            prefix = "面试官" if role == "assistant" else "候选人"
            lines.append(f"{prefix}：{content[:100]}")
    return "\n".join(lines)


def _now() -> str:
    return datetime.now().isoformat()
