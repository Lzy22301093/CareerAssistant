"""意图分类测试（v3）— classify_intent 各意图/兜底/异常。"""

from __future__ import annotations

import json

import pytest

from app.graph.intent import classify_intent, VALID_INTENTS
from app.llm import Message, Response, Role


class MockLLM:
    """可编程 Mock LLM。"""

    def __init__(self, default_response: str = "{}"):
        self._rules: list[tuple[str, str]] = []
        self._default = default_response

    def when(self, contains: str, response: str) -> "MockLLM":
        self._rules.append((contains, response))
        return self

    async def chat(self, messages: list[Message], **kwargs) -> Response:
        content = " ".join(m.content for m in messages)
        for pattern, resp in self._rules:
            if pattern in content:
                return Response(content=resp)
        return Response(content=self._default)


def _intent_json(intent: str, confidence: float = 0.95, reason: str = "test") -> str:
    return json.dumps({"intent": intent, "reason": reason, "confidence": confidence})


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_upload_jd(self):
        llm = MockLLM(_intent_json("upload_jd"))
        result = await classify_intent(llm, "这是岗位描述：Python 工程师", {})
        assert result["intent"] == "upload_jd"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_ask_question(self):
        llm = MockLLM(_intent_json("ask_question"))
        result = await classify_intent(llm, "这个岗位我匹配吗", {})
        assert result["intent"] == "ask_question"

    @pytest.mark.asyncio
    async def test_generate_cover_letter(self):
        llm = MockLLM(_intent_json("generate_cover_letter"))
        result = await classify_intent(llm, "帮我写个求职信", {})
        assert result["intent"] == "generate_cover_letter"

    @pytest.mark.asyncio
    async def test_parse_failure_falls_back(self):
        """输出非 JSON → fallback（调用方回退规则引擎）。"""
        llm = MockLLM("这不是 JSON")
        result = await classify_intent(llm, "随便说点什么", {})
        assert result["intent"] == "fallback"

    @pytest.mark.asyncio
    async def test_invalid_intent_falls_back(self):
        """输出了非法意图 → fallback。"""
        llm = MockLLM(_intent_json("not_a_real_intent"))
        result = await classify_intent(llm, "随便", {})
        assert result["intent"] == "fallback"

    @pytest.mark.asyncio
    async def test_low_confidence_falls_back(self):
        """置信度过低 → fallback。"""
        llm = MockLLM(_intent_json("upload_jd", confidence=0.3))
        result = await classify_intent(llm, "随便", {})
        assert result["intent"] == "fallback"

    @pytest.mark.asyncio
    async def test_llm_error_falls_back(self):
        """LLM 调用异常 → fallback（不中断流程）。"""

        class BoomLLM:
            async def chat(self, messages, **kwargs):
                raise RuntimeError("boom")

        result = await classify_intent(BoomLLM(), "随便", {})
        assert result["intent"] == "fallback"

    @pytest.mark.asyncio
    async def test_empty_message_falls_back(self):
        result = await classify_intent(MockLLM(), "", {})
        assert result["intent"] == "fallback"

    def test_valid_intents_set(self):
        assert "upload_jd" in VALID_INTENTS
        assert "generate_cover_letter" in VALID_INTENTS
        assert "record_interview" in VALID_INTENTS
        assert "interview_sim" not in VALID_INTENTS
        assert len(VALID_INTENTS) == 9

    @pytest.mark.asyncio
    async def test_record_interview(self):
        llm = MockLLM(_intent_json("record_interview"))
        result = await classify_intent(llm, "今天面试挂了，问了 Redis", {})
        assert result["intent"] == "record_interview"
