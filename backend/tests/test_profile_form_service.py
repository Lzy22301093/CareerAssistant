"""Tests for ProfileFormService (知识库 分阶段向导，阶段3)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.schemas import (
    ProfileEducationEntry,
    ProfileExtraEntry,
    ProfileFormSave,
    ProfileSocialEntry,
)
from app.services.profile_form_service import ProfileFormService
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


def test_save_basic_info_uses_expected_titles(db_session: Session):
    """基本信息写出后，条目标题必须与下游 `aggregate_confirmed_profile` 识别的一致。"""
    svc = ProfileFormService()
    svc.save(
        db_session, 1,
        ProfileFormSave(
            basic_info={
                "name": "张三",
                "phone": "13800000000",
                "email": "zhang@example.com",
                "location": "北京",
                "gender": "男",
            },
        ),
    )
    items = ProfileService().list_items(db_session, 1)
    by_title = {i.title: i.content for i in items}
    assert by_title["姓名"] == "张三"
    assert by_title["电话"] == "13800000000"
    assert by_title["邮箱"] == "zhang@example.com"
    assert by_title["所在地"] == "北京"
    assert by_title["性别"] == "男"

    # 聚合形态：姓名/邮箱/电话/所在地应映射到 name/email/phone/location
    from app.services.profile_service import build_profile_context
    ctx = build_profile_context(db_session, 1)
    assert ctx["name"] == "张三"
    assert ctx["email"] == "zhang@example.com"
    assert ctx["phone"] == "13800000000"
    assert ctx["location"] == "北京"


def test_upsert_idempotent(db_session: Session):
    """重复保存同一表单不产生重复条目（按 category+title upsert）。"""
    svc = ProfileFormService()
    payload = ProfileFormSave(basic_info={"name": "张三"})
    svc.save(db_session, 1, payload)
    svc.save(db_session, 1, payload)
    items = ProfileService().list_items(db_session, 1)
    assert len([i for i in items if i.title == "姓名"]) == 1


def test_save_education_award_social(db_session: Session):
    """教育经历/个人奖项/社交账号写入对应分类，且可回显。"""
    svc = ProfileFormService()
    svc.save(
        db_session, 1,
        ProfileFormSave(
            education=[
                ProfileEducationEntry(
                    school="北京交通大学", degree="本科", major="软件工程",
                    courses="数据结构", start="2020-09", end="2024-06", gpa="3.8",
                )
            ],
            awards="国家奖学金\n数学竞赛一等奖",
            social=[ProfileSocialEntry(platform="QQ", account="2323613122")],
        ),
    )
    prof = ProfileService()
    edu = prof.list_by_category(db_session, 1, "education")
    assert len(edu) == 1
    assert edu[0].title == "北京交通大学"
    assert "本科" in edu[0].content
    assert "软件工程" in edu[0].content

    award = prof.list_by_category(db_session, 1, "award")
    assert len(award) == 1
    assert "国家奖学金" in award[0].content

    social = prof.list_by_category(db_session, 1, "social")
    assert len(social) == 1
    assert social[0].title == "QQ"
    assert social[0].content == "2323613122"

    # 回显
    out = svc.load(db_session, 1)
    assert len(out.education) == 1
    assert out.education[0].school == "北京交通大学"
    assert out.education[0].degree == "本科"
    assert out.education[0].gpa == "3.8"
    assert out.awards == ["国家奖学金", "数学竞赛一等奖"]
    assert out.social[0].platform == "QQ"
    assert out.social[0].account == "2323613122"


def test_extra_category_validated(db_session: Session):
    """extra 只接受白名单分类。"""
    svc = ProfileFormService()
    with pytest.raises(ProfileServiceError):
        svc.save(
            db_session, 1,
            ProfileFormSave(extra=[ProfileExtraEntry(category="bogus", title="x")]),
        )


def test_empty_payload_returns_empty(db_session: Session):
    svc = ProfileFormService()
    out = svc.save(db_session, 1, ProfileFormSave())
    assert out.basic_info == {}
    assert out.education == []
    assert out.social == []
