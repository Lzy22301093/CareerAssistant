"""VoiceChatHandler — 简单语音对话处理器。

不包含面试评估逻辑，纯 ASR → LLM → TTS 对话循环。
注入 JD 分析、用户画像等上下文到 system prompt。

参考 voice-chat 项目的 LLM+TTS 并发流水线模式。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.llm.base import Message, Role
from app.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# 对话历史最大轮数
MAX_HISTORY_TURNS = 20


class VoiceChatSession:
    """单次语音对话的会话状态。"""

    def __init__(self, session_id: str, system_prompt: str):
        self.session_id = session_id
        self.system_prompt = system_prompt
        self.history: list[dict[str, str]] = []  # [{role, content}, ...]
        self.turn_count = 0

    def add_user_message(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})
        self.turn_count += 1
        self._trim_history()

    def add_assistant_message(self, text: str) -> None:
        self.history.append({"role": "assistant", "content": text})
        self._trim_history()

    def get_messages(self) -> list[dict[str, str]]:
        """返回带 system prompt 的完整消息列表。"""
        msgs = [{"role": "system", "content": self.system_prompt}]
        msgs.extend(self.history)
        return msgs

    def _trim_history(self) -> None:
        """裁剪历史到最近 N 轮。"""
        if len(self.history) > MAX_HISTORY_TURNS * 2:
            self.history = self.history[-(MAX_HISTORY_TURNS * 2):]


class VoiceChatHandler:
    """简单语音对话处理器。"""

    def __init__(self, provider: OpenAIProvider):
        self._provider = provider
        self._sessions: dict[str, VoiceChatSession] = {}

    def start_chat(
        self,
        jd_analysis: dict[str, Any],
        profile: dict[str, Any],
        gap_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建对话会话，返回 session_id 和开场白。"""
        session_id = f"vc-{uuid.uuid4().hex[:12]}"
        system_prompt = self._build_system_prompt(jd_analysis, profile, gap_analysis)
        session = VoiceChatSession(session_id, system_prompt)
        self._sessions[session_id] = session

        greeting = self._build_greeting(jd_analysis, profile)
        session.add_assistant_message(greeting)

        logger.info(f"[VoiceChat] started: {session_id}")
        return {
            "session_id": session_id,
            "greeting": greeting,
        }

    async def process_message_stream(
        self,
        session_id: str,
        user_text: str,
    ):
        """流式处理用户消息，yield 每个 token。"""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.add_user_message(user_text)
        messages = session.get_messages()

        # 将 dict 转为 Message 对象
        llm_messages = [
            Message(role=Role(m["role"]), content=m["content"])
            for m in messages
        ]

        full_response = ""
        async for chunk in self._provider.stream_chat(
            llm_messages,
            temperature=0.7,
            max_tokens=2048,
        ):
            if chunk.content:
                full_response += chunk.content
                yield chunk.content

        session.add_assistant_message(full_response)

    async def get_feedback(self, session_id: str) -> dict[str, Any]:
        """对话结束后生成反馈报告。"""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # 构造反馈生成 prompt
        history_text = "\n".join(
            f"{'面试官' if m['role'] == 'assistant' else '用户'}: {m['content']}"
            for m in session.history
        )

        feedback_prompt = f"""你是一位专业的面试教练。请根据以下模拟面试对话，给出详细的反馈报告。

对话记录：
{history_text}

请用 JSON 格式返回报告，包含以下字段：
{{
    "overall_score": 0-100 的综合评分,
    "overall_assessment": {{
        "strengths": ["优势1", "优势2"],
        "weaknesses": ["不足1", "不足2"],
        "summary": "总体评价（2-3句话）"
    }},
    "dimension_scores": {{
        "专业知识": 0-100,
        "表达能力": 0-100,
        "逻辑思维": 0-100,
        "岗位匹配": 0-100
    }},
    "suggestions": ["建议1", "建议2", "建议3"]
}}"""

        messages = [
            Message(role=Role.SYSTEM, content="你是一位专业的面试教练，擅长分析面试表现并给出建设性反馈。"),
            Message(role=Role.USER, content=feedback_prompt),
        ]

        try:
            response = await self._provider.chat(
                messages,
                temperature=0.3,
                max_tokens=2048,
                json_mode=True,
            )
            report = json.loads(response.content)
            logger.info(f"[VoiceChat] feedback generated for {session_id}")
            return report
        except Exception as e:
            logger.error(f"[VoiceChat] feedback generation failed: {e}")
            return {
                "overall_score": 0,
                "overall_assessment": {
                    "strengths": [],
                    "weaknesses": [],
                    "summary": "反馈生成失败，请重试",
                },
                "dimension_scores": {},
                "suggestions": [],
            }

    def _build_system_prompt(
        self,
        jd_analysis: dict[str, Any],
        profile: dict[str, Any],
        gap_analysis: dict[str, Any] | None,
    ) -> str:
        """构建注入上下文的 system prompt。"""
        parts = [
            "你是一位专业的模拟面试官。你的任务是根据以下信息进行一场逼真的技术面试。",
            "",
            "## 岗位要求（JD 分析）",
            json.dumps(jd_analysis, ensure_ascii=False, indent=2),
            "",
            "## 候选人画像",
            json.dumps(profile, ensure_ascii=False, indent=2),
        ]

        if gap_analysis:
            parts.extend([
                "",
                "## 差距分析",
                json.dumps(gap_analysis, ensure_ascii=False, indent=2),
            ])

        parts.extend([
            "",
            "## 面试规则",
            "1. 每次只问一个问题，等待用户回答后再问下一个",
            "2. 根据用户的回答深度决定后续问题的难度",
            "3. 如果用户回答不够深入，可以追问细节",
            "4. 保持专业、友好的语气",
            "5. 问题要结合岗位要求和候选人背景",
            "6. 面试约 8-10 轮后自然结束",
        ])

        return "\n".join(parts)

    def _build_greeting(
        self,
        jd_analysis: dict[str, Any],
        profile: dict[str, Any],
    ) -> str:
        """构建开场白。"""
        company = jd_analysis.get("company", "贵公司")
        position = jd_analysis.get("position", "该岗位")
        name = profile.get("name", "候选人")

        return f"你好{name}，欢迎参加{company}{position}的面试。我是今天的面试官，接下来我会问你一些问题，请放松，如实回答就好。我们开始吧——请先简单介绍一下你自己。"
