"""Proposal Service — 面试报告 → 画像更新提案（阶段1 指令1-1/1-2）。

设计（实施计划 §4.3）：
- 面试报告/状态 → 提取"能力证据 / 内容缺口 / 表达反馈"三类 ProfileUpdateProposal
- 每条带 evidence 引用（report_id 关联），status 默认 pending
- 确认逻辑：仅"采纳"写回 ProfileItem；拒绝/稍后不写。幂等：非 pending 不再处理
- 表达反馈（feedback 类型）默认只作报告，需用户明确采纳才写入（采纳即视为显式选择）
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.orm import ProfileEvidence, ProfileItem, ProfileUpdateProposal

# 新条目落库的默认分类（面试来源）
_DEFAULT_CATEGORY = "interview_feedback"

# 表达反馈写回时使用的 item_type
_FEEDBACK_ITEM_TYPE = "feedback"
_FACT_ITEM_TYPE = "fact"


class ProposalServiceError(ValueError):
    """业务校验错误。"""


def _match_existing(items: list[ProfileItem], text: str) -> tuple[int | None, str | None]:
    """按关键词重叠匹配已有条目，返回 (item_id, current_content)。"""
    words = [w for w in set(str(text).split()) if len(w) >= 2]
    if not words:
        return None, None
    best_id: int | None = None
    best_score = 0
    for item in items:
        haystack = f"{item.title or ''} {item.content or ''}".lower()
        score = sum(1 for w in words if w.lower() in haystack)
        if score > best_score:
            best_score = score
            best_id = item.id
    if best_id is None:
        return None, None
    item = next(i for i in items if i.id == best_id)
    return best_id, item.content


def build_proposals_from_state(
    db: DBSession,
    user_id: int,
    report_id: str,
    state: dict[str, Any],
) -> list[ProfileUpdateProposal]:
    """从面试状态生成三类提案并落库，返回新建的提案列表。"""
    proposals_spec: list[dict[str, Any]] = []
    existing_items = db.query(ProfileItem).filter(ProfileItem.user_id == user_id).all()

    # 1. strengths → 能力证据
    for s in state.get("strengths") or []:
        s = str(s).strip()
        if not s:
            continue
        target_id, before = _match_existing(existing_items, s)
        proposals_spec.append({
            "change_type": "add_evidence" if target_id else "add",
            "target_profile_item_id": target_id,
            "before_value": before,
            "after_value": s,
            "reason": "面试评价-能力证据",
        })

    # 2. weaknesses → 内容缺口
    for w in state.get("weaknesses") or []:
        w = str(w).strip()
        if not w:
            continue
        target_id, before = _match_existing(existing_items, w)
        proposals_spec.append({
            "change_type": "update" if target_id else "add",
            "target_profile_item_id": target_id,
            "before_value": before,
            "after_value": w,
            "reason": "面试评价-内容缺口",
        })

    # 3. dimension_scores 低分 → 表达反馈
    for dim, score in (state.get("dimension_scores") or {}).items():
        try:
            score_f = float(score)
        except (TypeError, ValueError):
            continue
        if score_f < 5.0:
            proposals_spec.append({
                "change_type": "feedback",
                "target_profile_item_id": None,
                "before_value": None,
                "after_value": f"{dim} 表现一般（{score_f:.1f}/10）",
                "reason": "面试评价-表达反馈",
            })

    created: list[ProfileUpdateProposal] = []
    for spec in proposals_spec:
        row = ProfileUpdateProposal(
            user_id=user_id,
            report_id=report_id,
            change_type=spec["change_type"],
            target_profile_item_id=spec.get("target_profile_item_id"),
            before_value=spec.get("before_value"),
            after_value=spec.get("after_value"),
            evidence_ids=json.dumps([report_id], ensure_ascii=False),
            reason=spec.get("reason"),
            status="pending",
        )
        db.add(row)
        created.append(row)
    if created:
        db.commit()
    return created


class ProfileProposalService:
    """画像更新提案的确认/拒绝/稍后处理。"""

    def get(self, db: DBSession, user_id: int, proposal_id: int) -> ProfileUpdateProposal:
        p = (
            db.query(ProfileUpdateProposal)
            .filter(ProfileUpdateProposal.id == proposal_id, ProfileUpdateProposal.user_id == user_id)
            .first()
        )
        if p is None:
            raise ProposalServiceError("提案不存在")
        return p

    def list_for_report(self, db: DBSession, user_id: int, report_id: str | None = None) -> list[ProfileUpdateProposal]:
        q = db.query(ProfileUpdateProposal).filter(ProfileUpdateProposal.user_id == user_id)
        if report_id:
            q = q.filter(ProfileUpdateProposal.report_id == report_id)
        return q.order_by(ProfileUpdateProposal.id.asc()).all()

    def accept(self, db: DBSession, user_id: int, proposal_id: int, after_value_override: str | None = None) -> ProfileUpdateProposal:
        """采纳：写回 ProfileItem（幂等）。after_value_override 用于"修改后采纳"。"""
        p = self.get(db, user_id, proposal_id)
        if p.status != "pending":
            return p  # 已处理，幂等返回
        after = after_value_override if after_value_override is not None else p.after_value

        if p.change_type == "add_evidence":
            # 给已有条目挂证据
            target = db.query(ProfileItem).filter(ProfileItem.id == p.target_profile_item_id).first()
            if target is None:
                raise ProposalServiceError("关联的画像条目不存在")
            db.add(ProfileEvidence(
                profile_item_id=target.id,
                source_type="interview_report",
                source_id=p.report_id,
                quote=after,
                verified_by_user=True,
            ))
        else:
            # add / update / feedback → 写条目
            item_type = _FEEDBACK_ITEM_TYPE if p.change_type == "feedback" else _FACT_ITEM_TYPE
            if p.target_profile_item_id:
                item = db.query(ProfileItem).filter(ProfileItem.id == p.target_profile_item_id).first()
                if item is None:
                    raise ProposalServiceError("关联的画像条目不存在")
                if after:
                    item.content = after
                item.status = "confirmed"
            else:
                item = ProfileItem(
                    user_id=user_id,
                    category=_DEFAULT_CATEGORY,
                    title=(after or "面试反馈")[:200],
                    content=after or None,
                    item_type=item_type,
                    confidence=1.0,
                    visibility="resume_interview",
                    status="confirmed",
                )
                db.add(item)
                db.flush()
                p.target_profile_item_id = item.id
            # 也给条目挂证据
            db.add(ProfileEvidence(
                profile_item_id=item.id,
                source_type="interview_report",
                source_id=p.report_id,
                quote=after,
                verified_by_user=True,
            ))

        p.status = "accepted"
        db.commit()
        db.refresh(p)
        return p

    def reject(self, db: DBSession, user_id: int, proposal_id: int) -> ProfileUpdateProposal:
        """拒绝：不写画像，仅保留该提案状态。"""
        p = self.get(db, user_id, proposal_id)
        if p.status == "pending":
            p.status = "rejected"
            db.commit()
            db.refresh(p)
        return p

    def defer(self, db: DBSession, user_id: int, proposal_id: int) -> ProfileUpdateProposal:
        """稍后处理：保留 suggested 状态，不影响当前画像。"""
        p = self.get(db, user_id, proposal_id)
        if p.status == "pending":
            p.status = "deferred"
            db.commit()
            db.refresh(p)
        return p
