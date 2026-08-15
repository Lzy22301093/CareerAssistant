"""Clarifier Agent — 智能检测缺失信息，生成有针对性的澄清问题。

支持多轮对话：
- 首次交互：检测缺失信息，生成引导问题
- 后续交互：解析用户回复，提取提供的信息
- 澄清完成：当信息齐全时，返回 ready_to_proceed=True
"""

from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.llm import Message, Role

SYSTEM_PROMPT = """你是一个智能对话助手。你的任务是根据当前会话状态和用户消息，判断缺少什么信息，并生成有针对性的澄清问题。

当前会话可能的状态：
- 无 JD：用户还没提供职位描述
- 无简历：用户还没提供简历/候选人信息
- 有 JD + 简历：可以进行差距分析和简历优化
- 有完整信息：可以生成简历内容

请以 JSON 格式返回：
{
    "missing_items": ["jd", "resume"],
    "question": "您好！我注意到您想优化简历，但还需要一些信息。请提供：\n1. 目标职位的 JD（职位描述）\n2. 您的简历或个人经历概述",
    "suggestions": ["粘贴 JD 文本", "上传简历文件", "简述工作经历"],
    "context_type": "initial"
}

context_type 说明：
- "initial": 首次交互，信息基本为空
- "partial_jd": 有 JD 但缺简历
- "partial_resume": 有简历但缺 JD
- "clarify_intent": 不确定用户想做什么
- "refinement": 已有完整信息，用户可能想调整

要求：
1. question 要具体、友好、可操作
2. suggestions 提供 2-4 个具体的操作建议
3. 只返回 JSON，不要添加额外说明"""

MULTI_TURN_PROMPT = """你是一个智能对话助手。用户正在回复你之前的澄清问题。你需要：
1. 判断用户是否提供了所需信息
2. 如果提供了，提取关键内容
3. 判断是否所有必要信息都已齐全

请以 JSON 格式返回：
{
    "detected_intent": "provide_jd",
    "extracted_content": "用户提供的 JD 文本或简历内容",
    "ready_to_proceed": false,
    "missing_items": ["resume"],
    "next_action": "profile_extractor",
    "question": "已收到 JD，请提供您的简历或工作经历。",
    "suggestions": ["粘贴简历", "简述工作经历"]
}

detected_intent 说明：
- "provide_jd": 用户提供了职位描述
- "provide_resume": 用户提供了简历/工作经历
- "refine_request": 用户想调整已有的内容
- "ask_question": 用户在提问
- "unclear": 无法判断意图

next_action 说明（当 ready_to_proceed=true 时）：
- "jd_analyzer": 需要分析 JD
- "profile_extractor": 需要提取简历
- "gap_analyzer": JD 和简历都有了，可以分析差距
- "content_generator": 所有信息齐全，可以生成内容

要求：
1. 如果用户粘贴了大段文本，尝试判断是 JD 还是简历
2. ready_to_proceed=true 时不需要 question 和 suggestions
3. 只返回 JSON，不要添加额外说明"""


class ClarifierAgent(BaseAgent):
    """智能澄清：检测缺失信息并生成引导问题，支持多轮对话。"""

    name = "clarifier"
    description = "智能澄清与引导"

    # 对话类 Agent：输出短小，低温度保证稳定
    temperature = 0.3
    max_tokens = 1024

    def build_messages(self, **kwargs) -> list[Message]:
        user_message = kwargs.get("user_message", "")
        session_state = kwargs.get("session_state", {})
        route_reason = kwargs.get("route_reason", "")
        is_multi_turn = kwargs.get("is_multi_turn", False)

        if is_multi_turn:
            return self._build_multi_turn_messages(user_message, session_state)
        return self._build_initial_messages(user_message, session_state, route_reason)

    def _build_initial_messages(
        self, user_message: str, session_state: dict, route_reason: str
    ) -> list[Message]:
        """首次澄清：检测缺失信息。"""
        state_desc = []
        if session_state.get("has_jd"):
            state_desc.append("已有 JD 分析结果")
        elif session_state.get("has_jd_text"):
            state_desc.append("有 JD 文件待分析")
        else:
            state_desc.append("缺少 JD")

        if session_state.get("has_profile"):
            state_desc.append("已有候选人画像")
        elif session_state.get("has_resume_text"):
            state_desc.append("有简历文件待提取")
        else:
            state_desc.append("缺少简历/候选人信息")

        if session_state.get("has_resume_content"):
            state_desc.append("已生成简历内容")

        user_content = (
            f"当前状态：{', '.join(state_desc) if state_desc else '全新会话'}\n\n"
            f"用户消息：{user_message}\n\n"
        )
        if route_reason:
            user_content += f"路由原因：{route_reason}\n\n"
        user_content += "请判断缺少什么信息，并生成澄清问题。"

        return [
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def _build_multi_turn_messages(
        self, user_message: str, session_state: dict
    ) -> list[Message]:
        """多轮澄清：解析用户回复。"""
        state_desc = []
        if session_state.get("has_jd"):
            state_desc.append("已有 JD")
        if session_state.get("has_profile"):
            state_desc.append("已有简历")
        if session_state.get("has_resume_content"):
            state_desc.append("已生成简历内容")

        # 包含最近的澄清历史
        clarification_history = session_state.get("clarification_history", [])
        history_text = ""
        if clarification_history:
            history_text = "之前的澄清对话：\n"
            for i, item in enumerate(clarification_history[-3:], 1):
                history_text += f"  {i}. 系统问：{item.get('question', '')}\n"
                if item.get("answer"):
                    history_text += f"     用户答：{item['answer']}\n"

        user_content = (
            f"当前状态：{', '.join(state_desc) if state_desc else '全新会话'}\n\n"
            f"{history_text}\n"
            f"用户最新回复：{user_message}\n\n"
            "请判断用户是否提供了所需信息，并决定下一步。"
        )

        return [
            Message(role=Role.SYSTEM, content=MULTI_TURN_PROMPT),
            Message(role=Role.USER, content=user_content),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and "question" in result:
            return result
        if result and "ready_to_proceed" in result:
            return result
        return {
            "missing_items": [],
            "question": content.strip() if content.strip() else "请提供更多信息以便继续处理。",
            "suggestions": [],
            "context_type": "unknown",
            "_raw": content,
            "_parse_error": True,
        }
