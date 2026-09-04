"""Tests for ProfileService CRUD (阶段0 指令0-3)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import ProfileItem
from app.models.schemas import EvidenceCreate, ProfileItemCreate, ProfileItemUpdate, StatusChange
from app.services.profile_service import ProfileService, ProfileServiceError


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


def test_create_and_list(db_session: Session):
    svc = ProfileService()
    item = svc.create_item(
        db_session, 1,
        ProfileItemCreate(category="experience", title="arXiv 问答系统", content="RAG 全链路"),
    )
    assert item.id is not None
    assert item.status == "confirmed"
    items = svc.list_items(db_session, 1)
    assert len(items) == 1


def test_update_and_status(db_session: Session):
    svc = ProfileService()
    item = svc.create_item(db_session, 1, ProfileItemCreate(category="skill", title="技能", content="Python"))
    updated = svc.update_item(db_session, 1, item.id, ProfileItemUpdate(content="Python, LangGraph"))
    assert updated.content == "Python, LangGraph"
    changed = svc.change_status(db_session, 1, item.id, StatusChange(status="suggested").status)
    assert changed.status == "suggested"


def test_add_evidence(db_session: Session):
    svc = ProfileService()
    item = svc.create_item(db_session, 1, ProfileItemCreate(category="experience", title="经历", content="x"))
    ev = svc.add_evidence(db_session, 1, item.id, EvidenceCreate(source_type="resume", quote="负责检索"))
    full = svc.get_item(db_session, 1, item.id)
    assert len(full.evidences) == 1
    assert full.evidences[0].quote == "负责检索"


def test_invalid_status_rejected(db_session: Session):
    svc = ProfileService()
    with pytest.raises(ProfileServiceError):
        svc.create_item(db_session, 1, ProfileItemCreate(category="skill", title="t", status="bogus"))


def test_delete_and_not_found(db_session: Session):
    svc = ProfileService()
    item = svc.create_item(db_session, 1, ProfileItemCreate(category="skill", title="t", content="c"))
    svc.delete_item(db_session, 1, item.id)
    with pytest.raises(ProfileServiceError):
        svc.get_item(db_session, 1, item.id)


def test_category_summary(db_session: Session):
    svc = ProfileService()
    svc.create_item(db_session, 1, ProfileItemCreate(category="skill", title="s1"))
    svc.create_item(db_session, 1, ProfileItemCreate(category="skill", title="s2", status="suggested"))
    svc.create_item(db_session, 1, ProfileItemCreate(category="experience", title="e1"))
    summary = svc.category_summary(db_session, 1)
    by_cat = {s["category"]: s for s in summary}
    assert by_cat["skill"]["count"] == 2
    assert by_cat["skill"]["confirmed"] == 1
    assert by_cat["skill"]["suggested"] == 1
    assert by_cat["experience"]["count"] == 1
