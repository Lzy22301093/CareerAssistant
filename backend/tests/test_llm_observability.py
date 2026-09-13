"""Tests for LLM 调用级观测埋点。"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.base import BaseAgent
from app.llm import Message, Response, Role, Usage
from app.llm.observability import (
    LLMCallRecord,
    classify_llm_error,
    start_llm_call,
    start_llm_capture,
    summarize_calls,
)


# === 错误分类 ===


class _FakeAPIError(Exception):
    """带 status_code 的伪 SDK 异常（绕开 openai 构造依赖）。"""


def test_classify_rate_limit():
    exc = _FakeAPIError("Too many requests")
    exc.status_code = 429
    assert classify_llm_error(exc) == "rate_limit"


def test_classify_timeout_by_name():
    assert classify_llm_error(TimeoutError("upstream timeout")) == "timeout"


def test_classify_auth():
    exc = _FakeAPIError("Invalid key")
    exc.status_code = 401
    assert classify_llm_error(exc) == "auth"


def test_classify_bad_request():
    exc = _FakeAPIError("bad")
    exc.status_code = 400
    assert classify_llm_error(exc) == "bad_request"


def test_classify_server():
    exc = _FakeAPIError("boom")
    exc.status_code = 503
    assert classify_llm_error(exc) == "server"


def test_classify_unknown_falls_back_to_class_name():
    assert classify_llm_error(ValueError("weird")) == "ValueError"


# === 捕获与汇总 ===


def test_capture_records_tracker_results():
    records = start_llm_capture()

    tracker = start_llm_call(agent="jd_analyzer", model="mimo-test", prompt_chars=100)
    tracker.succeed(
        Response(content="hello", usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15))
    )

    assert len(records) == 1
    rec = records[0]
    assert rec.agent == "jd_analyzer"
    assert rec.model == "mimo-test"
    assert rec.status == "success"
    assert rec.prompt_tokens == 10
    assert rec.completion_tokens == 5
    assert rec.prompt_chars == 100
    assert rec.completion_chars == 5
    assert rec.latency_ms >= 0


def test_capture_without_start_is_noop():
    # 未开启捕获时 succeed/fail 不抛异常、静默丢弃
    tracker = start_llm_call(agent="x", model="y")
    tracker.succeed(Response(content="ok"))
    tracker2 = start_llm_call(agent="x", model="y")
    tracker2.fail(ValueError("no capture"))
    # 能走到这里即通过


def test_summarize_calls():
    records = [
        LLMCallRecord(call_id="a", agent="jd_analyzer", model="m", status="success",
                      latency_ms=1000.0, prompt_tokens=10, completion_tokens=5, retries=1),
        LLMCallRecord(call_id="b", agent="jd_analyzer", model="m", status="failed",
                      latency_ms=2000.0),
        LLMCallRecord(call_id="c", agent="planner", model="fast", status="success",
                      latency_ms=500.0, prompt_tokens=3, completion_tokens=2),
    ]
    summary = summarize_calls(records)
    assert summary["total_calls"] == 3
    assert summary["failed_calls"] == 1
    assert summary["total_retries"] == 1
    assert summary["llm_time_ms"] == 3500.0
    assert summary["prompt_tokens"] == 13
    assert summary["completion_tokens"] == 7
    assert summary["by_agent"]["jd_analyzer"]["calls"] == 2
    assert summary["by_agent"]["planner"]["calls"] == 1


# === BaseAgent._call_llm 集成 ===


class _FlakyLLM:
    """先抛可重试异常再成功的伪 provider，记录调用次数。"""

    def __init__(self, failures: list[Exception]):
        self.failures = list(failures)
        self.calls = 0
        self.model = "fake-model"

    async def chat(self, messages, **kwargs) -> Response:
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return Response(
            content="ok",
            usage=Usage(prompt_tokens=7, completion_tokens=3, total_tokens=10),
        )


class _StubAgent(BaseAgent):
    name = "stub_agent"

    def build_messages(self, **kwargs):
        return [Message(role=Role.USER, content="hi")]

    def parse_response(self, content: str) -> dict:
        return {"ok": True}


@pytest.mark.asyncio
async def test_call_llm_records_success_with_tokens():
    records = start_llm_capture()
    agent = _StubAgent(_FlakyLLM(failures=[]))

    result = await agent.run()

    assert result == {"ok": True}
    assert len(records) == 1
    rec = records[0]
    assert rec.agent == "stub_agent"
    assert rec.model == "fake-model"
    assert rec.status == "success"
    assert rec.prompt_tokens == 7
    assert rec.completion_tokens == 3


@pytest.mark.asyncio
async def test_call_llm_counts_retries():
    records = start_llm_capture()
    rate_limited = _FakeAPIError("rate limited")
    rate_limited.status_code = 429
    agent = _StubAgent(_FlakyLLM(failures=[rate_limited]))

    with patch("app.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        await agent.run()

    assert len(records) == 1
    rec = records[0]
    assert rec.retries == 1
    assert rec.retry_error_types == ["rate_limit"]
    assert rec.status == "success"


@pytest.mark.asyncio
async def test_call_llm_records_failure_after_exhaustion():
    records = start_llm_capture()
    agent = _StubAgent(_FlakyLLM(failures=[TimeoutError("t1"), TimeoutError("t2"),
                                            TimeoutError("t3"), TimeoutError("t4")]))

    with patch("app.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(TimeoutError):
            await agent.run()

    assert len(records) == 1
    rec = records[0]
    assert rec.status == "failed"
    assert rec.error_type == "timeout"
    # 1 次初始 + 3 次重试均失败
    assert agent.llm.calls == 4
    assert rec.retries == 3
