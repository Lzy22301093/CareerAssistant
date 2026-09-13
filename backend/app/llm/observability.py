"""LLM 调用级观测埋点。

项目内所有 LLM 调用都经由 BaseAgent._call_llm（Agent 节点、意图分类、
结构化调用 consolidate 等），在此统一记录：

- 调用 id、agent 名、模型
- 延迟、prompt/completion tokens（缺 usage 时回退字符数）
- 重试次数与重试错误类型（配合 with_retry 的 on_retry 回调）
- 最终状态与错误分类（classify_llm_error）

捕获机制：请求入口调用 start_llm_capture() 在当前 context 放入共享列表；
LangGraph 并行节点作为子任务继承 context（引用同一列表对象），
因此一次请求的全部记录（含并行节点与图执行后的 consolidate）汇总到一处，
由 sessions.py 的 SSE 循环逐条推送、done 事件附汇总、会话持久化截断保留。
未开启捕获时（如单元测试）emit 为 no-op，零开销。
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# 会话中最多保留的 LLM 调用记录条数（防止会话数据无限增长）
MAX_SESSION_RECORDS = 200


@dataclass
class LLMCallRecord:
    """单次逻辑 LLM 调用（含其全部重试）的记录。"""

    call_id: str
    agent: str
    model: str
    status: str = "success"  # success / failed
    latency_ms: float = 0.0
    retries: int = 0
    retry_error_types: list[str] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    prompt_chars: int = 0
    completion_chars: int = 0
    error_type: str = ""
    error_message: str = ""
    started_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "agent": self.agent,
            "model": self.model,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 1),
            "retries": self.retries,
            "retry_error_types": self.retry_error_types,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "prompt_chars": self.prompt_chars,
            "completion_chars": self.completion_chars,
            "error_type": self.error_type,
            "error_message": self.error_message[:200],
            "started_at": self.started_at,
        }


def classify_llm_error(exc: Exception) -> str:
    """把 LLM 调用异常归类为简短标签，供 trace / 前端按类别展示。"""
    name = type(exc).__name__
    name_low = name.lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)

    if status == 429 or "ratelimit" in name_low:
        return "rate_limit"
    if "timeout" in name_low or "timeout" in str(exc).lower():
        return "timeout"
    if "connection" in name_low:
        return "connection"
    if status in (401, 403) or "auth" in name_low or "permission" in name_low:
        return "auth"
    if status in (400, 404, 422) or "badrequest" in name_low or "notfound" in name_low:
        return "bad_request"
    if isinstance(status, int) and status >= 500:
        return "server"
    if "internal" in name_low:
        return "server"
    return name or "unknown"


# 当前请求的捕获列表；default=None 表示未开启捕获
_capture: ContextVar[list[LLMCallRecord] | None] = ContextVar("llm_call_capture", default=None)


def start_llm_capture() -> list[LLMCallRecord]:
    """开始一次请求级捕获，返回共享记录列表（调用方持有引用增量消费）。"""
    records: list[LLMCallRecord] = []
    _capture.set(records)
    return records


def get_captured_calls() -> list[LLMCallRecord]:
    """获取当前 context 已捕获的记录（未开启时为空列表）。"""
    return _capture.get() or []


def emit_call_record(record: LLMCallRecord) -> None:
    """追加一条记录；未开启捕获时静默丢弃（保持调用方零负担）。"""
    records = _capture.get()
    if records is not None:
        records.append(record)


class LLMCallTracker:
    """单次逻辑 LLM 调用的记录器，由 BaseAgent._call_llm 创建。

    - note_retry: with_retry 的 on_retry 回调，累计重试次数与错误类型
    - succeed / fail: 记录最终结果并 emit（同时打一条结构化日志，
      捕获未开启时日志仍有排查价值）
    """

    def __init__(self, agent: str, model: str, prompt_chars: int = 0):
        self._record = LLMCallRecord(
            call_id=uuid.uuid4().hex[:8],
            agent=agent or "unknown_agent",
            model=model or "unknown_model",
            prompt_chars=prompt_chars,
            started_at=datetime.now().isoformat(timespec="milliseconds"),
        )
        self._start = time.perf_counter()

    def note_retry(self, exc: Exception, attempt: int, delay: float) -> None:
        self._record.retries += 1
        self._record.retry_error_types.append(classify_llm_error(exc))

    def succeed(self, response: Any) -> None:
        rec = self._record
        rec.latency_ms = (time.perf_counter() - self._start) * 1000
        rec.completion_chars = len(getattr(response, "content", "") or "")
        usage = getattr(response, "usage", None)
        if usage is not None:
            rec.prompt_tokens = usage.prompt_tokens
            rec.completion_tokens = usage.completion_tokens
            rec.total_tokens = usage.total_tokens
        emit_call_record(rec)
        logger.info(
            f"[{rec.agent}] LLM call done in {rec.latency_ms / 1000:.1f}s "
            f"model={rec.model} prompt={rec.prompt_tokens if rec.prompt_tokens is not None else '?'}tk "
            f"completion={rec.completion_tokens if rec.completion_tokens is not None else '?'}tk "
            f"retries={rec.retries}"
        )

    def fail(self, exc: Exception) -> None:
        rec = self._record
        rec.latency_ms = (time.perf_counter() - self._start) * 1000
        rec.status = "failed"
        rec.error_type = classify_llm_error(exc)
        rec.error_message = str(exc)
        emit_call_record(rec)
        logger.warning(
            f"[{rec.agent}] LLM call failed after {rec.latency_ms / 1000:.1f}s "
            f"retries={rec.retries} error={rec.error_type}: {rec.error_message[:200]}"
        )


def start_llm_call(agent: str, model: str, prompt_chars: int = 0) -> LLMCallTracker:
    """创建单次调用的 tracker（BaseAgent._call_llm 使用）。"""
    return LLMCallTracker(agent=agent, model=model, prompt_chars=prompt_chars)


def summarize_calls(records: list[LLMCallRecord]) -> dict[str, Any]:
    """请求级汇总：总次数 / 失败 / 重试 / 总延迟 / token 用量 / 分 agent 统计。"""
    by_agent: dict[str, dict[str, Any]] = {}
    for r in records:
        entry = by_agent.setdefault(r.agent, {"calls": 0, "llm_time_ms": 0.0})
        entry["calls"] += 1
        entry["llm_time_ms"] = round(entry["llm_time_ms"] + r.latency_ms, 1)

    return {
        "total_calls": len(records),
        "failed_calls": sum(1 for r in records if r.status == "failed"),
        "total_retries": sum(r.retries for r in records),
        "llm_time_ms": round(sum(r.latency_ms for r in records), 1),
        "prompt_tokens": sum(r.prompt_tokens or 0 for r in records),
        "completion_tokens": sum(r.completion_tokens or 0 for r in records),
        "by_agent": by_agent,
    }
