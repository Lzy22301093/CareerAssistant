"""Tests for the 5 new asset-profile ORM models (阶段0 指令0-1)."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import (
    JobPosting,
    MatchTask,
    ProfileEvidence,
    ProfileItem,
    ProfileUpdateProposal,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_profile_item_with_evidence(db_session: Session):
    """Create a ProfileItem and attach an Evidence, verify cascade + repr."""
    item = ProfileItem(
        user_id=1,
        category="experience",
        title="arXiv 论文问答系统",
        content="Production RAG pipeline",
        item_type="fact",
        confidence=0.9,
        status="confirmed",
    )
    db_session.add(item)
    db_session.flush()

    evidence = ProfileEvidence(
        profile_item_id=item.id,
        source_type="resume",
        source_id="resume-001",
        quote="负责向量检索与 RRF 融合排序",
        verified_by_user=False,
    )
    db_session.add(evidence)
    db_session.commit()

    retrieved = db_session.query(ProfileItem).filter_by(title="arXiv 论文问答系统").first()
    assert retrieved is not None
    assert retrieved.status == "confirmed"
    assert retrieved.confidence == 0.9
    assert len(retrieved.evidences) == 1
    assert retrieved.evidences[0].source_type == "resume"
    assert retrieved.evidences[0].quote.startswith("负责向量")


def test_job_posting_with_match_task(db_session: Session):
    """Create a JobPosting and a MatchTask linked to it."""
    posting = JobPosting(
        user_id=1,
        company="字节跳动",
        title="后端开发实习生",
        jd_text="负责搜索服务端开发",
        source="manual",
    )
    db_session.add(posting)
    db_session.flush()

    task = MatchTask(
        user_id=1,
        job_posting_id=posting.id,
        page_preference="one_page",
        score=82,
        stage="done",
    )
    db_session.add(task)
    db_session.commit()

    retrieved = db_session.query(JobPosting).filter_by(company="字节跳动").first()
    assert retrieved is not None
    assert len(retrieved.match_tasks) == 1
    assert retrieved.match_tasks[0].score == 82
    assert retrieved.match_tasks[0].stage == "done"


def test_profile_update_proposal(db_session: Session):
    """Create a ProfileUpdateProposal and verify default status."""
    proposal = ProfileUpdateProposal(
        user_id=1,
        report_id="interview-001",
        change_type="add",
        after_value="具备 RRF 融合排序经验",
        evidence_ids='["ev-1"]',
        reason="面试回答中清晰说明",
    )
    db_session.add(proposal)
    db_session.commit()

    retrieved = db_session.query(ProfileUpdateProposal).filter_by(report_id="interview-001").first()
    assert retrieved is not None
    assert retrieved.status == "pending"
    assert retrieved.change_type == "add"
    assert retrieved.created_at is not None


def test_interview_report_proposal_ids_column():
    """InterviewReport now has a proposal_ids column; verify it exists on create_all."""
    # Column presence check without connecting to MySQL: introspect the model.
    from app.models.orm import InterviewReport

    cols = {c.name for c in InterviewReport.__table__.columns}
    assert "proposal_ids" in cols
