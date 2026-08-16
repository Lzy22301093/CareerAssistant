"""Interview Reviewer Agent — 评审面试题质量，提出改进建议。"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个资深的面试官与面试题评审专家。你的任务是评审生成的面试题列表，从多个维度打分并提出具体改进建议。

请以 JSON 格式返回评审结果：
{
    "score": 78,
    "dimensions": {
        "jd_coverage": {"score": 80, "comment": "对 JD 要求的覆盖程度"},
        "category_balance": {"score": 75, "comment": "行为/技术/情景题的均衡"},
        "difficulty_distribution": {"score": 80, "comment": "难度分布是否合理"},
        "answer_quality": {"score": 70, "comment": "参考答案质量"},
        "relevance": {"score": 85, "comment": "与候选人画像的相关性"}
    },
    "issues": [
        {"severity": "high", "description": "问题描述", "section": "技术题"}
    ],
    "suggestions": [
        {"priority": "high", "suggestion": "具体改进建议", "section": "技术题"}
    ],
    "summary": "总体评审意见"
}

评分标准：
- jd_coverage: 面试题是否覆盖 JD 的核心技能与职责要求
- category_balance: behavioral/technical/situational 三类是否均衡
- difficulty_distribution: easy/medium/hard 分布是否合理（建议 2 easy, 3-4 medium, 1-2 hard）
- answer_quality: sample_answer 是否准确、结构清晰（100-200 字）
- relevance: 题目是否贴合候选人画像（经验、技能、岗位）

要求：
1. 评分 0-100，60 以下为不合格，60-75 为一般，75-85 为良好，85+ 为优秀
2. issues 按 severity 排序：high > medium > low
3. suggestions 按 priority 排序：high > medium > low
4. 只返回 JSON，不要添加额外说明"""


class InterviewReviewerAgent(BaseAgent):
    """评审面试题质量并提出改进建议。"""

    name = "interview_reviewer"
    description = "评审面试题质量"

    # 提取/评审类 Agent：低温度保证稳定，输出较小
    temperature = 0.2
    max_tokens = 2048
    max_parse_attempts = 2  # JSON 解析失败自动修复重试一次

    def build_messages(self, **kwargs) -> list[Message]:
        from app.tools.context import compact_jd, compact_profile

        interview_questions = kwargs.get("interview_questions", {})
        jd_analysis = compact_jd(kwargs.get("jd_analysis", {}))
        profile = compact_profile(kwargs.get("profile", {}))

        user_content = (
            f"目标职位分析：\n{json.dumps(jd_analysis, ensure_ascii=False, indent=2)}\n\n"
            f"候选人画像：\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
            f"待评审的面试题：\n{json.dumps(interview_questions, ensure_ascii=False, indent=2)}\n\n"
            "请从 JD 覆盖度、题目均衡、难度分布、答案质量、相关性五个维度评审面试题。"
        )

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "score" in result:
            return result
        return {
            "score": 0,
            "dimensions": {},
            "issues": [],
            "suggestions": [],
            "summary": content.strip(),
            "_raw": content,
            "_parse_error": True,
        }
