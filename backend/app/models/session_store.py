"""Session store abstraction — 内存 / Redis 两种实现。"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class SessionStore(ABC):
    """会话存储抽象基类。"""

    @abstractmethod
    async def create(self, session_id: str, data: dict[str, Any]) -> None:
        """创建会话。"""

    @abstractmethod
    async def get(self, session_id: str) -> dict[str, Any] | None:
        """获取会话，不存在返回 None。"""

    @abstractmethod
    async def update(self, session_id: str, data: dict[str, Any]) -> None:
        """更新会话（合并到现有数据）。"""

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """删除会话，返回是否存在。"""

    @abstractmethod
    async def exists(self, session_id: str) -> bool:
        """检查会话是否存在。"""


class InMemorySessionStore(SessionStore):
    """内存会话存储（开发 / 测试用）。"""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def create(self, session_id: str, data: dict[str, Any]) -> None:
        self._store[session_id] = data

    async def get(self, session_id: str) -> dict[str, Any] | None:
        return self._store.get(session_id)

    async def update(self, session_id: str, data: dict[str, Any]) -> None:
        if session_id in self._store:
            self._store[session_id].update(data)

    async def delete(self, session_id: str) -> bool:
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False

    async def exists(self, session_id: str) -> bool:
        return session_id in self._store


class RedisSessionStore(SessionStore):
    """Redis 会话存储（生产环境用）。"""

    KEY_PREFIX = "session:"
    DEFAULT_TTL = 86400 * 7  # 7 天过期

    def __init__(self, redis_client: Any, ttl: int = DEFAULT_TTL) -> None:
        self._redis = redis_client
        self._ttl = ttl

    def _key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}{session_id}"

    async def create(self, session_id: str, data: dict[str, Any]) -> None:
        serialized = json.dumps(data, default=str, ensure_ascii=False)
        await self._redis.set(self._key(session_id), serialized, ex=self._ttl)

    async def get(self, session_id: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def update(self, session_id: str, data: dict[str, Any]) -> None:
        existing = await self.get(session_id)
        if existing is None:
            return
        existing.update(data)
        await self.create(session_id, existing)

    async def delete(self, session_id: str) -> bool:
        return await self._redis.delete(self._key(session_id)) > 0

    async def exists(self, session_id: str) -> bool:
        return await self._redis.exists(self._key(session_id)) > 0
