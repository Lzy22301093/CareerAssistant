"""意图分类（v3）— LLM 意图识别，失败/低置信时由调用方回退规则引擎。

参考 ai-career-copilot 的 intent classification 模式：
- 一次 LLM 调用（FAST_MODEL，成本低）
- 输出结构化 {intent, reason, confidence}
- 解析失败或低置信 → 调用方回退 rule_based_route（guardrail）
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.base import BaseAgent
from app.llm import Message, Role, with_retry
from app.llm.retry import is_retryable_llm_error
from app.prompts.intent_classification import INTENT_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

# 合法的意图集合
VALID_INTENTS = {
    "upload_jd",
    "upload_profile",
    "gap_analysis",
    "content_edit",
    "render_edit",
    "export",
    "ask_question",
    "generate_cover_letter",
    "record_interview",
}

# 低置信阈值：低于该值视为不可信，回退规则引擎
CONFIDENCE_THRESHOLD = 0.6


def _has_valid_data(data: Any) -> bool:
    if not isinstance(data, dict):
        return bool(data)
    if data.get("_error"):
        return False
    return bool(data)


def _build_state_summary(state: dict) -> str:
    """构造分类器可见的状态摘要。"""
    has_jd = _has_valid_data(state.get("jd_analysis"))
    has_profile = _has_valid_data(state.get("profile"))
    has_resume = _has_valid_data(state.get("resume_content"))
    return (
        f"JD 已分析：{has_jd}，简历画像已提取：{has_profile}，"
        f"简历已生成：{has_resume}"
    )


class _IntentClassifier(BaseAgent):
    """内部使用的分类 Agent（复用 BaseAgent 的 LLM 调用/重试/超时）。"""

    name = "intent_classifier"

    def build_messages(self, **kwargs) -> list[Message]:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            has_jd=kwargs.get("has_jd", False),
            has_profile=kwargs.get("has_profile", False),
            has_resume=kwargs.get("has_resume", False),
            user_message=kwargs.get("user_message", ""),
        )
        return [Message(role=Role.USER, content=prompt)]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        if result and result.get("intent") in VALID_INTENTS:
            return result
        return {"_parse_error": True}


async def classify_intent(
    llm, user_message: str, state: dict
) -> dict[str, Any]:
    """对用户消息做 LLM 意图分类。

    Args:
        llm: LLMProvider 实例。
        user_message: 用户当前消息。
        state: 当前 GraphState（用于状态摘要）。

    Returns:
        {"intent": str, "reason": str, "confidence": float}
        解析失败/非法意图时返回 {"intent": "fallback", "reason": "...", "confidence": 0.0}，
        由调用方回退规则引擎。
    """
    if not user_message or not user_message.strip():
        return {"intent": "fallback", "reason": "空消息", "confidence": 0.0}

    classifier = _IntentClassifier(llm)
    # 意图分类走快速模型（FAST_MODEL 已由 create_agents 注入？这里单独创建：
    # 分类是一次独立调用，直接用主 provider 的默认模型即可，或传 fast 模型）
    try:
        result = await classifier.run(
            user_message=user_message,
            has_jd=_has_valid_data(state.get("jd_analysis")),
            has_profile=_has_valid_data(state.get("profile")),
            has_resume=_has_valid_data(state.get("resume_content")),
        )
    except Exception as e:
        logger.warning(f"意图分类调用失败: {e}")
        return {"intent": "fallback", "reason": f"分类调用失败: {e}", "confidence": 0.0}

    if result.get("_parse_error"):
        logger.warning("意图分类输出解析失败，回退规则引擎")
        return {"intent": "fallback", "reason": "分类输出解析失败", "confidence": 0.0}

    try:
        confidence = float(result.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    intent = result["intent"]
    if confidence < CONFIDENCE_THRESHOLD:
        logger.info(f"意图分类置信度过低 ({confidence:.2f})，回退规则引擎")
        return {"intent": "fallback", "reason": result.get("reason", ""), "confidence": confidence}

    logger.info(f"意图分类: {intent} (confidence={confidence:.2f}, reason={result.get('reason', '')})")
    return {
        "intent": intent,
        "reason": result.get("reason", ""),
        "confidence": confidence,
    }
