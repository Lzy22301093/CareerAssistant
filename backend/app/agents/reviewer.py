"""Reviewer Agent — 评审简历内容质量，提出改进建议。"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个资深的简历评审专家。你的任务是评审生成的简历内容，从多个维度打分并提出具体改进建议。

请以 JSON 格式返回评审结果：
{
    "score": 78,
    "dimensions": {
        "keyword_coverage": {"score": 80, "comment": "关键词覆盖情况"},
        "achievement_quantification": {"score": 70, "comment": "成就量化程度"},
        "relevance": {"score": 85, "comment": "与目标职位的相关性"},
        "clarity": {"score": 75, "comment": "表达清晰度"},
        "completeness": {"score": 80, "comment": "信息完整性"}
    },
    "issues": [
        {"severity": "high", "description": "问题描述", "section": "工作经历"}
    ],
    "suggestions": [
        {"priority": "high", "suggestion": "具体改进建议", "section": "工作经历"}
    ],
    "summary": "总体评审意见"
}

评分标准：
- keyword_coverage: JD 关键词是否在简历中充分体现
- achievement_quantification: 是否用数据量化成就（如提升 30%、管理 5 人团队）
- relevance: 内容是否针对目标职位，无关内容是否已剔除
- clarity: 表达是否简洁有力，避免冗余
- completeness: 关键板块是否齐全，信息是否充分

要求：
1. 评分 0-100，60 以下为不合格，60-75 为一般，75-85 为良好，85+ 为优秀
2. issues 按 severity 排序：high > medium > low
3. suggestions 按 priority 排序：high > medium > low
4. 只返回 JSON，不要添加额外说明"""


class ReviewerAgent(BaseAgent):
    """评审简历内容质量并提出改进建议。"""

    name = "reviewer"
    description = "评审简历质量"

    # 提取/评审类 Agent：低温度保证稳定，输出较小
    temperature = 0.2
    max_tokens = 2048
    max_parse_attempts = 2  # JSON 解析失败自动修复重试一次

    def build_messages(self, **kwargs) -> list[Message]:
        from app.tools.context import compact_jd, compact_profile, compact_resume_content

        resume_content = compact_resume_content(kwargs.get("resume_content", {}))
        jd_analysis = compact_jd(kwargs.get("jd_analysis", {}))
        profile = compact_profile(kwargs.get("profile", {}))

        user_content = (
            f"目标职位分析：\n{json.dumps(jd_analysis, ensure_ascii=False, indent=2)}\n\n"
            f"候选人画像：\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
            f"待评审的简历内容：\n{json.dumps(resume_content, ensure_ascii=False, indent=2)}\n\n"
            "请从关键词覆盖、成就量化、相关性、清晰度、完整性五个维度评审简历内容。"
        )

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "score" in result and "dimensions" in result:
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
