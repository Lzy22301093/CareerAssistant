"""Interview Q&A Agent — 根据 JD 和画像生成面试题。"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个专业的面试辅导助手。你的任务是根据职位要求和候选人画像，生成有针对性的面试题。

可用工具：
- question_bank：搜索面试题库，获取常见面试题和参考答案。生成题目前请调用此工具获取参考题目（可按 category/topic/difficulty 筛选），再结合 JD 与画像组织最终题目。

请以 JSON 格式返回面试题列表：
{
    "questions": [
        {
            "question": "面试问题",
            "category": "behavioral|technical|situational",
            "difficulty": "easy|medium|hard",
            "answer_points": ["要点1", "要点2"],
            "sample_answer": "参考答案"
        }
    ]
}

要求：
1. 生成 5-10 道面试题
2. 包含技术题、行为题和情景题
3. 难度分布：2 easy, 3-4 medium, 1-2 hard
4. answer_points 列出 3-5 个关键点
5. sample_answer 简洁明了（100-200字）
6. 只返回 JSON，不要添加额外说明"""


class InterviewQAAgent(BaseAgent):
    """根据 JD、画像和差距分析生成面试题。"""

    name = "interview_qa"
    description = "生成针对性面试题"

    def build_messages(self, **kwargs) -> list[Message]:
        jd_analysis = kwargs.get("jd_analysis", {})
        profile = kwargs.get("profile", {})
        gap_analysis = kwargs.get("gap_analysis", {})

        user_content = (
            f"职位分析：\n{json.dumps(jd_analysis, ensure_ascii=False, indent=2)}\n\n"
            f"候选人画像：\n{json.dumps(profile, ensure_ascii=False, indent=2)}"
        )
        if gap_analysis:
            user_content += f"\n\n差距分析：\n{json.dumps(gap_analysis, ensure_ascii=False, indent=2)}"
        user_content += "\n\n请生成面试题。"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "questions" in result:
            return result
        return {
            "questions": [],
            "_raw": content,
            "_parse_error": True,
        }
