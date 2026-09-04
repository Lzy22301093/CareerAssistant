"""Tests for ProfileProposalService (阶段1 指令1-1/1-2)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import ProfileEvidence, ProfileItem, ProfileUpdateProposal
from app.models.schemas import ProfileItemCreate
from app.services.profile_service import ProfileService
from app.services.proposal_service import (
    ProfileProposalService,
    ProposalServiceError,
    build_proposals_from_state,
)

STATE = {
    "user_id": 1,
    "strengths": ["具备 RRF 融合排序经验", "工程化素养完整"],
    "weaknesses": ["跨端开发经验空白", "缺乏数据驱动实验"],
    "dimension_scores": {"专业知识": 7.5, "表达": 4.0, "项目理解": 8.2},
}


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_build_proposals_three_types(db_session: Session):
    proposals = build_proposals_from_state(db_session, 1, "interview-001", STATE)
    assert len(proposals) >= 4  # 2 强项 + 2 弱项 + 1 低分维度
    types = {p.change_type for p in proposals}
    assert "add" in types or "add_evidence" in types  # 能力证据
    assert "feedback" in types  # 表达反馈（低分维度）
    # 低分维度产生 feedback
    feedbacks = [p for p in proposals if p.change_type == "feedback"]
    assert any("表达" in (p.after_value or "") for p in feedbacks)
    assert all(p.status == "pending" for p in proposals)


def test_accept_creates_item_and_evidence(db_session: Session):
    build_proposals_from_state(db_session, 1, "interview-001", STATE)
    svc = ProfileProposalService()
    proposal = db_session.query(ProfileUpdateProposal).filter_by(change_type="feedback").first()
    result = svc.accept(db_session, 1, proposal.id)
    assert result.status == "accepted"
    assert result.target_profile_item_id is not None
    item = db_session.query(ProfileItem).filter_by(id=result.target_profile_item_id).first()
    assert item is not None
    assert item.item_type == "feedback"
    assert item.status == "confirmed"
    ev = db_session.query(ProfileEvidence).filter_by(profile_item_id=item.id, source_type="interview_report").first()
    assert ev is not None
    assert ev.verified_by_user is True


def test_accept_idempotent(db_session: Session):
    build_proposals_from_state(db_session, 1, "interview-001", STATE)
    svc = ProfileProposalService()
    proposal = db_session.query(ProfileUpdateProposal).first()
    first = svc.accept(db_session, 1, proposal.id)
    count_before = db_session.query(ProfileItem).count()
    second = svc.accept(db_session, 1, proposal.id)
    assert second.status == "accepted"
    assert db_session.query(ProfileItem).count() == count_before  # 不重复写


def test_reject_no_write(db_session: Session):
    build_proposals_from_state(db_session, 1, "interview-001", STATE)
    svc = ProfileProposalService()
    proposal = db_session.query(ProfileUpdateProposal).first()
    before_items = db_session.query(ProfileItem).count()
    result = svc.reject(db_session, 1, proposal.id)
    assert result.status == "rejected"
    assert db_session.query(ProfileItem).count() == before_items  # 不写画像


def test_not_found(db_session: Session):
    svc = ProfileProposalService()
    with pytest.raises(ProposalServiceError):
        svc.accept(db_session, 1, 99999)


def test_accept_match_existing_adds_evidence(db_session: Session):
    # 先建一个与强项关键词匹配的条目
    ProfileService().create_item(db_session, 1, ProfileItemCreate(category="skill", title="RRF 融合排序", content="做过 RRF"))
    proposals = build_proposals_from_state(db_session, 1, "interview-001", STATE)
    add_ev = [p for p in proposals if p.change_type == "add_evidence"]
    assert add_ev, "应匹配到已有条目并生成 add_evidence"
    svc = ProfileProposalService()
    result = svc.accept(db_session, 1, add_ev[0].id)
    assert result.status == "accepted"
    # 给目标条目挂了证据
    ev = db_session.query(ProfileEvidence).filter_by(profile_item_id=add_ev[0].target_profile_item_id).first()
    assert ev is not None
