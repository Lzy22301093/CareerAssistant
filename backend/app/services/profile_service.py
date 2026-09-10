"""ProfileService — 个人画像/知识库条目与证据的 CRUD（阶段0 指令0-3）。

方法接收 db（Session），便于在测试中用 SQLite 注入。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import ProfileEvidence, ProfileItem
from app.models.schemas import EvidenceCreate, ProfileItemCreate, ProfileItemUpdate

ALLOWED_CATEGORIES = {
    "basic_info", "education", "experience", "skill", "target", "soft",
    "interview_feedback", "award", "social",
}
ALLOWED_STATUS = {"confirmed", "suggested", "rejected", "archived"}
ALLOWED_VISIBILITY = {"resume", "interview", "resume_interview", "private"}
ALLOWED_ITEM_TYPES = {"fact", "suggestion", "feedback"}
ALLOWED_SOURCE_TYPES = {"user_input", "resume", "interview_report"}
SOURCE_TYPE_USER_INPUT = "user_input"


def aggregate_confirmed_profile(items: list[ProfileItem]) -> dict[str, Any]:
    """把已确认画像条目聚合成"profile 形态"字典（供 agent 上下文使用）。

    纯函数，便于测试。只取 status=confirmed 的条目；按 category 归并到
    下游 agent 认识的字段（name/email/.../skills/experience/education/summary/target_roles/gaps）。
    """
    ctx: dict[str, Any] = {}
    for item in items:
        if item.status != "confirmed":
            continue
        content = item.content or ""
        if item.category == "basic_info":
            title = item.title or ""
            if title == "姓名":
                ctx["name"] = content
            elif title == "邮箱":
                ctx["email"] = content
            elif title == "电话":
                ctx["phone"] = content
            elif title == "所在地":
                ctx["location"] = content
            else:
                ctx.setdefault("basic_info", []).append(f"{title}: {content}".strip())
        elif item.category == "soft":
            if content:
                ctx["summary"] = "\n".join([x for x in (ctx.get("summary", ""), content) if x])
            ctx.setdefault("soft", []).append(f"{item.title}: {content}".strip())
        elif item.category == "skill":
            ctx.setdefault("skills", []).append(f"{item.title}: {content}".strip() if content else item.title)
        elif item.category == "experience":
            ctx.setdefault("experience", []).append({"title": item.title, "content": content})
        elif item.category == "education":
            ctx.setdefault("education", []).append(f"{item.title}: {content}".strip() if content else item.title)
        elif item.category == "target":
            ctx.setdefault("target_roles", []).append(item.content or item.title)
        elif item.category == "award":
            ctx.setdefault("certifications", []).append(
                f"{item.title}: {content}".strip() if content else item.title
            )
        elif item.category == "social":
            ctx.setdefault("social", []).append(f"{item.title}: {content}".strip() if content else item.title)
        elif item.category == "interview_feedback":
            ctx.setdefault("gaps", []).append(f"{item.title}: {content}".strip() if content else item.title)
    return ctx


def build_profile_context(db: DBSession, user_id: int) -> dict[str, Any]:
    """读取用户已确认的画像条目并聚合成 profile 上下文（供 graph_state.profile 覆盖/增强）。"""
    items = (
        db.query(ProfileItem)
        .filter(ProfileItem.user_id == user_id, ProfileItem.status == "confirmed")
        .all()
    )
    return aggregate_confirmed_profile(items)


class ProfileServiceError(ValueError):
    """业务校验错误。"""


def _ensure(value: str | None, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise ProfileServiceError(f"{label} 非法: {value!r}，允许 {sorted(allowed)}")
    return value


class ProfileService:
    """画像条目 + 证据。"""

    def list_items(
        self,
        db: DBSession,
        user_id: int,
        category: str | None = None,
        status: str | None = None,
    ) -> list[ProfileItem]:
        q = db.query(ProfileItem).filter(ProfileItem.user_id == user_id)
        if category:
            q = q.filter(ProfileItem.category == category)
        if status:
            q = q.filter(ProfileItem.status == status)
        return q.order_by(ProfileItem.sort_order.asc(), ProfileItem.id.asc()).all()

    def get_item(self, db: DBSession, user_id: int, item_id: int) -> ProfileItem:
        item = db.query(ProfileItem).filter(ProfileItem.id == item_id, ProfileItem.user_id == user_id).first()
        if item is None:
            raise ProfileServiceError("画像条目不存在")
        return item

    def create_item(self, db: DBSession, user_id: int, data: ProfileItemCreate) -> ProfileItem:
        _ensure(data.category, ALLOWED_CATEGORIES, "category")
        _ensure(data.status, ALLOWED_STATUS, "status")
        _ensure(data.visibility, ALLOWED_VISIBILITY, "visibility")
        _ensure(data.item_type, ALLOWED_ITEM_TYPES, "item_type")
        item = ProfileItem(
            user_id=user_id,
            category=data.category,
            title=data.title,
            content=data.content,
            item_type=data.item_type,
            confidence=data.confidence,
            visibility=data.visibility,
            status=data.status,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def update_item(self, db: DBSession, user_id: int, item_id: int, data: ProfileItemUpdate) -> ProfileItem:
        item = self.get_item(db, user_id, item_id)
        updates = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in updates.items():
            if field in ("category", "status", "visibility", "item_type"):
                allowed = {
                    "category": ALLOWED_CATEGORIES,
                    "status": ALLOWED_STATUS,
                    "visibility": ALLOWED_VISIBILITY,
                    "item_type": ALLOWED_ITEM_TYPES,
                }[field]
                _ensure(value, allowed, field)
            setattr(item, field, value)
        db.commit()
        db.refresh(item)
        return item

    def change_status(self, db: DBSession, user_id: int, item_id: int, status: str) -> ProfileItem:
        _ensure(status, ALLOWED_STATUS, "status")
        item = self.get_item(db, user_id, item_id)
        item.status = status
        db.commit()
        db.refresh(item)
        return item

    def delete_item(self, db: DBSession, user_id: int, item_id: int) -> None:
        item = self.get_item(db, user_id, item_id)
        db.delete(item)
        db.commit()

    def upsert_item(self, db: DBSession, user_id: int, data: ProfileItemCreate) -> tuple[ProfileItem, bool]:
        """按 (category, title) 幂等写入一条 confirmed 画像条目。

        存在则更新 content/status/visibility，返回 (item, False)；不存在则新建，
        返回 (item, True)。供"结构化画像向导"重复保存时保持一致（不产生重复条目）。
        """
        _ensure(data.category, ALLOWED_CATEGORIES, "category")
        _ensure(data.status, ALLOWED_STATUS, "status")
        _ensure(data.visibility, ALLOWED_VISIBILITY, "visibility")
        _ensure(data.item_type, ALLOWED_ITEM_TYPES, "item_type")
        existing = (
            db.query(ProfileItem)
            .filter(
                ProfileItem.user_id == user_id,
                ProfileItem.category == data.category,
                ProfileItem.title == data.title,
            )
            .order_by(ProfileItem.id.asc())
            .first()
        )
        if existing is not None:
            existing.content = data.content
            existing.item_type = data.item_type
            existing.status = data.status
            existing.visibility = data.visibility
            existing.confidence = data.confidence
            db.commit()
            db.refresh(existing)
            return existing, False
        item = self.create_item(db, user_id, data)
        return item, True

    def list_by_category(self, db: DBSession, user_id: int, category: str) -> list[ProfileItem]:
        return (
            db.query(ProfileItem)
            .filter(ProfileItem.user_id == user_id, ProfileItem.category == category)
            .order_by(ProfileItem.sort_order.asc(), ProfileItem.id.asc())
            .all()
        )

    def add_evidence(self, db: DBSession, user_id: int, item_id: int, data: EvidenceCreate) -> ProfileEvidence:
        _ensure(data.source_type, ALLOWED_SOURCE_TYPES, "source_type")
        item = self.get_item(db, user_id, item_id)
        ev = ProfileEvidence(
            profile_item_id=item.id,
            source_type=data.source_type,
            source_id=data.source_id,
            quote=data.quote,
            verified_by_user=data.verified_by_user,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        return ev

    def category_summary(self, db: DBSession, user_id: int) -> list[dict[str, Any]]:
        """按分类聚合条目数量（供节点星座图/导航）。"""
        rows = (
            db.query(ProfileItem.category, ProfileItem.status)
            .filter(ProfileItem.user_id == user_id)
            .all()
        )
        summary: dict[str, dict[str, Any]] = {}
        for category, status in rows:
            entry = summary.setdefault(category, {"category": category, "count": 0, "confirmed": 0, "suggested": 0})
            entry["count"] += 1
            if status == "confirmed":
                entry["confirmed"] += 1
            elif status == "suggested":
                entry["suggested"] += 1
        return sorted(summary.values(), key=lambda e: e["category"])
