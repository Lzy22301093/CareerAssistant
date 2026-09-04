"""Tests for MatchService（阶段2 指令2-4：岗位匹配任务化）。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.database import Base
from app.models.orm import MatchTask, ProfileItem, User
from app.models.schemas import JobPostingCreate, MatchTaskCreate
from app.services.matching_service import MatchError, MatchService

JD = {"job_title": "Agent 开发", "requirements": [{"category": "技能", "content": "RAG", "importance": "high"}]}
GAP = {
    "overall_score": 82,
    "strengths": ["RAG 实战"],
    "gaps": [{"category": "技能", "requirement": "跨端开发", "gap_severity": "major", "suggestion": "补充"}],
    "recommendations": ["强化 AB 实验经验"],
}
DRAFT = {"sections": [{"title": "技能", "content": "Python, RAG"}], "raw_text": "技能: Python, RAG"}


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    session.add(User(username="u1", email="u1@test.com", hashed_password="x"))
    session.commit()
    session.add(ProfileItem(user_id=1, category="skill", title="Python", content="3 年", status="confirmed"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_task(db: Session, page="one_page") -> MatchTask:
    svc = MatchService()
    posting = svc.create_posting(db, 1, JobPostingCreate(company="tiktok", title="agent开发", jd_text="负责 Agent/RAG 研发" * 10))
    return svc.create_task(db, 1, MatchTaskCreate(job_posting_id=posting.id, page_preference=page))


def _agents(jd=JD, gap=GAP, draft=DRAFT):
    return {
        "jd_analyzer": FakeAgent(jd),
        "gap_analyzer": FakeAgent(gap),
        "content_generator": FakeAgent(draft),
    }


def test_posting_and_task_crud(db_session: Session):
    svc = MatchService()
    posting = svc.create_posting(db_session, 1, JobPostingCreate(company="A", title="B", jd_text="jd"))
    assert posting.id and posting.source == "manual"
    assert len(svc.list_postings(db_session, 1)) == 1
    with pytest.raises(MatchError):
        svc.create_task(db_session, 1, MatchTaskCreate(job_posting_id=posting.id, page_preference="three"))
    with pytest.raises(MatchError):
        svc.create_task(db_session, 1, MatchTaskCreate(job_posting_id=999))
    task = svc.create_task(db_session, 1, MatchTaskCreate(job_posting_id=posting.id))
    assert task.stage == "created" and task.score is None
    svc.delete_task(db_session, 1, task.id)
    assert svc.list_tasks(db_session, 1) == []


async def test_run_matching_with_draft(db_session: Session):
    svc = MatchService()
    task = _make_task(db_session)
    agents = _agents()
    done = await svc.run_matching(db_session, 1, task.id, agents, with_draft=True)
    assert done.stage == "done" and done.score == 82
    summary = json.loads(done.summary_json)
    assert summary["company"] == "tiktok"
    assert len(summary["gaps"]) == 1 and summary["draft"]["sections"]
    steps = [h["step"] for h in summary["stage_history"]]
    assert steps == ["分析需求", "匹配定位", "重写内容", "校验格式"]
    # 画像上下文确实传给了 gap/content
    assert agents["gap_analyzer"].calls[0]["profile"]["skills"]
    assert "一页" in agents["content_generator"].calls[0]["user_instructions"]


async def test_run_matching_without_draft(db_session: Session):
    svc = MatchService()
    task = _make_task(db_session)
    agents = _agents()
    done = await svc.run_matching(db_session, 1, task.id, agents, with_draft=False)
    summary = json.loads(done.summary_json)
    assert summary["draft"] is None
    assert agents["content_generator"].calls == []
    assert [h["step"] for h in summary["stage_history"]] == ["分析需求", "匹配定位", "校验格式"]


async def test_run_matching_empty_profile_fails_clean(db_session: Session):
    svc = MatchService()
    db_session.query(ProfileItem).delete()
    db_session.commit()
    task = _make_task(db_session)
    with pytest.raises(MatchError):
        await svc.run_matching(db_session, 1, task.id, _agents())
    refreshed = svc.get_task(db_session, 1, task.id)
    assert refreshed.stage == "failed"
    history = json.loads(refreshed.summary_json)["stage_history"]
    assert history[-1]["status"] == "failed"


async def test_run_matching_agent_crash_marks_failed(db_session: Session):
    svc = MatchService()
    task = _make_task(db_session)

    class BoomAgent:
        async def run(self, **kwargs):
            raise RuntimeError("LLM timeout")

    agents = _agents()
    agents["gap_analyzer"] = BoomAgent()
    with pytest.raises(MatchError):
        await svc.run_matching(db_session, 1, task.id, agents)
    refreshed = svc.get_task(db_session, 1, task.id)
    assert refreshed.stage == "failed"
    summary = json.loads(refreshed.summary_json)
    assert "LLM timeout" in summary.get("error", "")


async def test_export_draft_to_library(db_session: Session):
    svc = MatchService()
    task = _make_task(db_session)
    with pytest.raises(MatchError):
        svc.export_draft_to_library(db_session, 1, task.id)  # 还没跑过
    await svc.run_matching(db_session, 1, task.id, _agents())
    doc, version = svc.export_draft_to_library(db_session, 1, task.id)
    assert doc.title == "tiktok·agent开发 定向简历"
    assert version.version == 1 and len(version.sections) == 1


def test_build_match_agents_uses_factory_tiers(db_session: Session):
    """匹配链路 agent 必须来自 create_agents 工厂（jd/gap 注入 FAST_MODEL 分层）。"""
    from app.config import settings

    from app.services.matching_service import build_match_agents

    class _L:
        pass

    agents = build_match_agents(_L())
    assert set(agents) == {"jd_analyzer", "gap_analyzer", "content_generator"}
    # FAST_MODEL 配置为空时工厂回落主模型（model=None）；配置时必须等于 fast_model
    expected = settings.fast_model or None
    assert agents["jd_analyzer"].model == expected
    assert agents["gap_analyzer"].model == expected
