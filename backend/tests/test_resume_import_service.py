"""Tests for 简历库 上传/生成 导入（生成区缺口）。"""

import base64
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import User
from app.services.resume_library_service import (
    ResumeLibraryError,
    ResumeLibraryService,
    infer_section_type,
    sections_from_text,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    session.add(User(username="u1", email="u1@test.com", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_sections_from_text_heuristic():
    text = "个人信息\n张三\n教育背景\n北京大学 本科\n技能\nPython"
    content = sections_from_text(text)
    titles = [s["title"] for s in content["sections"]]
    assert "教育背景" in titles and "技能" in titles
    assert content["raw_text"] == text


def test_sections_from_text_single_block():
    content = sections_from_text("只有一段正文，没有标题。")
    assert content["sections"][0]["title"] == "正文"


def test_objective_section_type_infer():
    assert infer_section_type("求职意向") == "objective"
    assert infer_section_type("目标岗位") == "objective"
    assert infer_section_type("教育背景") == "education"


def test_import_generated(db_session: Session):
    svc = ResumeLibraryService()
    content = {"sections": [{"title": "基本信息", "content": "姓名：张三"}], "raw_text": "姓名：张三"}
    doc, ver = svc.import_generated(db_session, 1, "生成简历", content, "two_pages")
    assert doc.source == "generation"
    assert ver.document_id == doc.id
    assert json.loads(ver.render_config_json)["page_preference"] == "two_pages"
    # 区域自动拆分 + 接口类型推断
    assert any(s.section_type == "header" for s in ver.sections)


@pytest.mark.asyncio
async def test_import_uploaded_file(db_session: Session):
    svc = ResumeLibraryService()
    text = "个人信息\n张三\n教育背景\n北京大学 本科\n技能\nPython"
    b64 = base64.b64encode(text.encode()).decode()
    doc, ver = await svc.import_uploaded_file(db_session, 1, "上传简历", b64, "resume.txt")
    assert doc.source == "upload"
    assert any(s.title == "教育背景" for s in ver.sections)
    assert any(s.section_type == "skill" for s in ver.sections)


@pytest.mark.asyncio
async def test_import_uploaded_file_bad_format(db_session: Session):
    svc = ResumeLibraryService()
    with pytest.raises(ResumeLibraryError):
        await svc.import_uploaded_file(db_session, 1, "x", base64.b64encode(b"x").decode(), "a.exe")
