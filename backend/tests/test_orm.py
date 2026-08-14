"""Tests for SQLAlchemy ORM models using SQLite in-memory database."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import AnalysisSession, ResumeVersion, UploadedFile


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


def test_create_session(db_session: Session):
    """Test creating and retrieving an AnalysisSession."""
    session = AnalysisSession(
        session_id="test-session-001",
        stage="init",
        jd_text="Python developer job description",
    )
    db_session.add(session)
    db_session.commit()

    # Retrieve and verify
    retrieved = db_session.query(AnalysisSession).filter_by(session_id="test-session-001").first()
    assert retrieved is not None
    assert retrieved.session_id == "test-session-001"
    assert retrieved.stage == "init"
    assert retrieved.jd_text == "Python developer job description"
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None


def test_create_resume_version(db_session: Session):
    """Test creating a ResumeVersion linked to a session."""
    # Create parent session
    session = AnalysisSession(session_id="test-session-002", stage="has_resume")
    db_session.add(session)
    db_session.commit()

    # Create resume version
    resume = ResumeVersion(
        session_id="test-session-002",
        version=1,
        content_json='{"sections": [{"title": "Experience", "content": "Test"}]}',
    )
    db_session.add(resume)
    db_session.commit()

    # Retrieve and verify
    retrieved = db_session.query(ResumeVersion).filter_by(session_id="test-session-002").first()
    assert retrieved is not None
    assert retrieved.version == 1
    assert retrieved.session_id == "test-session-002"
    assert retrieved.created_at is not None

    # Verify relationship
    parent = db_session.query(AnalysisSession).filter_by(session_id="test-session-002").first()
    assert len(parent.resume_versions) == 1
    assert parent.resume_versions[0].version == 1


def test_create_uploaded_file(db_session: Session):
    """Test creating an UploadedFile linked to a session."""
    # Create parent session
    session = AnalysisSession(session_id="test-session-003", stage="init")
    db_session.add(session)
    db_session.commit()

    # Create uploaded file
    file = UploadedFile(
        session_id="test-session-003",
        filename="resume.pdf",
        file_type="resume",
        file_path="/uploads/resume.pdf",
        file_size=1024,
    )
    db_session.add(file)
    db_session.commit()

    # Retrieve and verify
    retrieved = db_session.query(UploadedFile).filter_by(session_id="test-session-003").first()
    assert retrieved is not None
    assert retrieved.filename == "resume.pdf"
    assert retrieved.file_type == "resume"
    assert retrieved.file_size == 1024

    # Verify relationship
    parent = db_session.query(AnalysisSession).filter_by(session_id="test-session-003").first()
    assert len(parent.uploaded_files) == 1
    assert parent.uploaded_files[0].filename == "resume.pdf"
