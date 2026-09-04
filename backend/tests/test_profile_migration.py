"""Tests for profile migration (阶段0 指令0-2)."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import CareerProfile, ProfileEvidence, ProfileItem
from app.services.profile_migration import apply_migration, plan_migration, split_profile

SAMPLE_PROFILE = {
    "name": "量子",
    "email": "qa@example.com",
    "location": "北京",
    "summary": "热爱 AI 应用开发",
    "skills": ["Python", "LangGraph"],
    "projects": [{"name": "arXiv 问答系统", "role": "开发者", "result": "全链路落地"}],
    "education": ["北京大学 软件工程硕士"],
    "target_roles": ["后端开发工程师", "算法工程师"],
    "gaps": ["跨端开发经验空白"],
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


def test_split_profile_mapping():
    items = split_profile(SAMPLE_PROFILE)
    by_title = {it["title"]: it for it in items}
    assert "姓名" in by_title and by_title["姓名"]["category"] == "basic_info"
    assert "专业技能" in by_title and by_title["专业技能"]["category"] == "skill"
    assert "项目经历" in by_title and by_title["项目经历"]["category"] == "experience"
    assert "教育经历" in by_title and by_title["教育经历"]["category"] == "education"
    assert "目标岗位" in by_title and by_title["目标岗位"]["category"] == "target"
    # gaps 是反馈 → suggested / feedback
    assert by_title["待补强能力"]["status"] == "suggested"
    assert by_title["待补强能力"]["item_type"] == "feedback"
    # fact 默认 confirmed
    assert by_title["姓名"]["status"] == "confirmed"


def test_plan_then_apply(db_session: Session):
    db_session.add(CareerProfile(user_id=1, profile_json=json.dumps(SAMPLE_PROFILE, ensure_ascii=False), source="resume"))
    db_session.commit()

    plan = plan_migration(db_session)
    assert len(plan) == 1
    assert plan[0]["user_id"] == 1
    assert len(plan[0]["items"]) >= 8  # 各分类条目

    summary = apply_migration(db_session)
    assert len(summary) == 1

    items = db_session.query(ProfileItem).filter_by(user_id=1).all()
    assert len(items) >= 8
    # evidence 已挂上
    ev = db_session.query(ProfileEvidence).filter_by(source_type="resume").first()
    assert ev is not None
    assert ev.quote.startswith("量子")

    # 原表保留
    assert db_session.query(CareerProfile).filter_by(user_id=1).count() == 1


def test_idempotent(db_session: Session):
    db_session.add(CareerProfile(user_id=1, profile_json=json.dumps(SAMPLE_PROFILE, ensure_ascii=False), source="resume"))
    db_session.commit()
    apply_migration(db_session)
    # 再次迁移应跳过（已存在条目）
    plan2 = plan_migration(db_session)
    assert plan2 == []
