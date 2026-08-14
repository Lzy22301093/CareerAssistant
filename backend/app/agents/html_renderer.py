"""HTML Renderer Agent — 根据简历内容生成渲染配置。"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个专业的简历排版助手。你的任务是根据简历内容和用户偏好，生成渲染配置。

请以 JSON 格式返回渲染配置：
{
    "template": "modern|classic|minimal|creative",
    "font_size": 11,
    "line_spacing": 1.15,
    "margin_top": 1.0,
    "margin_bottom": 1.0,
    "margin_left": 1.0,
    "margin_right": 1.0,
    "accent_color": "#2563eb",
    "layout_notes": "排版建议说明"
}

要求：
1. 根据简历内容量和职位类型选择合适的模板
2. 技术岗位推荐 modern 或 classic
3. 创意岗位推荐 creative
4. 内容较多时适当减小字号（最小 10）
5. 只返回 JSON，不要添加额外说明"""


class HTMLRendererAgent(BaseAgent):
    """根据简历内容和样式指令生成渲染配置 JSON。"""

    name = "html_renderer"
    description = "生成简历渲染配置"

    def build_messages(self, **kwargs) -> list[Message]:
        resume_content = kwargs.get("resume_content", {})
        style_preferences = kwargs.get("style_preferences", "")

        user_content = f"简历内容：\n{resume_content}"
        if style_preferences:
            user_content += f"\n\n样式偏好：{style_preferences}"
        user_content += "\n\n请生成渲染配置。"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "template" in result:
            return result
        return {
            "template": "modern",
            "font_size": 11,
            "line_spacing": 1.15,
            "margin_top": 1.0,
            "margin_bottom": 1.0,
            "margin_left": 1.0,
            "margin_right": 1.0,
            "accent_color": "#2563eb",
            "_raw": content,
            "_parse_error": True,
        }
