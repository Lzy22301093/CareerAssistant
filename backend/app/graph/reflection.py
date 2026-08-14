"""Reflection Engine — 评审反馈 → 决策（通过 / 迭代）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 评审通过阈值
PASS_SCORE = 75

# 最大迭代次数
MAX_ITERATIONS = 3


@dataclass
class ReflectionResult:
    """反思结果。"""
    action: str  # "proceed" | "iterate"
    score: int
    suggestions: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    reason: str


def reflect(review: dict[str, Any], iteration: int = 0) -> ReflectionResult:
    """根据评审结果决定是否需要迭代。

    Args:
        review: ReviewerAgent 的输出，包含 score, suggestions, issues。
        iteration: 当前迭代次数（从 0 开始）。

    Returns:
        ReflectionResult，包含决策和改进建议。
    """
    score = review.get("score", 0)
    suggestions = review.get("suggestions", [])
    issues = review.get("issues", [])

    # 已达最大迭代次数，强制通过
    if iteration >= MAX_ITERATIONS:
        return ReflectionResult(
            action="proceed",
            score=score,
            suggestions=suggestions,
            issues=issues,
            reason=f"已达到最大迭代次数 {MAX_ITERATIONS}，强制通过",
        )

    # 评分达标，通过
    if score >= PASS_SCORE:
        return ReflectionResult(
            action="proceed",
            score=score,
            suggestions=suggestions,
            issues=issues,
            reason=f"评分 {score} 达到阈值 {PASS_SCORE}，质量合格",
        )

    # 评分不达标，需要迭代
    high_priority = [s for s in suggestions if s.get("priority") == "high"]
    high_issues = [i for i in issues if i.get("severity") == "high"]

    return ReflectionResult(
        action="iterate",
        score=score,
        suggestions=suggestions,
        issues=issues,
        reason=(
            f"评分 {score} 未达阈值 {PASS_SCORE}，"
            f"有 {len(high_priority)} 条高优先级建议，{len(high_issues)} 个高严重性问题"
        ),
    )


def build_reflection_prompt(review: dict[str, Any]) -> str:
    """从评审结果构建迭代改进提示词。

    将评审的 suggestions 和 issues 转换为给 ContentGenerator 的改进指令。
    """
    suggestions = review.get("suggestions", [])
    issues = review.get("issues", [])

    parts = ["请根据以下评审反馈改进简历内容：\n"]

    if issues:
        parts.append("需要修复的问题：")
        for i, issue in enumerate(issues, 1):
            severity = issue.get("severity", "medium")
            section = issue.get("section", "未指定")
            desc = issue.get("description", "")
            parts.append(f"  {i}. [{severity}] {section}：{desc}")
        parts.append("")

    if suggestions:
        parts.append("改进建议：")
        for i, sug in enumerate(suggestions, 1):
            priority = sug.get("priority", "medium")
            section = sug.get("section", "未指定")
            text = sug.get("suggestion", "")
            parts.append(f"  {i}. [{priority}] {section}：{text}")
        parts.append("")

    parts.append("请在生成的内容中体现以上改进，重点关注高优先级项。")
    return "\n".join(parts)
