"""Tests for the retry decorator."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.llm.retry import with_retry


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
