"""Tests for the retry decorator."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.llm.retry import _retry_delay, with_retry


class _RateLimited(Exception):
    """带 429 状态码的伪限流异常。"""

    status_code = 429


@pytest.mark.asyncio
async def test_success_on_first_try():
    """第一次成功，不重试。"""
    mock_fn = AsyncMock(return_value="ok")
    decorated = with_retry(max_retries=3)(mock_fn)

    result = await decorated()
    assert result == "ok"
    assert mock_fn.call_count == 1


@pytest.mark.asyncio
async def test_success_on_second_try():
    """第一次失败，第二次成功。"""
    mock_fn = AsyncMock(side_effect=[TimeoutError("timeout"), "ok"])
    decorated = with_retry(max_retries=3)(mock_fn)

    with patch("app.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await decorated()

    assert result == "ok"
    assert mock_fn.call_count == 2


@pytest.mark.asyncio
async def test_exhausted_retries():
    """全部失败，抛出最后一次异常。"""
    # side_effect 传异常实例：每次调用都抛同一异常
    # （传列表会在耗尽后抛 StopAsyncIteration，污染断言）
    mock_fn = AsyncMock(side_effect=TimeoutError("timeout"))
    decorated = with_retry(max_retries=2)(mock_fn)

    with patch("app.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(TimeoutError):
            await decorated()

    # 1 次初始调用 + 2 次重试 = 3 次
    assert mock_fn.call_count == 3


@pytest.mark.asyncio
async def test_exponential_delay():
    """验证退避间隔递增。"""
    mock_fn = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), "ok"])
    decorated = with_retry(max_retries=3, base_delay=1.0)(mock_fn)

    sleep_mock = AsyncMock()
    with patch("app.llm.retry.asyncio.sleep", sleep_mock):
        result = await decorated()

    assert result == "ok"
    # 验证 sleep 调用的延迟递增
    assert sleep_mock.call_count == 2
    delays = [call.args[0] for call in sleep_mock.call_args_list]
    assert delays[0] == 1.0   # 1.0 * 2^0
    assert delays[1] == 2.0   # 1.0 * 2^1


def test_rate_limit_backoff_compressed():
    """A3：429 退避从 10/20/30s 压缩为 2/4/8s（快速失败优先）。"""
    assert _retry_delay(_RateLimited(), attempt=0, base_delay=1.0) == 2.0
    assert _retry_delay(_RateLimited(), attempt=1, base_delay=1.0) == 4.0
    assert _retry_delay(_RateLimited(), attempt=2, base_delay=1.0) == 8.0


def test_rate_limit_respects_retry_after_with_cap():
    """429 带 Retry-After 头时尊重之，但设 10s 上限防单次退避失控。"""
    exc = _RateLimited()
    exc.headers = {"retry-after": "60"}
    assert _retry_delay(exc, attempt=0, base_delay=1.0) == 10.0

    exc_short = _RateLimited()
    exc_short.headers = {"retry-after": "5"}
    assert _retry_delay(exc_short, attempt=0, base_delay=1.0) == 5.0


@pytest.mark.asyncio
async def test_on_retry_callback():
    """on_retry 回调在每次重试前收到 (异常, 轮次, 延迟)，供 C1 埋点使用。"""
    mock_fn = AsyncMock(side_effect=[TimeoutError("t1"), TimeoutError("t2"), "ok"])
    calls: list[tuple[Exception, int, float]] = []
    decorated = with_retry(max_retries=3, on_retry=lambda e, a, d: calls.append((e, a, d)))(mock_fn)

    with patch("app.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await decorated()

    assert result == "ok"
    assert len(calls) == 2
    assert isinstance(calls[0][0], TimeoutError)
    assert calls[0][1] == 0  # 第一次失败的轮次
    assert calls[1][1] == 1


@pytest.mark.asyncio
async def test_on_retry_callback_error_is_swallowed():
    """埋点回调自身异常不影响重试主流程。"""
    mock_fn = AsyncMock(side_effect=[TimeoutError("t1"), "ok"])

    def bad_callback(exc, attempt, delay):
        raise RuntimeError("callback boom")

    decorated = with_retry(max_retries=3, on_retry=bad_callback)(mock_fn)

    with patch("app.llm.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await decorated()

    assert result == "ok"
    assert mock_fn.call_count == 2
