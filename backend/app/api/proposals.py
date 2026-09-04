"""Proposal API — 面试报告 → 画像更新提案的确认/拒绝（阶段1 指令1-2）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_auth
from app.models.database import get_db
from app.models.orm import ProfileUpdateProposal
from app.models.schemas import ProfileUpdateProposalOut, ProposalAction
from app.services.proposal_service import ProfileProposalService, ProposalServiceError

router = APIRouter()
service = ProfileProposalService()


def _serialize(p: ProfileUpdateProposal) -> dict:
    return {
        "id": p.id,
        "report_id": p.report_id,
        "change_type": p.change_type,
        "target_profile_item_id": p.target_profile_item_id,
        "before_value": p.before_value,
        "after_value": p.after_value,
        "reason": p.reason,
        "status": p.status,
        "created_at": p.created_at,
    }


@router.get("/{report_id}", response_model=list[ProfileUpdateProposalOut])
async def list_proposals(
    report_id: str,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    return [_serialize(p) for p in service.list_for_report(db, user["id"], report_id)]


@router.post("/{proposal_id}/action", response_model=ProfileUpdateProposalOut)
async def act_on_proposal(
    proposal_id: int,
    data: ProposalAction,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        if data.action == "accept":
            p = service.accept(db, user["id"], proposal_id, after_value_override=data.after_value)
        elif data.action == "reject":
            p = service.reject(db, user["id"], proposal_id)
        elif data.action == "defer":
            p = service.defer(db, user["id"], proposal_id)
        else:
            raise ProposalServiceError(f"未知操作: {data.action}")
    except ProposalServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serialize(p)
