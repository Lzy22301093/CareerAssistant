"""Gap Analyzer Agent — 对比 JD 与候选人画像，输出匹配分析。"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个专业的职业匹配分析师。你的任务是对比职位要求（JD）和候选人画像，分析匹配度和差距。

可用工具：
- similar_cases：检索相似的简历/面试案例作为参考。分析前请调用此工具获取参考案例，提升建议的专业性和可落地性；检索不到时直接基于已有信息分析。

请以 JSON 格式返回分析结果：
{
    "overall_score": 75.0,
    "strengths": ["优势1", "优势2"],
    "gaps": [
        {
            "category": "skill|experience|education",
            "requirement": "JD 中的要求",
            "current_level": "候选人当前水平",
            "gap_severity": "critical|major|minor",
            "suggestion": "改进建议"
        }
    ],
    "recommendations": ["建议1", "建议2"]
}

要求：
1. overall_score 范围 0-100，基于匹配度打分
2. strengths 至少列出 2 个
3. gaps 按 severity 从高到低排列
4. recommendations 给出 3-5 条具体可执行的建议
5. 只返回 JSON，不要添加额外说明"""


class GapAnalyzerAgent(BaseAgent):
    """对比 JD 与候选人画像，输出 matched/missing skills 和 overall_score。"""

    name = "gap_analyzer"
    description = "分析 JD 与候选人画像的匹配度"

    def build_messages(self, **kwargs) -> list[Message]:
        jd_analysis = kwargs.get("jd_analysis", {})
        profile = kwargs.get("profile", {})
        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(
                role=Role.USER,
                content=(
                    f"职位分析：\n{json.dumps(jd_analysis, ensure_ascii=False, indent=2)}\n\n"
                    f"候选人画像：\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
                    "请分析两者的匹配度和差距。"
                ),
            ),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "overall_score" in result:
            return result
        return {
            "overall_score": 0.0,
            "strengths": [],
            "gaps": [],
            "recommendations": [],
            "_raw": content,
            "_parse_error": True,
        }
