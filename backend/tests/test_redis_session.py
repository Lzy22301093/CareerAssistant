"""Tests for Redis session store (using memory fallback mode)."""

import pytest

from app.models.redis_session import MemorySessionStore


@pytest.fixture
def store():
    """Create a fresh memory session store for each test."""
    return MemorySessionStore()


def test_create_and_get_session(store: MemorySessionStore):
    """Test creating and retrieving a session."""
    session_id = "test-session-001"
    data = {"stage": "init", "jd_text": "Test JD"}

    created = store.create_session(session_id, data)
    assert created["session_id"] == session_id
    assert created["stage"] == "init"
    assert "created_at" in created
    assert "updated_at" in created
    assert created["messages"] == []

    # Retrieve
    retrieved = store.get_session(session_id)
    assert retrieved is not None
    assert retrieved["session_id"] == session_id
    assert retrieved["stage"] == "init"


def test_update_session(store: MemorySessionStore):
    """Test updating session data."""
    session_id = "test-session-002"
    store.create_session(session_id, {"stage": "init"})

    updated = store.update_session(session_id, {"stage": "has_jd"})
    assert updated is not None
    assert updated["stage"] == "has_jd"

    # Verify update persisted
    retrieved = store.get_session(session_id)
    assert retrieved["stage"] == "has_jd"


def test_update_nonexistent_session(store: MemorySessionStore):
    """Test updating a session that doesn't exist."""
    result = store.update_session("nonexistent", {"stage": "init"})
    assert result is None


def test_delete_session(store: MemorySessionStore):
    """Test deleting a session."""
    session_id = "test-session-003"
    store.create_session(session_id)

    assert store.delete_session(session_id) is True
    assert store.get_session(session_id) is None


def test_delete_nonexistent_session(store: MemorySessionStore):
    """Test deleting a session that doesn't exist."""
    assert store.delete_session("nonexistent") is False


def test_append_message(store: MemorySessionStore):
    """Test appending messages to a session."""
    session_id = "test-session-004"
    store.create_session(session_id)

    # Append first message
    msg1 = {"role": "user", "content": "Hello"}
    assert store.append_message(session_id, msg1) is True

    # Append second message
    msg2 = {"role": "assistant", "content": "Hi there!"}
    assert store.append_message(session_id, msg2) is True

    # Verify messages
    session = store.get_session(session_id)
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"
    assert "timestamp" in session["messages"][0]


def test_append_message_nonexistent(store: MemorySessionStore):
    """Test appending to a nonexistent session."""
    result = store.append_message("nonexistent", {"role": "user", "content": "test"})
    assert result is False


def test_get_nonexistent(store: MemorySessionStore):
    """Test getting a nonexistent session."""
    result = store.get_session("nonexistent")
    assert result is None


def test_list_sessions(store: MemorySessionStore):
    """Test listing all sessions."""
    store.create_session("session-1")
    store.create_session("session-2")
    store.create_session("session-3")

    sessions = store.list_sessions()
    assert len(sessions) == 3
    assert "session-1" in sessions
    assert "session-2" in sessions
    assert "session-3" in sessions
