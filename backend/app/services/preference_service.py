"""Preference Service — 用户偏好管理（Long-term Memory）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.database import SessionLocal
from app.models.orm import UserPreference

logger = logging.getLogger(__name__)


class PreferenceService:
    """用户偏好服务。"""

    def __init__(self, db_factory=None) -> None:
        self._db_factory = db_factory or SessionLocal

    def _get_db(self) -> DBSession:
        return self._db_factory()

    def get_preferences(self, user_id: int) -> dict[str, Any]:
        """获取用户偏好，不存在则返回默认值。"""
        db = self._get_db()
        try:
            pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
            if not pref:
                return self._default_preferences()
            return self._preference_to_dict(pref)
        finally:
            db.close()

    def update_preferences(self, user_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """更新用户偏好。"""
        db = self._get_db()
        try:
            pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
            if not pref:
                pref = UserPreference(user_id=user_id)
                db.add(pref)

            if "preferred_template" in data:
                pref.preferred_template = data["preferred_template"]
            if "resume_style" in data:
                pref.resume_style = data["resume_style"]
            if "job_preferences" in data:
                pref.job_preferences_json = json.dumps(data["job_preferences"], ensure_ascii=False)
            if "extra" in data:
                pref.extra_json = json.dumps(data["extra"], ensure_ascii=False)

            db.commit()
            db.refresh(pref)
            logger.info(f"Updated preferences for user {user_id}")
            return self._preference_to_dict(pref)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update preferences: {e}")
            raise
        finally:
            db.close()

    def get_template_preference(self, user_id: int) -> str:
        """获取用户偏好的简历模板。"""
        prefs = self.get_preferences(user_id)
        return prefs.get("preferred_template", "modern")

    def get_job_preferences(self, user_id: int) -> dict[str, Any]:
        """获取用户求职偏好。"""
        prefs = self.get_preferences(user_id)
        return prefs.get("job_preferences", {})

    @staticmethod
    def _default_preferences() -> dict[str, Any]:
        """默认偏好。"""
        return {
            "preferred_template": "modern",
            "resume_style": "concise",
            "job_preferences": {},
            "extra": {},
        }

    @staticmethod
    def _preference_to_dict(pref: UserPreference) -> dict[str, Any]:
        """将 ORM 对象转换为字典。"""
        return {
            "preferred_template": pref.preferred_template or "modern",
            "resume_style": pref.resume_style or "concise",
            "job_preferences": json.loads(pref.job_preferences_json) if pref.job_preferences_json else {},
            "extra": json.loads(pref.extra_json) if pref.extra_json else {},
            "updated_at": pref.updated_at.isoformat() if pref.updated_at else None,
        }
