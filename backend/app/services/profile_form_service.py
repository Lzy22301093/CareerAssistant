"""ProfileFormService — 个人画像分阶段向导（阶段3）。

把 FResume 风格的结构化"个人画像"表单（基本信息 / 教育经历 / 个人奖项 / 社交账号）
写入现有 `profile_items` 表，并保持与下游消费方的一致：

- 写出的条目标题对齐 `profile_service.aggregate_confirmed_profile` 与
  简历生成"从画像导入"共同识别的标题（姓名/邮箱/电话/所在地/性别/自我评价等），
  保证方向推荐 / 软性信息 / 简历生成都能正确复用。
- 采用 upsert（按 category+title 幂等），重复保存不产生重复条目。

basic_info 的字段键 → profile_items.title 映射见 `BASIC_INFO_FIELDS`。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import ProfileItem
from app.models.schemas import (
    EvidenceCreate,
    ProfileEducationEntry,
    ProfileExtraEntry,
    ProfileFormOut,
    ProfileFormSave,
    ProfileItemCreate,
    ProfileSocialEntry,
)
from app.services.profile_service import ProfileService, ProfileServiceError

# 基本信息字段：form 键 → 写入 profile_items 的 title。
# 标题务必与下游 `aggregate_confirmed_profile` / 简历生成导入识别的标题一致。
BASIC_INFO_FIELDS: dict[str, str] = {
    "name": "姓名",
    "phone": "电话",
    "email": "邮箱",
    "location": "所在地",
    "gender": "性别",
    "birthday": "出生日期",
    "nationality": "国籍",
    "hometown": "家乡",
}

# 其他分类兜底（不在分阶段表单里，但知识库仍要能补充）
EXTRA_CATEGORIES = {"experience", "skill", "target", "soft", "interview_feedback"}

# 教育经历内容的书写格式（用于把结构化条目拼成 content，便于检索与复用）
_EDU_LABELS = (
    ("degree", "学历"),
    ("major", "专业"),
    ("courses", "主修课程"),
    ("start", "开始时间"),
    ("end", "结束时间"),
    ("gpa", "GPA"),
)


class ProfileFormError(ValueError):
    """结构化画像表单业务错误。"""


class ProfileFormService:
    """分阶段画像表单读写。"""

    def __init__(self) -> None:
        self._profile = ProfileService()

    def load(self, db: DBSession, user_id: int) -> ProfileFormOut:
        """读取用户已保存的画像表单数据（回显 / 继续编辑）。"""
        basic_info: dict[str, str] = {}
        by_title = {i.title: i for i in self._profile.list_by_category(db, user_id, "basic_info")}
        for form_key, title in BASIC_INFO_FIELDS.items():
            item = by_title.get(title)
            if item and item.content:
                basic_info[form_key] = item.content

        education_items = self._profile.list_by_category(db, user_id, "education")
        education = [self._parse_education(i.title, i.content or "") for i in education_items]

        award_items = self._profile.list_by_category(db, user_id, "award")
        awards: list[str] = []
        for a in award_items:
            if a.content:
                awards.extend([ln.strip() for ln in a.content.splitlines() if ln.strip()])
            elif a.title:
                awards.append(a.title)

        social_items = self._profile.list_by_category(db, user_id, "social")
        social = []
        for s in social_items:
            if s.content:
                social.append(ProfileSocialEntry(platform=s.title, account=s.content))
            elif s.title:
                social.append(ProfileSocialEntry(platform="", account=s.title))

        extra_items = self._profile.list_items(db, user_id)
        extra = [
            ProfileExtraEntry(category=i.category, title=i.title, content=i.content or "")
            for i in extra_items
            if i.category in EXTRA_CATEGORIES
        ]

        return ProfileFormOut(
            basic_info=basic_info,
            education=education,
            awards=awards,
            social=social,
            extra=extra,
        )

    def save(self, db: DBSession, user_id: int, data: ProfileFormSave) -> ProfileFormOut:
        """把分阶段表单写入 profile_items（upsert，幂等），返回保存后的表单。"""
        # 1) 基本信息
        for form_key, value in (data.basic_info or {}).items():
            title = BASIC_INFO_FIELDS.get(form_key or "")
            if not title:
                continue
            text = (value or "").strip()
            self._profile.upsert_item(
                db,
                user_id,
                ProfileItemCreate(
                    category="basic_info",
                    title=title,
                    content=text or "",
                    item_type="fact",
                    status="confirmed",
                    visibility="resume_interview",
                ),
            )

        # 2) 教育经历（逐条 upsert，用学校作首个标识；同校则合并首条）
        for edu in data.education or []:
            self._upsert_education(db, user_id, edu)

        # 3) 个人奖项（多行，每行一条 → 一条类目为 award 的条目）
        awards = [a.strip() for a in (data.awards or "").splitlines() if a.strip()]
        if awards:
            self._profile.upsert_item(
                db,
                user_id,
                ProfileItemCreate(
                    category="award",
                    title="个人奖项",
                    content="\n".join(awards),
                    item_type="fact",
                    status="confirmed",
                    visibility="resume_interview",
                ),
            )

        # 4) 社交账号（每条 → 一条 category=social，title=平台）
        for soc in data.social or []:
            platform = (soc.platform or "").strip()
            account = (soc.account or "").strip()
            if not platform and not account:
                continue
            self._profile.upsert_item(
                db,
                user_id,
                ProfileItemCreate(
                    category="social",
                    title=platform or "社交账号",
                    content=account or "",
                    item_type="fact",
                    status="confirmed",
                    visibility="resume_interview",
                ),
            )

        # 5) 其他分类兜底
        for ext in data.extra or []:
            cat = (ext.category or "").strip()
            if cat not in EXTRA_CATEGORIES:
                raise ProfileServiceError(f"其他分类非法: {cat!r}，允许 {sorted(EXTRA_CATEGORIES)}")
            title = (ext.title or "").strip()
            if not title:
                continue
            self._profile.upsert_item(
                db,
                user_id,
                ProfileItemCreate(
                    category=cat,
                    title=title,
                    content=(ext.content or "").strip() or "",
                    item_type="fact",
                    status="confirmed",
                    visibility="resume_interview",
                ),
            )

        return self.load(db, user_id)

    # ---- 内部 ----

    def _upsert_education(self, db: DBSession, user_id: int, edu: ProfileEducationEntry) -> ProfileItem:
        school = (edu.school or "").strip()
        title = school or "教育经历"
        content = self._format_education(edu)
        item, created = self._profile.upsert_item(
            db,
            user_id,
            ProfileItemCreate(
                category="education",
                title=title,
                content=content,
                item_type="fact",
                status="confirmed",
                visibility="resume_interview",
            ),
        )
        if created:
            self._profile.add_evidence(
                db,
                user_id,
                item.id,
                EvidenceCreate(
                    source_type="user_input",
                    quote=f"教育经历·{title}：{content}" if content else f"教育经历·{title}",
                    verified_by_user=True,
                ),
            )
        return item

    @staticmethod
    def _format_education(edu: ProfileEducationEntry) -> str:
        """把结构化教育经历拼成 content（学历/专业/主修课程/起止/GPA）。"""
        parts: list[str] = []
        for field_key, label in _EDU_LABELS:
            value = getattr(edu, field_key, None)
            if value:
                parts.append(f"{label}：{value}")
        return "\n".join(parts)

    @staticmethod
    def _parse_education(title: str, content: str) -> ProfileEducationEntry:
        """把 education 条目解析回结构化字段（回显表单）。"""
        fields: dict[str, str] = {}
        for line in (content or "").splitlines():
            if "：" in line:
                key, _, val = line.partition("：")
                fields[key.strip()] = val.strip()
        return ProfileEducationEntry(
            school=title if title != "教育经历" else "",
            degree=fields.get("学历", ""),
            major=fields.get("专业", ""),
            courses=fields.get("主修课程", ""),
            start=fields.get("开始时间", ""),
            end=fields.get("结束时间", ""),
            gpa=fields.get("GPA", ""),
        )


__all__ = ["ProfileFormService", "ProfileFormError", "BASIC_INFO_FIELDS"]
