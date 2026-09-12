"""SoftInfoService — 软性信息（阶段3 指令3-2）。

软性信息 = 性格特点 / 职业愿景 / 不感兴趣的方向 / 自我评价。
- generate_soft_info: 依已确认画像用 LLM 生成软性信息建议（自我评价可 AI 生成）。
- save_soft_info: 把填好的软性信息写成 category=soft 的 confirmed 画像条目。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import ProfileItem
from app.models.schemas import EvidenceCreate, ProfileItemCreate, SoftInfoSaveRequest, SoftInfoSuggestion
from app.services.profile_service import ProfileService, build_profile_context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是求职简历润色助手。请根据候选人的个人画像，用温柔、真诚、有温度的中文帮他补全软性信息。\n"
    "输出四个字段：personality（性格特点）、vision（职业愿景）、disinterested（不感兴趣的方向）、"
    "self_eval（自我评价）。\n"
    "要求：结合画像中的经历/技能/优点，措辞具体、真诚、不浮夸；自我评价 2~3 句；"
    "不感兴趣的方向写清楚但语气温和。\n"
    "只输出 JSON。JSON 结构："
    '{"personality":"...","vision":"...","disinterested":"...","self_eval":"..."}'
)

# 字段 → 画像条目标题（供写入 soft 分类）
FIELD_TO_LABEL = {
    "personality": "性格特点",
    "vision": "职业愿景",
    "disinterested": "不感兴趣的方向",
    "self_eval": "自我评价",
}


class SoftInfoError(ValueError):
    """软性信息业务错误。"""


class SoftInfoService:
    """软性信息生成 + 保存。"""

    def __init__(self) -> None:
        self._profile = ProfileService()

    async def generate_soft_info(
        self,
        db: DBSession,
        user_id: int,
        llm: Any,
    ) -> SoftInfoSuggestion:
        """基于已确认画像生成软性信息建议。"""
        profile_ctx = build_profile_context(db, user_id)
        if not profile_ctx:
            raise SoftInfoError("暂无已确认画像，请先到个人画像完善并确认条目")

        from app.llm.structured import ainvoke_json_with_schema

        user_content = (
            "候选人画像：\n"
            f"{_format_profile(profile_ctx)}\n\n"
            "请帮我补全软性信息。"
        )
        result = await ainvoke_json_with_schema(
            llm,
            system_prompt=SYSTEM_PROMPT,
            user_content=user_content,
            schema=SoftInfoSuggestion,
            max_attempts=2,
            temperature=0.7,
            max_tokens=1024,
        )
        return result

    def save_soft_info(
        self,
        db: DBSession,
        user_id: int,
        payload: SoftInfoSaveRequest,
    ) -> list[ProfileItem]:
        """把软性信息字段写成 category=soft 的 confirmed 画像条目（幂等，覆盖同名非删除项）。"""
        saved: list[ProfileItem] = []
        for field, label in FIELD_TO_LABEL.items():
            value = (getattr(payload, field) or "").strip()
            if not value:
                continue
            saved.append(self._upsert_soft_item(db, user_id, label, value))
        if not saved:
            raise SoftInfoError("至少填写一项软性信息")
        return saved

    def _upsert_soft_item(self, db: DBSession, user_id: int, title: str, value: str) -> ProfileItem:
        """在 user 下 upsert 一条指定标题的 soft 条目（存在则更新内容，不存在则新建 + 证据）。"""
        existing = (
            db.query(ProfileItem)
            .filter(
                ProfileItem.user_id == user_id,
                ProfileItem.category == "soft",
                ProfileItem.title == title,
            )
            .order_by(ProfileItem.id.asc())
            .first()
        )
        if existing:
            existing.content = value
            existing.status = "confirmed"
            db.commit()
            db.refresh(existing)
            return existing

        item = self._profile.create_item(
            db,
            user_id,
            ProfileItemCreate(
                category="soft",
                title=title,
                content=value,
                item_type="fact",
                status="confirmed",
                visibility="resume_interview",
            ),
        )
        self._profile.add_evidence(
            db,
            user_id,
            item.id,
            EvidenceCreate(
                source_type="user_input",
                quote=f"软性信息·{title}：{value}",
                verified_by_user=True,
            ),
        )
        return item


def _format_profile(ctx: dict[str, Any]) -> str:
    parts: list[str] = []
    if ctx.get("name"):
        parts.append(f"姓名：{ctx['name']}")
    if ctx.get("summary"):
        parts.append(f"个人简介：{ctx['summary']}")
    if ctx.get("skills"):
        parts.append(f"技能：{', '.join(str(s) for s in ctx['skills'])}")
    if ctx.get("education"):
        parts.append(f"教育经历：{'; '.join(str(e) for e in ctx['education'])}")
    if ctx.get("experience"):
        parts.append(
            "项目/工作经历：\n" + "\n".join(f"- {e}" for e in ctx["experience"])
        )
    if ctx.get("certifications"):
        parts.append(f"证书/奖项：{'; '.join(str(c) for c in ctx['certifications'])}")
    if ctx.get("social"):
        parts.append(f"社交账号：{'; '.join(str(s) for s in ctx['social'])}")
    if ctx.get("target_roles"):
        parts.append(f"目标方向：{', '.join(str(t) for t in ctx['target_roles'])}")
    return "\n".join(parts)
