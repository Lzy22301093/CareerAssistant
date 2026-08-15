"""Cover Letter Agent（v3）— 生成求职信或招聘软件打招呼文案。

两种渠道（由用户选择）：
- linkedin_message：招聘软件打招呼，简短（100 字以内）
- email：正式求职信，150-300 字，含主题与正文
"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role
from app.tools.analysis_tools import BestPracticesTool

SYSTEM_PROMPT_TEMPLATE = """你是一个专业的求职文案助手。根据候选人画像、目标职位分析和差距分析，生成针对性的求职文案。

渠道说明：
- linkedin_message：招聘软件/私信打招呼。要求：100 字以内，一句话点明目标岗位 + 与岗位最匹配的 1-2 个亮点，语气友好自然，末尾可加一句邀请（如"方便的话期待和您聊聊"）
- email：正式求职信。要求：150-300 字，结构为 开场（应聘岗位+来源）→ 匹配点（2-3 条，引用具体经历，不捏造）→ 价值（能为团队带来什么）→ 行动号召（期待面试）

可用工具：
- best_practices：获取求职文案写作要点，生成前可调用

请以 JSON 格式返回：
{
    "channel": "linkedin_message|email",
    "subject": "主题（仅 email 需要，打招呼可为空）",
    "body": "正文",
    "tone": "professional|friendly",
    "highlights": ["正文中引用的候选人亮点1", "亮点2"]
}

要求：
1. 内容必须基于画像中的真实经历，不得捏造
2. 突出与 JD 的匹配点，可参考差距分析中的优势
3. 只返回 JSON，不要添加额外说明"""


class CoverLetterAgent(BaseAgent):
    """生成求职信 / 打招呼文案（双渠道）。"""

    name = "cover_letter"
    description = "生成求职信或招聘软件打招呼文案"

    temperature = 0.7
    max_tokens = 2048
    tools = [BestPracticesTool()]

    def build_messages(self, **kwargs) -> list[Message]:
        from app.tools.context import compact_gap, compact_jd, compact_profile

        profile = compact_profile(kwargs.get("profile", {}))
        jd_analysis = compact_jd(kwargs.get("jd_analysis", {}))
        gap_analysis = compact_gap(kwargs.get("gap_analysis", {}))
        channel = kwargs.get("channel", "email")
        user_instructions = kwargs.get("user_instructions", "")

        user_content = (
            f"渠道：{channel}\n\n"
            f"候选人画像：\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
            f"目标职位分析：\n{json.dumps(jd_analysis, ensure_ascii=False, indent=2)}"
        )
        if gap_analysis:
            user_content += f"\n\n差距分析：\n{json.dumps(gap_analysis, ensure_ascii=False, indent=2)}"
        if user_instructions:
            user_content += f"\n\n用户补充要求：{user_instructions}"
        user_content += f"\n\n请生成{channel}文案。"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT_TEMPLATE),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "body" in result:
            return result
        return {
            "channel": "",
            "subject": "",
            "body": content.strip(),
            "tone": "professional",
            "highlights": [],
            "_raw": content,
            "_parse_error": True,
        }
