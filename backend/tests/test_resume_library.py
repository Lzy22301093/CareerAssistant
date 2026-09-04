"""Tests for ResumeLibraryService（阶段2 指令2-1：简历库资产化）。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import AnalysisSession, ResumeDocument, ResumeSection, ResumeVersion, User
from app.models.schemas import (
    ResumeDocumentCreate,
    ResumeDocumentUpdate,
    ResumeSectionUpdate,
    ResumeVersionCreate,
)
from app.services.resume_library_service import (
    ResumeLibraryError,
    ResumeLibraryService,
    infer_section_type,
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


CONTENT_V1 = {
    "sections": [
        {"title": "教育经历", "content": "XX大学 计算机 本科"},
        {"title": "工作经历", "content": "A公司 后端工程师"},
        {"title": "项目经历", "content": "检索问答系统"},
        {"title": "技能", "content": "Python, SQL"},
    ],
    "raw_text": "教育经历\n工作经历",
}
CONTENT_V2 = {
    "sections": [{"title": "项目经历", "content": "检索问答系统（量化优化版）"}],
    "raw_text": "项目经历",
}


def _create_doc(svc, db, title="我的简历"):
    return svc.create_document(db, 1, ResumeDocumentCreate(title=title))


def test_create_and_list_documents(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    assert doc.id is not None and doc.source == "manual" and doc.deleted_at is None
    assert len(svc.list_documents(db_session, 1)) == 1
    assert svc.list_documents(db_session, 2) == []


def test_add_version_auto_numbering_and_sections(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    v1 = svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT_V1))
    v2 = svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT_V2))
    assert (v1.version, v2.version) == (1, 2)
    assert doc.current_version_id == v2.id
    # 区域自动拆分 + 类型推断
    types = [s.section_type for s in v1.sections]
    assert types == ["education", "experience", "project", "skill"]
    assert len(v2.sections) == 1
    # 版本列表倒序
    versions = svc.list_versions(db_session, 1, doc.id)
    assert [v.version for v in versions] == [2, 1]


def test_add_version_with_raw_text_only(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    version = svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content={"raw_text": "纯文本简历"}))
    assert len(version.sections) == 1
    assert version.sections[0].section_type == "custom"


def test_rollback_is_non_destructive(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    v1 = svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT_V1))
    v2 = svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT_V2))
    rolled = svc.rollback_version(db_session, 1, doc.id, v1.id)
    assert rolled.current_version_id == v1.id
    # 历史版本仍在，可再滚回来
    assert len(svc.list_versions(db_session, 1, doc.id)) == 2
    svc.rollback_version(db_session, 1, doc.id, v2.id)
    assert svc.get_document(db_session, 1, doc.id).current_version_id == v2.id


def test_rollback_foreign_version_rejected(db_session: Session):
    svc = ResumeLibraryService()
    doc_a = _create_doc(svc, db_session, "A")
    doc_b = _create_doc(svc, db_session, "B")
    v_b = svc.add_version(db_session, 1, doc_b.id, ResumeVersionCreate(content=CONTENT_V1))
    with pytest.raises(ResumeLibraryError):
        svc.rollback_version(db_session, 1, doc_a.id, v_b.id)


def test_soft_delete_restore_recycle_bin(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT_V1))
    svc.soft_delete_document(db_session, 1, doc.id)
    assert svc.list_documents(db_session, 1) == []
    assert [d.id for d in svc.list_deleted(db_session, 1)] == [doc.id]
    # 回收站里的文档 get 默认 404
    with pytest.raises(ResumeLibraryError):
        svc.get_document(db_session, 1, doc.id)
    restored = svc.restore_document(db_session, 1, doc.id)
    assert restored.deleted_at is None
    assert len(svc.list_documents(db_session, 1)) == 1


def test_purge_removes_versions_and_sections(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    version = svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT_V1))
    svc.soft_delete_document(db_session, 1, doc.id)
    svc.purge_document(db_session, 1, doc.id)
    assert svc.list_deleted(db_session, 1) == []
    assert db_session.query(ResumeVersion).count() == 0
    assert db_session.query(ResumeSection).count() == 0


def test_rename_document(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    renamed = svc.rename_document(db_session, 1, doc.id, ResumeDocumentUpdate(title="新名字", notes="备注"))
    assert renamed.title == "新名字" and renamed.notes == "备注"


def test_update_section_content_and_bounding_box(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    version = svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT_V1))
    section = version.sections[3]  # 技能
    box = {"x": 10, "y": 20, "width": 300, "height": 80, "page": 1}
    updated = svc.update_section(
        db_session, 1, section.id, ResumeSectionUpdate(content="Python, SQL, LangGraph", bounding_box=box)
    )
    assert updated.content == "Python, SQL, LangGraph"
    assert json.loads(updated.bounding_box) == box
    with pytest.raises(ResumeLibraryError):
        svc.update_section(db_session, 1, section.id, ResumeSectionUpdate(section_type="bogus"))


def test_import_from_session(db_session: Session):
    svc = ResumeLibraryService()
    db_session.add(AnalysisSession(session_id="sess-12345678", user_id=1, stage="completed"))
    db_session.add(
        ResumeVersion(session_id="sess-12345678", version=1, content_json=json.dumps(CONTENT_V1, ensure_ascii=False))
    )
    db_session.commit()
    doc, version = svc.import_from_session(db_session, 1, "sess-12345678")
    assert doc.source == "session" and doc.title == "会话简历 sess-123"
    assert version.version == 1 and version.document_id == doc.id
    assert len(version.sections) == 4
    # 幂等不受限：再导一次生成第二个文档（用户可自行命名/删除）
    doc2, _ = svc.import_from_session(db_session, 1, "sess-12345678", title="自命名")
    assert doc2.title == "自命名" and doc2.id != doc.id


def test_import_empty_session_rejected(db_session: Session):
    svc = ResumeLibraryService()
    db_session.add(AnalysisSession(session_id="sess-empty", user_id=1))
    db_session.commit()
    with pytest.raises(ResumeLibraryError):
        svc.import_from_session(db_session, 1, "sess-empty")


def test_foreign_user_isolated(db_session: Session):
    svc = ResumeLibraryService()
    doc = _create_doc(svc, db_session)
    svc.add_version(db_session, 1, doc.id, ResumeVersionCreate(content=CONTENT_V1))
    with pytest.raises(ResumeLibraryError):
        svc.get_document(db_session, 2, doc.id)
    with pytest.raises(ResumeLibraryError):
        svc.list_versions(db_session, 2, doc.id)


def test_invalid_source_rejected(db_session: Session):
    svc = ResumeLibraryService()
    with pytest.raises(ResumeLibraryError):
        svc.create_document(db_session, 1, ResumeDocumentCreate(title="x", source="bogus"))


def test_infer_section_type():
    assert infer_section_type("教育经历") == "education"
    assert infer_section_type("实习经历") == "experience"
    assert infer_section_type("项目经历") == "project"
    assert infer_section_type("专业技能") == "skill"
    assert infer_section_type("自我评价") == "summary"
    assert infer_section_type("基本信息") == "header"
    assert infer_section_type("奇怪的标题") == "custom"
    assert infer_section_type(None) == "custom"
