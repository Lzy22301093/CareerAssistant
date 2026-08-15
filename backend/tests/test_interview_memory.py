"""Interview Memory Service 测试（M3 长久陪伴）。"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.llm import Response
from app.models.database import Base
from app.models.orm import InterviewLog
from app.services.interview_memory import InterviewMemoryService
from app.services.memory_service import MemoryService


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    yield TestSession
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def svc(db_factory):
    return InterviewMemoryService(db_factory=db_factory)


class MockLLM:
    def __init__(self, response: str):
        self._response = response

    async def chat(self, messages, **kwargs):
        return Response(content=self._response)


# === 追问逻辑 ===


class TestDraftFlow:
    def test_next_question_order(self, svc):
        assert "公司" in svc.next_question({})
        assert "岗位" in svc.next_question({"company": "腾讯"})
        assert "结果" in svc.next_question({"company": "腾讯", "job_title": "后端"})
        assert "问题" in svc.next_question({"company": "腾讯", "job_title": "后端", "result": "failed"})

    def test_is_complete(self, svc):
        assert svc.is_complete({"company": "腾讯", "job_title": "后端", "result": "failed"}) is True
        assert svc.is_complete({"company": "腾讯", "job_title": "后端"}) is False
        assert svc.is_complete({}) is False


# === 解析 ===


class TestParseReply:
    @pytest.mark.asyncio
    async def test_parse_extracts_fields(self, svc):
        llm = MockLLM(json.dumps({
            "company": "腾讯", "job_title": "后端工程师", "result": "failed",
            "questions": ["Redis 原理"], "weak_points": ["Redis 底层原理"],
        }))
        draft = await svc.parse_interview_reply(llm, "面试了腾讯后端，挂了，问了Redis", {})
        assert draft["company"] == "腾讯"
        assert draft["result"] == "failed"
        assert draft["weak_points"] == ["Redis 底层原理"]

    @pytest.mark.asyncio
    async def test_parse_merges_not_overwrites(self, svc):
        llm = MockLLM(json.dumps({"questions": ["系统设计"], "weak_points": ["系统设计"]}))
        draft = await svc.parse_interview_reply(
            llm, "还问了系统设计", {"company": "腾讯", "job_title": "后端", "result": "pending"}
        )
        assert draft["company"] == "腾讯"  # 已收集的不被覆盖
        assert draft["questions"] == ["系统设计"]

    @pytest.mark.asyncio
    async def test_parse_bad_output_keeps_draft(self, svc):
        llm = MockLLM("不是 JSON")
        draft = await svc.parse_interview_reply(llm, "随便", {"company": "腾讯"})
        assert draft["company"] == "腾讯"


# === 入库 ===


class TestRecordInterview:
    def test_record_and_lessons_update_gaps(self, svc, db_factory):
        memory = MemoryService(db_factory=db_factory)
        memory.upsert_profile(1, {"name": "张三", "skills": ["Python"]})

        log = svc.record_interview(1, {
            "company": "腾讯", "job_title": "后端", "result": "failed",
            "questions": ["Redis"], "weak_points": ["Redis 底层原理"],
        })
        assert log is not None
        assert log.result == "failed"

        # 教训写入 career_profile gaps
        profile = memory.get_profile(1)
        assert "Redis 底层原理" in (profile.get("gaps") or [])

    def test_record_incomplete_skipped(self, svc):
        log = svc.record_interview(1, {"company": "腾讯"})
        assert log is None

    def test_recent_lessons(self, svc):
        svc.record_interview(1, {"company": "A", "job_title": "后端", "result": "failed", "weak_points": ["X"]})
        svc.record_interview(1, {"company": "B", "job_title": "前端", "result": "passed", "weak_points": []})
        lessons = svc.recent_lessons(1)
        assert len(lessons) == 1  # 只有失败/有失分点的
        assert lessons[0]["company"] == "A"


# === 复习计划 ===


class TestReviewPlan:
    @pytest.mark.asyncio
    async def test_plan_with_lessons(self, svc, db_factory):
        svc.record_interview(1, {"company": "A", "job_title": "后端", "result": "failed", "weak_points": ["Redis"]})
        llm = MockLLM(json.dumps({"items": [
            {"topic": "Redis 底层原理", "reason": "上次面试失分", "suggestion": "复习数据结构与持久化"}
        ]}))
        plan = await svc.build_review_plan(llm, 1, {"keywords": ["Redis"]}, {"overall_score": 70})
        assert plan["has_lessons"] is True
        assert plan["items"][0]["topic"] == "Redis 底层原理"

    @pytest.mark.asyncio
    async def test_plan_without_lessons(self, svc):
        llm = MockLLM(json.dumps({"items": []}))
        plan = await svc.build_review_plan(llm, 999, {"keywords": ["Redis"]})
        assert plan["items"] == []
        assert plan["has_lessons"] is False

    @pytest.mark.asyncio
    async def test_plan_generation_failure_graceful(self, svc, db_factory):
        svc.record_interview(1, {"company": "A", "job_title": "后端", "result": "failed", "weak_points": ["Redis"]})
        llm = MockLLM("坏数据")
        plan = await svc.build_review_plan(llm, 1, {"keywords": ["Redis"]})
        assert plan["items"] == []
        assert plan["has_lessons"] is True  # 有教训但生成失败，不报错