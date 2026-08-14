"""Preference Service 测试。"""

from __future__ import annotations

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.orm import User
from app.services.preference_service import PreferenceService


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
def user_id(db_factory):
    """创建测试用户并返回 user_id。"""
    db = db_factory()
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed",
    )
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    return user_id


@pytest.fixture
def pref_service(db_factory):
    """创建 PreferenceService 实例。"""
    return PreferenceService(db_factory=db_factory)


# === 测试用例 ===


class TestPreferenceService:
    def test_get_default_preferences(self, pref_service: PreferenceService, user_id: int):
        """获取默认偏好。"""
        prefs = pref_service.get_preferences(user_id)
        assert prefs["preferred_template"] == "modern"
        assert prefs["resume_style"] == "concise"
        assert prefs["job_preferences"] == {}

    def test_update_template(self, pref_service: PreferenceService, user_id: int):
        """更新模板偏好。"""
        prefs = pref_service.update_preferences(user_id, {"preferred_template": "classic"})
        assert prefs["preferred_template"] == "classic"

    def test_update_resume_style(self, pref_service: PreferenceService, user_id: int):
        """更新简历风格。"""
        prefs = pref_service.update_preferences(user_id, {"resume_style": "detailed"})
        assert prefs["resume_style"] == "detailed"

    def test_update_job_preferences(self, pref_service: PreferenceService, user_id: int):
        """更新求职偏好。"""
        job_prefs = {"industry": "互联网", "role": "后端工程师", "salary": "30-50k"}
        prefs = pref_service.update_preferences(user_id, {"job_preferences": job_prefs})
        assert prefs["job_preferences"]["industry"] == "互联网"
        assert prefs["job_preferences"]["role"] == "后端工程师"

    def test_update_extra(self, pref_service: PreferenceService, user_id: int):
        """更新自定义偏好。"""
        extra = {"language": "zh", "theme": "dark"}
        prefs = pref_service.update_preferences(user_id, {"extra": extra})
        assert prefs["extra"]["language"] == "zh"

    def test_get_template_preference(self, pref_service: PreferenceService, user_id: int):
        """获取模板偏好。"""
        assert pref_service.get_template_preference(user_id) == "modern"
        pref_service.update_preferences(user_id, {"preferred_template": "creative"})
        assert pref_service.get_template_preference(user_id) == "creative"

    def test_get_job_preferences(self, pref_service: PreferenceService, user_id: int):
        """获取求职偏好。"""
        job_prefs = {"industry": "金融"}
        pref_service.update_preferences(user_id, {"job_preferences": job_prefs})
        result = pref_service.get_job_preferences(user_id)
        assert result["industry"] == "金融"

    def test_update_preserves_other_fields(self, pref_service: PreferenceService, user_id: int):
        """更新一个字段不影响其他字段。"""
        pref_service.update_preferences(user_id, {
            "preferred_template": "classic",
            "resume_style": "detailed",
        })
        pref_service.update_preferences(user_id, {"preferred_template": "modern"})
        prefs = pref_service.get_preferences(user_id)
        assert prefs["preferred_template"] == "modern"
        assert prefs["resume_style"] == "detailed"
