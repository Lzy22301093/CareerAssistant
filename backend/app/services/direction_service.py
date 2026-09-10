"""DirectionService — 画像方向推荐（阶段3 指令3-1）。

基于已确认画像生成岗位方向候选（供用户选 1~3 个），并把用户选中的方向
写成 category=target 的 confirmed 画像条目，供下游简历/匹配/面试复用。

复用现有画像能力：
- profile_service.build_profile_context 聚合已确认条目为 profile 形态
- llm.structured.ainvoke_json_with_schema 做结构化 schema 校验（失败自动重试）
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import ProfileItem
from app.models.schemas import (
    DirectionCandidate,
    DirectionRecommendation,
    EvidenceCreate,
    ProfileItemCreate,
)
from app.services.profile_service import ProfileService, build_profile_context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是资深职业规划师。请根据候选人的个人画像，分析并推荐 3~8 个适合他的岗位投递方向。\n"
    "要求：\n"
    "1. 每个方向给出岗位名称 title、推荐理由 reason、方向详情/匹配点说明 detail。\n"
    "2. reason 要结合画像中的技能、经历、教育、软性信息等，具体且可解释，不要空泛；"
    "detail 给出该方向的核心要求与候选人匹配点。\n"
    "3. 候选方向互不重复，覆盖不同职业赛道（技术/产品/数据/咨询/运营等）。\n"
    "4. 只输出 JSON，不要任何额外文字。JSON 结构："
    '{"directions": [{"title": "...", "reason": "...", "detail": "..."}]}'
)

MAX_SELECT = 3


class DirectionError(ValueError):
    """方向推荐业务错误。"""


class DirectionService:
    """画像方向推荐 + 保存选择。"""

    def __init__(self) -> None:
        self._profile = ProfileService()

    async def recommend_directions(
        self,
        db: DBSession,
        user_id: int,
        llm: Any,
    ) -> list[dict[str, Any]]:
        """基于已确认画像生成岗位方向候选。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            llm: LLMProvider 实例。

        Returns:
            候选方向列表：[{"title", "reason", "detail"}]。

        Raises:
            DirectionError: 无已确认画像 / 未生成有效候选。
        """
        profile_ctx = build_profile_context(db, user_id)
        if not profile_ctx:
            raise DirectionError("暂无已确认画像，请先到个人知识库完善并确认画像条目")

        from app.llm.structured import ainvoke_json_with_schema

        user_content = (
            "候选人画像：\n"
            f"{_format_profile(profile_ctx)}\n\n"
            "请给出 3~8 个适合的岗位投递方向。"
        )
        result = await ainvoke_json_with_schema(
            llm,
            system_prompt=SYSTEM_PROMPT,
            user_content=user_content,
            schema=DirectionRecommendation,
            max_attempts=2,
            temperature=0.5,
            max_tokens=2048,
        )

        # 去重 + 截断
        seen: set[str] = set()
        candidates: list[dict[str, Any]] = []
        for d in result.directions:
            title = (d.title or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            candidates.append(
                {"title": title, "reason": (d.reason or "").strip(), "detail": (d.detail or "").strip()}
            )
        if not candidates:
            raise DirectionError("画像分析未生成有效的岗位方向，请重试")
        return candidates

    def confirm_directions(
        self,
        db: DBSession,
        user_id: int,
        selected: list[DirectionCandidate],
    ) -> list[ProfileItem]:
        """把用户选中的方向（1~3 个）写成 target 分类的 confirmed 画像条目。

        幂等：如果已存在同名的 confirmed target 条目，则跳过不重复写。

        Args:
            db: 数据库会话。
            user_id: 用户 ID。
            selected: 用户选中的方向候选。

        Returns:
            写入/复用的画像条目列表。

        Raises:
            DirectionError: 未选择任何方向 / 超过 3 个。
        """
        # 去重、去空白
        cleaned: list[DirectionCandidate] = []
        seen: set[str] = set()
        for sel in selected or []:
            title = (sel.title or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            cleaned.append(DirectionCandidate(title=title, reason=(sel.reason or "").strip(), detail=(sel.detail or "").strip()))
        if not cleaned:
            raise DirectionError("请至少选择一个岗位方向")
        if len(cleaned) > MAX_SELECT:
            raise DirectionError(f"最多只能选择 {MAX_SELECT} 个方向")

        saved: list[ProfileItem] = []
        for sel in cleaned:
            exists = (
                db.query(ProfileItem)
                .filter(
                    ProfileItem.user_id == user_id,
                    ProfileItem.category == "target",
                    ProfileItem.title == sel.title,
                    ProfileItem.status == "confirmed",
                )
                .first()
            )
            if exists:
                saved.append(exists)
                continue

            item = self._profile.create_item(
                db,
                user_id,
                ProfileItemCreate(
                    category="target",
                    title=sel.title,
                    content=(sel.reason or None),
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
                    quote=f"选择投递方向：{sel.title}",
                    verified_by_user=True,
                ),
            )
            saved.append(item)
        return saved


def _format_profile(ctx: dict[str, Any]) -> str:
    """把 profile 形态上下文格式化为可读文本（供 LLM 分析）。"""
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
        parts.append(f"现有目标方向：{', '.join(str(t) for t in ctx['target_roles'])}")
    if ctx.get("gaps"):
        parts.append(f"待补强：{', '.join(str(g) for g in ctx['gaps'])}")
    return "\n".join(parts)
