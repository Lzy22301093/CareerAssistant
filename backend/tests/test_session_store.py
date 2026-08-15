"""SessionStore 单元测试。"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.session_store import InMemorySessionStore, RedisSessionStore


@pytest.fixture
def memory_store():
    return InMemorySessionStore()


@pytest.fixture
def redis_store():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.exists = AsyncMock(return_value=1)
    return RedisSessionStore(mock_redis), mock_redis


# === InMemorySessionStore ===


class TestInMemorySessionStore:
    async def test_create_and_get(self, memory_store: InMemorySessionStore):
        data = {"session_id": "s1", "stage": "init"}
        await memory_store.create("s1", data)
        result = await memory_store.get("s1")
        assert result == data

    async def test_get_nonexistent(self, memory_store: InMemorySessionStore):
        result = await memory_store.get("nonexistent")
        assert result is None

    async def test_update(self, memory_store: InMemorySessionStore):
        await memory_store.create("s1", {"stage": "init", "messages": []})
        await memory_store.update("s1", {"stage": "has_jd"})
        result = await memory_store.get("s1")
        assert result["stage"] == "has_jd"
        assert result["messages"] == []

    async def test_update_nonexistent(self, memory_store: InMemorySessionStore):
        await memory_store.update("nonexistent", {"stage": "init"})
        result = await memory_store.get("nonexistent")
        assert result is None

    async def test_delete(self, memory_store: InMemorySessionStore):
        await memory_store.create("s1", {"session_id": "s1"})
        deleted = await memory_store.delete("s1")
        assert deleted is True
        assert await memory_store.get("s1") is None

    async def test_delete_nonexistent(self, memory_store: InMemorySessionStore):
        deleted = await memory_store.delete("nonexistent")
        assert deleted is False

    async def test_exists(self, memory_store: InMemorySessionStore):
        assert await memory_store.exists("s1") is False
        await memory_store.create("s1", {"session_id": "s1"})
        assert await memory_store.exists("s1") is True

    async def test_list_sessions(self, memory_store: InMemorySessionStore):
        await memory_store.create("s1", {"session_id": "s1"})
        await memory_store.create("s2", {"session_id": "s2"})
        ids = await memory_store.list_sessions()
        assert sorted(ids) == ["s1", "s2"]

    async def test_list_sessions_empty(self, memory_store: InMemorySessionStore):
        assert await memory_store.list_sessions() == []


# === RedisSessionStore ===


class TestRedisSessionStore:
    async def test_create(self, redis_store):
        store, mock_redis = redis_store
        data = {"session_id": "s1", "stage": "init"}
        await store.create("s1", data)
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "session:s1"
        assert json.loads(call_args[0][1]) == data

    async def test_get(self, redis_store):
        store, mock_redis = redis_store
        data = {"session_id": "s1", "stage": "init"}
        mock_redis.get = AsyncMock(return_value=json.dumps(data))
        result = await store.get("s1")
        assert result == data

    async def test_get_nonexistent(self, redis_store):
        store, mock_redis = redis_store
        mock_redis.get = AsyncMock(return_value=None)
        result = await store.get("nonexistent")
        assert result is None

    async def test_update(self, redis_store):
        store, mock_redis = redis_store
        existing = {"session_id": "s1", "stage": "init", "messages": []}
        mock_redis.get = AsyncMock(return_value=json.dumps(existing))
        await store.update("s1", {"stage": "has_jd"})
        mock_redis.set.assert_called_once()
        saved = json.loads(mock_redis.set.call_args[0][1])
        assert saved["stage"] == "has_jd"
        assert saved["messages"] == []

    async def test_delete(self, redis_store):
        store, mock_redis = redis_store
        mock_redis.delete = AsyncMock(return_value=1)
        result = await store.delete("s1")
        assert result is True
        mock_redis.delete.assert_called_once_with("session:s1")

    async def test_delete_nonexistent(self, redis_store):
        store, mock_redis = redis_store
        mock_redis.delete = AsyncMock(return_value=0)
        result = await store.delete("nonexistent")
        assert result is False

    async def test_exists(self, redis_store):
        store, mock_redis = redis_store
        mock_redis.exists = AsyncMock(return_value=1)
        assert await store.exists("s1") is True
        mock_redis.exists = AsyncMock(return_value=0)
        assert await store.exists("s2") is False

    async def test_create_maintains_index(self, redis_store):
        """create 时应把 session_id 加入索引 set。"""
        store, mock_redis = redis_store
        await store.create("s1", {"session_id": "s1"})
        mock_redis.sadd.assert_awaited_once_with("session:index", "s1")

    async def test_delete_removes_index(self, redis_store):
        """delete 时应从索引 set 移除 session_id。"""
        store, mock_redis = redis_store
        await store.delete("s1")
        mock_redis.srem.assert_awaited_once_with("session:index", "s1")

    async def test_list_sessions(self, redis_store):
        store, mock_redis = redis_store
        mock_redis.smembers = AsyncMock(return_value={"s1", "s2"})
        ids = await store.list_sessions()
        assert sorted(ids) == ["s1", "s2"]

    async def test_list_sessions_rebuilds_index_from_keys(self, redis_store):
        """索引为空时（存量会话）用 KEYS 扫描兜底并重建索引。"""
        store, mock_redis = redis_store
        mock_redis.smembers = AsyncMock(return_value=set())
        mock_redis.keys = AsyncMock(return_value=["session:s1", "session:s2", "session:index"])
        ids = await store.list_sessions()
        assert sorted(ids) == ["s1", "s2"]
        mock_redis.sadd.assert_awaited_once_with("session:index", "s1", "s2")
