"""InterviewerAgent — 根据 Evaluator 决策生成面试问题。"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一位专业的技术面试官，正在进行模拟面试。

你的任务是根据面试策略生成下一个面试问题。

## 提问风格
- 语气自然、专业，像真实面试对话
- 不要一次问多个问题
- 追问时要引用候选人的回答
- 技术问题要有深度，行为问题要有具体场景

## 输出格式
严格输出以下 JSON，不要添加任何额外文字：
{
    "question": "面试问题文本",
    "category": "technical|behavioral|situational"
}"""


class InterviewerAgent(BaseAgent):
    """根据 Evaluator 决策生成面试问题。"""

    name = "interviewer"
    description = "生成面试提问"

    temperature: float = 0.7
    # 面试出题需要结构化 JSON，但不需要 8192；过大拖慢首响
    max_tokens: int = 2048
    max_parse_attempts: int = 2

    def build_messages(self, **kwargs) -> list[Message]:
        target_position = kwargs.get("target_position", "")
        difficulty = kwargs.get("difficulty_level", "medium")
        decision = kwargs.get("decision", {})
        pending_topics = kwargs.get("pending_topics", [])
        covered_topics = kwargs.get("covered_topics", [])
        referenced_questions = kwargs.get("referenced_questions", [])
        current_question = kwargs.get("current_question", "")
        current_answer = kwargs.get("current_answer", "")

        user_content = (
            f"## 面试信息\n"
            f"- 目标岗位：{target_position}\n"
            f"- 当前难度：{difficulty}\n"
            f"- 已覆盖话题：{', '.join(covered_topics) if covered_topics else '无'}\n"
            f"- 待考察话题：{', '.join(pending_topics) if pending_topics else '无'}\n"
        )

        if referenced_questions:
            user_content += f"- 候选人已参考过的题目（优先跳过）：{json.dumps(referenced_questions[:10], ensure_ascii=False)}\n"

        # Evaluator 的决策
        action = decision.get("next_action", "切换话题")
        user_content += f"\n## 面试官决策\n- 动作：{action}\n- 理由：{decision.get('reason', '')}\n"

        if action == "追问" and decision.get("follow_up_question"):
            user_content += f"- 建议追问：{decision['follow_up_question']}\n"
        elif action == "切换话题":
            if decision.get("next_topic"):
                user_content += f"- 下一个话题：{decision['next_topic']}\n"
            if decision.get("next_question"):
                user_content += f"- 建议问题：{decision['next_question']}\n"
        elif action in ("提高难度", "降低难度"):
            user_content += f"- 新难度：{decision.get('new_difficulty', difficulty)}\n"

        # 如果是追问，提供上下文
        if action == "追问" and current_question and current_answer:
            user_content += (
                f"\n## 上一轮对话\n"
                f"- 问题：{current_question}\n"
                f"- 回答：{current_answer}\n"
            )

        user_content += "\n请生成下一个面试问题。"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "question" in result:
            if "category" not in result:
                result["category"] = "technical"
            return result
        return {
            "question": "请介绍一下你最近做的一个项目。",
            "category": "behavioral",
            "_raw": content,
            "_parse_error": True,
        }
