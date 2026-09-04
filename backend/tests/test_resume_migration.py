"""Tests for resume_versions → 简历库文档迁移（阶段2 指令2-1）。

SQLite 下 create_all 直接带全量列，因此只测回填计划与执行；
列变更 DDL 仅 MySQL 生效（plan_column_changes 对非 MySQL 方言返回空）。
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import AnalysisSession, ResumeDocument, ResumeVersion, User
from app.services.resume_migration import apply_migration, plan_backfill, plan_column_changes


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    session.add(User(username="u1", email="u1@test.com", hashed_password="x"))
    session.add(User(username="u2", email="u2@test.com", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed(db: Session, session_id: str, user_id: int | None, versions: int = 2) -> None:
    db.add(AnalysisSession(session_id=session_id, user_id=user_id, stage="completed"))
    for i in range(1, versions + 1):
        db.add(
            ResumeVersion(
                session_id=session_id,
                version=i,
                content_json=json.dumps({"sections": [{"title": f"v{i}", "content": "c"}]}, ensure_ascii=False),
            )
        )
    db.commit()


def test_plan_column_changes_empty_on_sqlite(db_session: Session):
    assert plan_column_changes(db_session) == []


def test_backfill_plan_groups_by_session(db_session: Session):
    _seed(db_session, "sess-a", 1, versions=2)
    _seed(db_session, "sess-b", 2, versions=1)
    plan, skipped = plan_backfill(db_session)
    assert skipped == 0
    assert {e["session_id"] for e in plan} == {"sess-a", "sess-b"}
    entry_a = next(e for e in plan if e["session_id"] == "sess-a")
    assert entry_a["user_id"] == 1 and entry_a["version_count"] == 2


def test_backfill_skips_anonymous_sessions(db_session: Session):
    _seed(db_session, "sess-anon", None, versions=1)
    plan, skipped = plan_backfill(db_session)
    assert plan == [] and skipped == 1
    # 执行也不应创建任何文档
    summary = apply_migration(db_session)
    assert summary["docs_created"] == 0
    assert db_session.query(ResumeDocument).count() == 0


def test_apply_backfill_creates_docs_and_links_versions(db_session: Session):
    _seed(db_session, "sess-a", 1, versions=3)
    summary = apply_migration(db_session)
    assert summary["docs_created"] == 1
    assert summary["versions_linked"] == 3
    docs = db_session.query(ResumeDocument).all()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.user_id == 1 and doc.source == "session"
    versions = db_session.query(ResumeVersion).order_by(ResumeVersion.version.asc()).all()
    assert [v.version for v in versions] == [1, 2, 3]
    assert all(v.document_id == doc.id for v in versions)
    assert all(v.user_id == 1 for v in versions)
    assert doc.current_version_id == versions[-1].id  # 最新版本为当前版本


def test_apply_is_idempotent(db_session: Session):
    _seed(db_session, "sess-a", 1, versions=2)
    first = apply_migration(db_session)
    second = apply_migration(db_session)
    assert first["docs_created"] == 1
    assert second["docs_created"] == 0 and second["versions_linked"] == 0
    assert db_session.query(ResumeDocument).count() == 1
    assert db_session.query(ResumeVersion).count() == 2
