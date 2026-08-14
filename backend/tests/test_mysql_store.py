"""MySQL Session Store 测试 — 使用 SQLite 内存数据库。"""

from __future__ import annotations

import json
import pytest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.mysql_store import MySQLSessionStore
from app.models.orm import AnalysisSession


@pytest.fixture
def db_engine():
    """创建 SQLite 内存数据库引擎。"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_factory(db_engine):
    """创建数据库会话工厂。"""
    TestSession = sessionmaker(bind=db_engine)
    return TestSession


@pytest.fixture
def store(db_factory):
    """创建 MySQLSessionStore 实例。"""
    return MySQLSessionStore(db_factory=db_factory)


# === 测试用例 ===


class TestMySQLSessionStore:
    @pytest.mark.asyncio
    async def test_create_and_get(self, store: MySQLSessionStore):
        """创建并获取会话。"""
        data = {
            "stage": "init",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        await store.create("test-session-1", data)
        result = await store.get("test-session-1")
        assert result is not None
        assert result["session_id"] == "test-session-1"
        assert result["stage"] == "init"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store: MySQLSessionStore):
        """获取不存在的会话返回 None。"""
        result = await store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_stage(self, store: MySQLSessionStore):
        """更新会话阶段。"""
        data = {
            "stage": "init",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        await store.create("test-session-2", data)
        await store.update("test-session-2", {"stage": "has_jd"})
        result = await store.get("test-session-2")
        assert result["stage"] == "has_jd"

    @pytest.mark.asyncio
    async def test_update_jd_analysis(self, store: MySQLSessionStore):
        """更新 JD 分析结果。"""
        data = {
            "stage": "init",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        await store.create("test-session-3", data)
        jd = {"job_title": "Python 工程师", "company": "示例科技"}
        await store.update("test-session-3", {"jd_analysis": jd})
        result = await store.get("test-session-3")
        assert result["jd_analysis"]["job_title"] == "Python 工程师"

    @pytest.mark.asyncio
    async def test_update_resume_content(self, store: MySQLSessionStore):
        """更新简历内容（创建版本）。"""
        data = {
            "stage": "init",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        await store.create("test-session-4", data)
        resume = {"sections": [{"title": "技能", "content": "Python"}]}
        await store.update("test-session-4", {"resume_content": resume})
        result = await store.get("test-session-4")
        assert result["resume_content"]["sections"][0]["title"] == "技能"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, store: MySQLSessionStore):
        """更新不存在的会话不报错。"""
        await store.update("nonexistent", {"stage": "init"})
        result = await store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, store: MySQLSessionStore):
        """删除会话。"""
        data = {
            "stage": "init",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        await store.create("test-session-5", data)
        deleted = await store.delete("test-session-5")
        assert deleted is True
        result = await store.get("test-session-5")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store: MySQLSessionStore):
        """删除不存在的会话返回 False。"""
        deleted = await store.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_exists(self, store: MySQLSessionStore):
        """检查会话是否存在。"""
        assert await store.exists("test-session-6") is False
        data = {
            "stage": "init",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        await store.create("test-session-6", data)
        assert await store.exists("test-session-6") is True

    @pytest.mark.asyncio
    async def test_uploaded_files(self, store: MySQLSessionStore):
        """上传文件记录。"""
        data = {
            "stage": "init",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        await store.create("test-session-7", data)
        files = [
            {"filename": "jd.txt", "file_type": "txt", "file_path": "/uploads/jd.txt", "file_size": 100},
            {"filename": "resume.pdf", "file_type": "pdf", "file_path": "/uploads/resume.pdf", "file_size": 200},
        ]
        await store.update("test-session-7", {"uploaded_files": files})
        result = await store.get("test-session-7")
        assert len(result["uploaded_files"]) == 2
        assert result["uploaded_files"][0]["filename"] == "jd.txt"
