"""Exponential backoff retry decorator for LLM calls."""

import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """指数退避重试装饰器，用于 LLM 调用。

    Args:
        max_retries: 最大重试次数（不含首次调用）
        base_delay: 基础延迟秒数，实际延迟 = base_delay * 2^attempt
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {e}, "
                            f"retrying in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
            logger.error(f"LLM call failed after {max_retries + 1} attempts")
            raise last_exception
        return wrapper
    return decorator
