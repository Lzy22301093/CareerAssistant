"""Memory Service（v3）— 跨会话长期记忆（career_profile / preferences）。

设计（按 architecture-v3 §3.3）：
- 存储与读写是纯机制（本模块，代码实现）
- 维护分两级：
  1. 规则合并（本模块）：上传简历/新画像 → 去重合并进 career_profile（零 LLM）
  2. consolidate 提炼（后续里程碑）：LLM 一步提炼缺口/偏好，输出经代码校验
- 全部写操作前做字段校验，防止脏数据
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.database import SessionLocal
from app.models.orm import CareerProfile, UserPreference

logger = logging.getLogger(__name__)

# career_profile 允许的顶层字段（白名单，防 LLM/外部乱写）
_ALLOWED_FIELDS = {
    "name", "email", "phone", "location", "summary",
    "skills", "experience", "projects", "education", "certifications",
    "preferences", "gaps", "target_roles",
}


class MemoryService:
    """跨会话记忆仓库：注入 / 查询 / 规则合并。"""

    def __init__(self, db_factory=None) -> None:
        self._db_factory = db_factory or SessionLocal

    def _get_db(self) -> DBSession:
        return self._db_factory()

    # === 读取 ===

    def get_profile(self, user_id: int) -> dict[str, Any] | None:
        """读取用户的长期求职档案，无则返回 None。"""
        db = self._get_db()
        try:
            row = db.query(CareerProfile).filter(CareerProfile.user_id == user_id).first()
            if row is None:
                return None
            return json.loads(row.profile_json)
        except Exception as e:
            logger.error(f"Memory: 读取档案失败 user={user_id}: {e}")
            return None
        finally:
            db.close()

    def get_preferences(self, user_id: int) -> dict[str, Any]:
        """读取用户偏好（user_preferences 表）。"""
        db = self._get_db()
        try:
            row = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
            if row is None:
                return {}
            prefs: dict[str, Any] = {}
            if row.preferred_template:
                prefs["preferred_template"] = row.preferred_template
            if row.resume_style:
                prefs["resume_style"] = row.resume_style
            if row.job_preferences_json:
                try:
                    prefs["job_preferences"] = json.loads(row.job_preferences_json)
                except json.JSONDecodeError:
                    pass
            if row.extra_json:
                try:
                    prefs["extra"] = json.loads(row.extra_json)
                except json.JSONDecodeError:
                    pass
            return prefs
        except Exception as e:
            logger.error(f"Memory: 读取偏好失败 user={user_id}: {e}")
            return {}
        finally:
            db.close()

    def build_summary(self, user_id: int) -> dict[str, Any]:
        """构造注入 GraphState 的记忆摘要（档案 + 偏好）。"""
        profile = self.get_profile(user_id) or {}
        return {
            "profile": profile,
            "preferences": self.get_preferences(user_id),
        }

    # === 规则合并 ===

    def upsert_profile(self, user_id: int, new_profile: dict[str, Any], source: str = "resume") -> dict[str, Any]:
        """把新画像规则合并进长期档案（去重、保留旧数据），返回合并后档案。

        - skills：集合合并（保留顺序）
        - experience/projects：按 (company+title) / name 去重合并，新材料在前
        - 其余字段：新材料非空时覆盖
        """
        cleaned = {k: v for k, v in (new_profile or {}).items() if k in _ALLOWED_FIELDS}
        if not cleaned:
            return {}

        existing = self.get_profile(user_id) or {}
        merged = self._merge(existing, cleaned)

        db = self._get_db()
        try:
            row = db.query(CareerProfile).filter(CareerProfile.user_id == user_id).first()
            if row is None:
                row = CareerProfile(user_id=user_id, profile_json=json.dumps(merged, ensure_ascii=False), source=source)
                db.add(row)
            else:
                row.profile_json = json.dumps(merged, ensure_ascii=False)
                row.source = source
            db.commit()
            logger.info(f"Memory: 已合并档案 user={user_id} (source={source})")
        except Exception as e:
            db.rollback()
            logger.error(f"Memory: 合并档案失败 user={user_id}: {e}")
        finally:
            db.close()
        return merged

    # === 内部 ===

    @staticmethod
    def _merge(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        out = dict(existing)

        # skills：集合合并
        old_skills = list(existing.get("skills") or [])
        new_skills = list(new.get("skills") or [])
        if new_skills:
            seen = set(str(s).strip().lower() for s in old_skills)
            for s in new_skills:
                key = str(s).strip().lower()
                if key and key not in seen:
                    old_skills.append(s)
                    seen.add(key)
            out["skills"] = old_skills

        # experience：按 company+title 去重，新材料在前
        out["experience"] = MemoryService._merge_by_key(
            existing.get("experience"), new.get("experience"),
            key_fn=lambda e: f"{e.get('company', '')}|{e.get('title', '')}",
        )

        # projects：按 name 去重
        out["projects"] = MemoryService._merge_by_key(
            existing.get("projects"), new.get("projects"),
            key_fn=lambda p: str(p.get("name", "")),
        )

        # 标量/其他列表：新材料非空时覆盖
        for field in ("name", "email", "phone", "location", "summary", "education", "certifications", "preferences", "gaps", "target_roles"):
            if field in new and new[field]:
                out[field] = new[field]

        return out

    @staticmethod
    def _merge_by_key(old_items: Any, new_items: Any, key_fn) -> list[dict]:
        if not isinstance(old_items, list):
            old_items = []
        if not isinstance(new_items, list):
            return list(old_items)
        merged = list(old_items)
        seen = {key_fn(d) for d in merged if isinstance(d, dict)}
        for item in new_items:
            if not isinstance(item, dict):
                continue
            key = key_fn(item)
            if key and key not in seen:
                merged.insert(0, item)
                seen.add(key)
        return merged
