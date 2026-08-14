"""Exponential backoff retry decorator for LLM calls."""

import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)

# 可安全重试的 HTTP 状态码
_RETRYABLE_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
# 重试无意义的状态码（配置/认证/请求错误，重试只会浪费配额和时间）
_NON_RETRYABLE_HTTP_CODES = {400, 401, 403, 404, 405, 422}


def is_retryable_llm_error(exc: Exception) -> bool:
    """判断 LLM 调用异常是否值得重试。

    规则（优先级从高到低）：
    1. openai SDK 异常类型：RateLimit/连接/超时/5xx → 重试；认证/权限/请求错误 → 不重试
    2. 带 HTTP 状态码的异常按状态码判断
    3. 超时/连接类内置错误 → 重试
    4. 其余未知异常 → 保守重试
    """
    try:
        from openai import (
            APIConnectionError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            InternalServerError,
            PermissionDeniedError,
            RateLimitError,
        )
        # 明确不可重试
        if isinstance(exc, (AuthenticationError, PermissionDeniedError, BadRequestError)):
            return False
        # 明确可重试
        if isinstance(exc, (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)):
            return True
    except ImportError:
        pass

    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status is not None:
        try:
            code = int(status)
        except (TypeError, ValueError):
            code = None
        if code is not None:
            if code in _RETRYABLE_HTTP_CODES:
                return True
            if code in _NON_RETRYABLE_HTTP_CODES:
                return False

    # 超时 / 连接类内置错误默认重试
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return True

    return True


def _rate_limited(exc: Exception) -> bool:
    """判断是否限流（429），用于延长退避。"""
    try:
        from openai import RateLimitError
        if isinstance(exc, RateLimitError):
            return True
    except ImportError:
        pass
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    return status == 429


def _retry_delay(exc: Exception, attempt: int, base_delay: float) -> float:
    """计算本次重试前的等待秒数。

    - 普通错误：指数退避 base_delay * 2^attempt
    - 429 限流：额外延长（10s/20s/30s），并尽量尊重 Retry-After 头
    """
    delay = base_delay * (2 ** attempt)
    if _rate_limited(exc):
        # 尊重 Retry-After 响应头（如果有）
        headers = getattr(exc, "headers", None)
        if isinstance(headers, dict):
            retry_after = headers.get("retry-after")
            if retry_after:
                try:
                    return max(delay, float(retry_after))
                except (TypeError, ValueError):
                    pass
        delay = max(delay, 10.0 * (attempt + 1))
    return delay


def with_retry(max_retries: int = 3, base_delay: float = 1.0, retryable=None):
    """指数退避重试装饰器，用于 LLM 调用。

    Args:
        max_retries: 最大重试次数（不含首次调用）
        base_delay: 基础延迟秒数，实际延迟 = base_delay * 2^attempt
        retryable: 可选判断函数 (Exception) -> bool，
                   返回 False 时立即抛出异常不做重试；
                   不传则所有异常都重试（保持旧行为）。
    """
    if retryable is None:
        retryable = lambda exc: True

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if not retryable(e):
                        logger.warning(
                            f"LLM call failed with non-retryable error "
                            f"(attempt {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        raise
                    if attempt < max_retries:
                        delay = _retry_delay(e, attempt, base_delay)
                        logger.warning(
                            f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {e}, "
                            f"retrying in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
            logger.error(f"LLM call failed after {max_retries + 1} attempts")
            raise last_exception
        return wrapper
    return decorator
