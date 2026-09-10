"""Tests for ApplicationService（阶段3 指令3-3：投递记录手动新增 + 状态提醒）。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import User
from app.models.schemas import JobApplicationCreate, JobApplicationUpdate
from app.services.application_service import ApplicationError, ApplicationService


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


def _svc() -> ApplicationService:
    return ApplicationService()


def test_create_and_list(db_session: Session):
    svc = _svc()
    app = svc.create(db_session, 1, JobApplicationCreate(company="字节跳动", job_title="后端开发"))
    assert app.id and app.status == "applied"
    assert len(svc.list(db_session, 1)) == 1


def test_search_by_company_or_title(db_session: Session):
    svc = _svc()
    svc.create(db_session, 1, JobApplicationCreate(company="字节跳动", job_title="后端开发"))
    svc.create(db_session, 1, JobApplicationCreate(company="腾讯", job_title="前端开发"))
    assert len(svc.list(db_session, 1, q="字节")) == 1
    assert len(svc.list(db_session, 1, q="前端")) == 1
    assert len(svc.list(db_session, 1, q="不存在")) == 0


def test_filter_by_status_and_result(db_session: Session):
    svc = _svc()
    svc.create(db_session, 1, JobApplicationCreate(company="A", job_title="x", status="applied"))
    svc.create(db_session, 1, JobApplicationCreate(company="B", job_title="y", status="interview"))
    svc.create(db_session, 1, JobApplicationCreate(company="C", job_title="z", status="offer"))
    assert len(svc.list(db_session, 1, status="interview")) == 1
    assert len(svc.list(db_session, 1, result="ongoing")) == 2
    assert len(svc.list(db_session, 1, result="passed")) == 1
    with pytest.raises(ApplicationError):
        svc.list(db_session, 1, result="bogus")


def test_update_status(db_session: Session):
    svc = _svc()
    app = svc.create(db_session, 1, JobApplicationCreate(company="A", job_title="x"))
    out = svc.update(db_session, 1, app.id, JobApplicationUpdate(status="offer"))
    assert out.status == "offer"
    assert svc.serialize(out)["result"] == "passed"


def test_delete(db_session: Session):
    svc = _svc()
    app = svc.create(db_session, 1, JobApplicationCreate(company="A", job_title="x"))
    svc.delete(db_session, 1, app.id)
    assert len(svc.list(db_session, 1)) == 0


def test_summary_counts(db_session: Session):
    svc = _svc()
    svc.create(db_session, 1, JobApplicationCreate(company="A", job_title="x", status="applied"))
    svc.create(db_session, 1, JobApplicationCreate(company="B", job_title="y", status="interview"))
    svc.create(db_session, 1, JobApplicationCreate(company="C", job_title="z", status="offer"))
    svc.create(db_session, 1, JobApplicationCreate(company="D", job_title="w", status="rejected"))
    s = svc.summary(db_session, 1)
    assert s["total"] == 4
    assert s["by_result"]["ongoing"] == 2
    assert s["by_result"]["passed"] == 1
    assert s["by_result"]["failed"] == 1


def test_invalid_status_rejected(db_session: Session):
    svc = _svc()
    with pytest.raises(ApplicationError):
        svc.create(db_session, 1, JobApplicationCreate(company="A", job_title="x", status="bogus"))
