"""Reflection Engine 单元测试。"""

from __future__ import annotations

import pytest

from app.graph.reflection import (
    PASS_SCORE,
    MAX_ITERATIONS,
    ReflectionResult,
    reflect,
    build_reflection_prompt,
)


# === reflect() 测试 ===


class TestReflect:
    def test_high_score_proceed(self):
        """高分通过。"""
        review = {"score": 85, "suggestions": [], "issues": []}
        result = reflect(review, iteration=0)
        assert result.action == "proceed"
        assert result.score == 85
        assert "达到阈值" in result.reason

    def test_exact_threshold_proceed(self):
        """刚好达到阈值通过。"""
        review = {"score": PASS_SCORE, "suggestions": [], "issues": []}
        result = reflect(review, iteration=0)
        assert result.action == "proceed"

    def test_low_score_iterate(self):
        """低分迭代。"""
        review = {
            "score": 60,
            "suggestions": [{"priority": "high", "suggestion": "添加量化数据"}],
            "issues": [{"severity": "high", "description": "缺少关键信息"}],
        }
        result = reflect(review, iteration=0)
        assert result.action == "iterate"
        assert result.score == 60
        assert len(result.suggestions) == 1

    def test_max_iterations_force_proceed(self):
        """达到最大迭代次数强制通过。"""
        review = {"score": 30, "suggestions": [], "issues": []}
        result = reflect(review, iteration=MAX_ITERATIONS)
        assert result.action == "proceed"
        assert "最大迭代次数" in result.reason

    def test_iteration_below_max(self):
        """未达最大迭代次数，低分应继续迭代。"""
        review = {"score": 50, "suggestions": [], "issues": []}
        result = reflect(review, iteration=MAX_ITERATIONS - 1)
        assert result.action == "iterate"

    def test_missing_score_defaults_zero(self):
        """缺少 score 字段默认为 0。"""
        review = {"suggestions": [], "issues": []}
        result = reflect(review, iteration=0)
        assert result.score == 0
        assert result.action == "iterate"

    def test_preserves_all_data(self):
        """结果保留所有评审数据。"""
        review = {
            "score": 70,
            "suggestions": [{"priority": "low", "suggestion": "格式调整"}],
            "issues": [{"severity": "low", "description": "拼写错误"}],
        }
        result = reflect(review, iteration=0)
        assert result.suggestions == review["suggestions"]
        assert result.issues == review["issues"]


# === build_reflection_prompt() 测试 ===


class TestBuildReflectionPrompt:
    def test_with_issues_and_suggestions(self):
        """包含问题和建议的提示词。"""
        review = {
            "score": 60,
            "issues": [
                {"severity": "high", "section": "工作经历", "description": "缺少量化数据"},
                {"severity": "medium", "section": "技能", "description": "关键词不足"},
            ],
            "suggestions": [
                {"priority": "high", "section": "工作经历", "suggestion": "添加百分比数据"},
                {"priority": "low", "section": "格式", "suggestion": "统一日期格式"},
            ],
        }
        prompt = build_reflection_prompt(review)
        assert "工作经历" in prompt
        assert "high" in prompt
        assert "添加百分比数据" in prompt
        assert "需要修复的问题" in prompt
        assert "改进建议" in prompt

    def test_empty_review(self):
        """空评审生成基础提示。"""
        review = {"score": 50, "suggestions": [], "issues": []}
        prompt = build_reflection_prompt(review)
        assert "评审反馈" in prompt
        assert "高优先级" in prompt

    def test_only_suggestions(self):
        """只有建议没有问题。"""
        review = {
            "score": 65,
            "suggestions": [{"priority": "medium", "section": "教育", "suggestion": "补充 GPA"}],
            "issues": [],
        }
        prompt = build_reflection_prompt(review)
        assert "改进建议" in prompt
        assert "需要修复" not in prompt


# === ReflectionResult 数据类 ===


class TestReflectionResult:
    def test_dataclass_fields(self):
        result = ReflectionResult(
            action="proceed",
            score=80,
            suggestions=[],
            issues=[],
            reason="good",
        )
        assert result.action == "proceed"
        assert result.score == 80
        assert result.reason == "good"
