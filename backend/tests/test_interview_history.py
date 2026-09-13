"""Interview history API tests（直接覆盖鉴权依赖，聚焦历史查询）。"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import require_auth
from app.main import app
from app.models.database import Base, get_db
from app.models.orm import InterviewReport, User


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    user = User(username="u1", email="u1@test.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    user_dict = {"id": user.id, "username": user.username, "email": user.email}

    db.add(
        InterviewReport(
            interview_id="iv-1",
            user_id=user.id,
            target_position="后端实习",
            turn_count=3,
            completion_reason="max_turns",
            dimension_scores_json=json.dumps({"专业知识": 8}, ensure_ascii=False),
            strengths_json=json.dumps(["清晰"], ensure_ascii=False),
            weaknesses_json=json.dumps(["案例少"], ensure_ascii=False),
            conversation_history_json=json.dumps(
                [{"role": "assistant", "content": "你好"}, {"role": "user", "content": "我是谁"}],
                ensure_ascii=False,
            ),
            final_report_json=json.dumps(
                {"overall_score": 8.5, "summary": "表现不错"}, ensure_ascii=False
            ),
        )
    )
    db.commit()
    db.close()

    def _override_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    def _override_auth():
        return user_dict

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_auth] = _override_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_list_history(client: TestClient):
    res = client.get("/api/interview/history")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["interview_id"] == "iv-1"
    assert data[0]["overall_score"] == 8.5
    assert data[0]["target_position"] == "后端实习"


def test_history_detail(client: TestClient):
    res = client.get("/api/interview/history/iv-1")
    assert res.status_code == 200
    data = res.json()
    assert data["turn_count"] == 3
    assert len(data["conversation_history"]) == 2
    assert data["final_report"]["summary"] == "表现不错"


def test_history_detail_not_found(client: TestClient):
    res = client.get("/api/interview/history/missing")
    assert res.status_code == 404


def test_save_interview_report_sync_commit():
    """同步 Session 不能 await commit（回归：报告曾因此写不进库）。"""
    import asyncio

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.interview.session_service import save_interview_report
    from app.models.database import Base
    from app.models.orm import InterviewReport, User

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(username="u2", email="u2@test.com", hashed_password="x")
    db.add(user)
    db.commit()

    state = {
        "user_id": user.id,
        "session_id": "s1",
        "target_position": "后端",
        "difficulty_level": "medium",
        "turn_count": 2,
        "dimension_scores": {"专业知识": 8},
        "strengths": ["ok"],
        "weaknesses": [],
        "conversation_history": [{"role": "assistant", "content": "hi"}],
        "final_report": {"overall_score": 8, "summary": "不错"},
        "completion_reason": "max_turns",
    }
    asyncio.get_event_loop().run_until_complete(
        save_interview_report("iv-sync-1", state, db)
    )
    row = db.query(InterviewReport).filter_by(interview_id="iv-sync-1").first()
    assert row is not None
    assert row.user_id == user.id
    assert row.turn_count == 2
    db.close()
