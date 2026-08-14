"""Content Generator Agent — 根据画像、JD 和差距分析生成简历内容。"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个专业的简历内容生成助手。你的任务是根据候选人画像、职位要求和差距分析，生成针对性的简历内容。

请以 JSON 格式返回生成的简历内容：
{
    "sections": [
        {
            "title": "个人信息",
            "content": "格式化的个人信息"
        },
        {
            "title": "专业技能",
            "content": "与 JD 匹配的技能列表"
        },
        {
            "title": "工作经历",
            "content": "针对 JD 优化的工作经历描述"
        },
        {
            "title": "项目经历",
            "content": "与 JD 相关的项目经历"
        },
        {
            "title": "教育背景",
            "content": "教育信息"
        }
    ],
    "raw_text": "完整的简历纯文本"
}

要求：
1. 内容应针对目标职位进行优化，突出匹配的技能和经验
2. 使用 STAR 法则描述工作成就（情境、任务、行动、结果）
3. 量化成就（如"提升效率30%"）
4. 只返回 JSON，不要添加额外说明"""


class ContentGeneratorAgent(BaseAgent):
    """根据画像 + JD + 差距分析生成结构化简历内容。"""

    name = "content_generator"
    description = "生成针对性简历内容"

    def build_messages(self, **kwargs) -> list[Message]:
        profile = kwargs.get("profile", {})
        jd_analysis = kwargs.get("jd_analysis", {})
        gap_analysis = kwargs.get("gap_analysis", {})
        user_instructions = kwargs.get("user_instructions", "")

        user_content = (
            f"候选人画像：\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
            f"目标职位分析：\n{json.dumps(jd_analysis, ensure_ascii=False, indent=2)}"
        )
        if gap_analysis:
            user_content += f"\n\n差距分析：\n{json.dumps(gap_analysis, ensure_ascii=False, indent=2)}"
        if user_instructions:
            user_content += f"\n\n用户特别要求：{user_instructions}"
        user_content += "\n\n请生成针对性的简历内容。"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "sections" in result:
            return result
        return {
            "sections": [],
            "raw_text": content.strip(),
            "_raw": content,
            "_parse_error": True,
        }
