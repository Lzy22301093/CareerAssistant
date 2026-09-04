"""EvaluatorAgent — 评价候选人回答并决定面试下一步动作。"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一位资深技术面试官，正在对候选人进行模拟面试。

你的任务是：
1. 评价候选人的回答质量（0-10 分）
2. 判断下一步面试策略

## 评分维度
根据目标岗位动态评估以下维度（每项 0-10 分）：
- 专业知识：技术概念是否准确、深入
- 问题分析：思路是否清晰、有条理
- 沟通表达：表述是否简洁、易懂
- 实践经验：是否有实际案例支撑
- 学习能力：能否举一反三

## 决策规则
根据回答质量决定下一步：
- **追问**：回答正确但浅显，有深入空间；或回答有明显错误需要澄清
- **切换话题**：回答优秀，当前话题已充分考察
- **提高难度**：回答轻松、快速准确
- **降低难度**：回答吃力、频繁出错
- **结束面试**：所有核心话题已覆盖，或达到最大轮数

## 输出格式
严格输出以下 JSON，不要添加任何额外文字：
{
    "score": 7.5,
    "dimension_scores": {
        "专业知识": 8.0,
        "问题分析": 7.0,
        "沟通表达": 7.5,
        "实践经验": 6.0,
        "学习能力": 7.0
    },
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["不足1"],
    "feedback": "简短的评价反馈（一句话）",
    "next_action": "追问",
    "reason": "决策理由",
    "follow_up_question": "如果决定追问，这里写追问内容；否则为 null",
    "next_topic": "如果决定切换话题，这里写下一个话题；否则为 null",
    "next_question": "如果决定切换话题，这里写下一道题；否则为 null",
    "new_difficulty": "如果决定调整难度，写新的难度；否则为 null"
}"""


class EvaluatorAgent(BaseAgent):
    """评价候选人回答并决定面试下一步动作。"""

    name = "evaluator"
    description = "评价面试回答并决策"

    temperature: float = 0.3
    # max_tokens 需足够大：MIMO 模型可能有内部思考链消耗 token，过小会导致输出为空
    max_tokens: int = 8192
    max_parse_attempts: int = 2
    json_mode = True

    def build_messages(self, **kwargs) -> list[Message]:
        question = kwargs.get("current_question", "")
        answer = kwargs.get("current_answer", "")
        difficulty = kwargs.get("difficulty_level", "medium")
        turn_count = kwargs.get("turn_count", 0)
        max_turns = kwargs.get("max_turns", 10)
        covered_topics = kwargs.get("covered_topics", [])
        pending_topics = kwargs.get("pending_topics", [])
        dimension_scores = kwargs.get("dimension_scores", {})
        conversation_history = kwargs.get("conversation_history", [])
        referenced_questions = kwargs.get("referenced_questions", [])

        user_content = (
            f"## 当前面试状态\n"
            f"- 已完成轮数：{turn_count}/{max_turns}\n"
            f"- 当前难度：{difficulty}\n"
            f"- 已覆盖话题：{', '.join(covered_topics) if covered_topics else '无'}\n"
            f"- 待考察话题：{', '.join(pending_topics) if pending_topics else '无'}\n"
        )

        if dimension_scores:
            user_content += f"- 历史维度评分：{json.dumps(dimension_scores, ensure_ascii=False)}\n"

        if referenced_questions:
            user_content += f"- 候选人已参考过的题目（避免重复出题）：{json.dumps(referenced_questions[:10], ensure_ascii=False)}\n"

        user_content += (
            f"\n## 当前问题\n{question}\n\n"
            f"## 候选人回答\n{answer}\n\n"
            f"请评价回答并决定下一步动作。"
        )

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "next_action" in result and "score" in result:
            # 校验 next_action 枚举值
            valid_actions = {"追问", "切换话题", "提高难度", "降低难度", "结束面试"}
            if result["next_action"] not in valid_actions:
                result["next_action"] = "切换话题"
            return result
        return {
            "score": 5.0,
            "dimension_scores": {},
            "strengths": [],
            "weaknesses": [],
            "feedback": "",
            "next_action": "切换话题",
            "reason": "解析失败，默认切换话题",
            "follow_up_question": None,
            "next_topic": None,
            "next_question": None,
            "new_difficulty": None,
            "_raw": content,
            "_parse_error": True,
        }
