"""Profile migration: career_profiles.profile_json → item-level ProfileItem + Evidence.

阶段0 指令0-2。核心逻辑放在 service（可被 SQLite 单测覆盖），CLI 脚本薄封装。
迁移规则：
- 顶层白名单字段按 CATEGORY_MAP 分成多个 ProfileItem
- gaps 属于"反馈/建议" → status=suggested, item_type=feedback；其余 → confirmed / fact
- 每个条目生成一条 ProfileEvidence(source_type 根据 career_profiles.source)
- 幂等：同一 user 一旦已存在 ProfileItem，则不再迁移（防止重复）
- 原 career_profiles 表保留，不删除
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import CareerProfile, ProfileEvidence, ProfileItem

# 顶层字段 → 画像分类（实施计划 §4.2 的分类）
CATEGORY_MAP = {
    "name": "basic_info",
    "email": "basic_info",
    "phone": "basic_info",
    "location": "basic_info",
    "summary": "soft",
    "skills": "skill",
    "experience": "experience",
    "projects": "experience",
    "education": "education",
    "certifications": "education",
    "preferences": "target",
    "target_roles": "target",
    "gaps": "interview_feedback",
}

_TITLES = {
    "name": "姓名",
    "email": "邮箱",
    "phone": "电话",
    "location": "所在地",
    "summary": "自我评价",
    "skills": "专业技能",
    "experience": "经历",
    "projects": "项目经历",
    "education": "教育经历",
    "certifications": "证书/资质",
    "preferences": "目标与偏好",
    "target_roles": "目标岗位",
    "gaps": "待补强能力",
}


def _content(key: str, value: Any) -> str:
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(" ".join(f"{k}: {v}" for k, v in item.items() if v))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(value)


def _status_type(key: str) -> tuple[str, str]:
    # gaps 是反馈/建议，其余是事实；对应 item_type=feedback / fact
    if key == "gaps":
        return "suggested", "feedback"
    return "confirmed", "fact"


def _source_for(source: str) -> str:
    return "user_input" if source == "consolidate" else "resume"


def split_profile(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """把一个 profile 拆成多条条目（纯逻辑，便于测试）。"""
    items: list[dict[str, Any]] = []
    for key, value in (profile or {}).items():
        if key not in CATEGORY_MAP:
            continue
        if value in (None, "", [], {}):
            continue
        status, item_type = _status_type(key)
        content = _content(key, value)
        items.append({
            "category": CATEGORY_MAP[key],
            "title": _TITLES.get(key, key),
            "content": content,
            "item_type": item_type,
            "status": status,
            "visibility": "resume_interview",
            "sort_order": 0,
            "_quote": content,
        })
    return items


def plan_migration(db: DBSession) -> list[dict[str, Any]]:
    """生成迁移计划（不写入）。返回 [{'user_id', 'source', 'items': [...]}]。"""
    plan: list[dict[str, Any]] = []
    for row in db.query(CareerProfile).all():
        # 幂等：该 user 已迁移则跳过
        if db.query(ProfileItem).filter(ProfileItem.user_id == row.user_id).count() > 0:
            continue
        try:
            profile = json.loads(row.profile_json)
        except (json.JSONDecodeError, TypeError):
            continue
        items = split_profile(profile)
        if not items:
            continue
        plan.append({"user_id": row.user_id, "source": row.source, "items": items})
    return plan


def apply_migration(db: DBSession) -> list[dict[str, Any]]:
    """执行迁移并落库，返回已迁移计划的摘要。"""
    plan = plan_migration(db)
    for entry in plan:
        for it in entry["items"]:
            item = ProfileItem(
                user_id=entry["user_id"],
                category=it["category"],
                title=it["title"],
                content=it["content"],
                item_type=it["item_type"],
                confidence=1.0,
                visibility=it["visibility"],
                status=it["status"],
                sort_order=it["sort_order"],
            )
            db.add(item)
            db.flush()
            db.add(ProfileEvidence(
                profile_item_id=item.id,
                source_type=_source_for(entry["source"]),
                source_id="legacy_career_profile",
                quote=it["_quote"],
                verified_by_user=False,
            ))
    db.commit()
    return plan
