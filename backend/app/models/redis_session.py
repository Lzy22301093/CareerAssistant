"""Redis session store with memory fallback."""

import json
import logging
from datetime import datetime
from typing import Any

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class MemorySessionStore:
    """In-memory session store (fallback when Redis is unavailable)."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(self, session_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new session."""
        session_data = data or {}
        session_data["session_id"] = session_id
        session_data["created_at"] = datetime.now().isoformat()
        session_data["updated_at"] = datetime.now().isoformat()
        session_data["messages"] = []
        self._sessions[session_id] = session_data
        return session_data

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def update_session(self, session_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update session data."""
        if session_id not in self._sessions:
            return None
        self._sessions[session_id].update(data)
        self._sessions[session_id]["updated_at"] = datetime.now().isoformat()
        return self._sessions[session_id]

    def delete_session(self, session_id: str) -> bool:
        """Delete session by ID."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def append_message(self, session_id: str, message: dict[str, Any]) -> bool:
        """Append a message to session conversation."""
        if session_id not in self._sessions:
            return False
        if "messages" not in self._sessions[session_id]:
            self._sessions[session_id]["messages"] = []
        message["timestamp"] = datetime.now().isoformat()
        self._sessions[session_id]["messages"].append(message)
        self._sessions[session_id]["updated_at"] = datetime.now().isoformat()
        return True

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        return list(self._sessions.keys())


class RedisSessionStore:
    """Redis-backed session store."""

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client
        self._prefix = "session:"
        self._ttl = 86400 * 7  # 7 days

    def _key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self._prefix}{session_id}"

    def create_session(self, session_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new session in Redis."""
        session_data = data or {}
        session_data["session_id"] = session_id
        session_data["created_at"] = datetime.now().isoformat()
        session_data["updated_at"] = datetime.now().isoformat()
        session_data["messages"] = []
        self._redis.setex(self._key(session_id), self._ttl, json.dumps(session_data))
        return session_data

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session from Redis."""
        data = self._redis.get(self._key(session_id))
        if data is None:
            return None
        return json.loads(data)

    def update_session(self, session_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update session in Redis."""
        existing = self.get_session(session_id)
        if existing is None:
            return None
        existing.update(data)
        existing["updated_at"] = datetime.now().isoformat()
        self._redis.setex(self._key(session_id), self._ttl, json.dumps(existing))
        return existing

    def delete_session(self, session_id: str) -> bool:
        """Delete session from Redis."""
        return bool(self._redis.delete(self._key(session_id)))

    def append_message(self, session_id: str, message: dict[str, Any]) -> bool:
        """Append a message to session conversation in Redis."""
        existing = self.get_session(session_id)
        if existing is None:
            return False
        if "messages" not in existing:
            existing["messages"] = []
        message["timestamp"] = datetime.now().isoformat()
        existing["messages"].append(message)
        existing["updated_at"] = datetime.now().isoformat()
        self._redis.setex(self._key(session_id), self._ttl, json.dumps(existing))
        return True

    def list_sessions(self) -> list[str]:
        """List all session IDs in Redis."""
        keys = self._redis.keys(f"{self._prefix}*")
        return [key.decode().replace(self._prefix, "") for key in keys]


def create_session_store() -> MemorySessionStore | RedisSessionStore:
    """Create session store with automatic fallback.

    Returns Redis store if available, otherwise falls back to memory store.
    """
    try:
        client = redis.from_url(settings.redis_url, decode_responses=False)
        client.ping()
        logger.info("Using Redis session store")
        return RedisSessionStore(client)
    except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
        logger.warning(f"Redis unavailable ({e}), falling back to memory store")
        return MemorySessionStore()


# Global session store instance
session_store = create_session_store()
