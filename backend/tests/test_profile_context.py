"""Tests for confirmed-profile context aggregation (阶段1 指令1-4)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.schemas import ProfileItemCreate
from app.services.profile_service import (
    ProfileService,
    aggregate_confirmed_profile,
    build_profile_context,
)


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


def _mk(category, title, content, status="confirmed"):
    return ProfileItemCreate(category=category, title=title, content=content, status=status)


def test_aggregate_groups_by_category(db_session: Session):
    svc = ProfileService()
    svc.create_item(db_session, 1, _mk("basic_info", "姓名", "量子"))
    svc.create_item(db_session, 1, _mk("skill", "专业技能", "Python, LangGraph"))
    svc.create_item(db_session, 1, _mk("education", "教育经历", "北京大学 硕士"))
    svc.create_item(db_session, 1, _mk("target", "目标岗位", "后端开发工程师"))
    ctx = build_profile_context(db_session, 1)
    assert ctx["name"] == "量子"
    assert any("Python" in s for s in ctx["skills"])
    assert any("北京大学" in e for e in ctx["education"])
    assert "后端开发工程师" in ctx["target_roles"]


def test_suggested_not_included(db_session: Session):
    svc = ProfileService()
    svc.create_item(db_session, 1, _mk("skill", "专业技能", "Python", status="confirmed"))
    svc.create_item(db_session, 1, _mk("skill", "专业技能", "建议技能", status="suggested"))
    ctx = build_profile_context(db_session, 1)
    assert len(ctx["skills"]) == 1
    assert "Python" in ctx["skills"][0]


def test_rejected_not_included(db_session: Session):
    svc = ProfileService()
    svc.create_item(db_session, 1, _mk("target", "目标岗位", "被拒岗位", status="rejected"))
    ctx = build_profile_context(db_session, 1)
    assert "target_roles" not in ctx


def test_aggregate_pure_function():
    items = [
        __import__("app.models.orm", fromlist=["ProfileItem"]).ProfileItem(
            category="skill", title="技能", content="Go", status="confirmed"
        ),
        __import__("app.models.orm", fromlist=["ProfileItem"]).ProfileItem(
            category="skill", title="技能", content="Rust", status="suggested"
        ),
    ]
    ctx = aggregate_confirmed_profile(items)
    assert len(ctx["skills"]) == 1
