"""Memory Service 测试（v3）— career_profile 规则合并 + consolidate 提炼。"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.llm import Response
from app.models.database import Base
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
def memory(db_factory):
    return MemoryService(db_factory=db_factory)


class TestUpsertProfile:
    def test_first_upsert_creates(self, memory):
        merged = memory.upsert_profile(1, {"name": "张三", "skills": ["Python", "FastAPI"]})
        assert merged["name"] == "张三"
        assert merged["skills"] == ["Python", "FastAPI"]
        # 可再次读取
        assert memory.get_profile(1)["name"] == "张三"

    def test_skills_merge_dedupe(self, memory):
        memory.upsert_profile(1, {"name": "张三", "skills": ["Python", "FastAPI"]})
        merged = memory.upsert_profile(1, {"name": "张三", "skills": ["Python", "Docker"]})
        assert merged["skills"] == ["Python", "FastAPI", "Docker"]

    def test_experience_merge_by_company_title(self, memory):
        exp1 = [{"company": "A公司", "title": "工程师", "highlights": ["做了X"]}]
        memory.upsert_profile(1, {"name": "张三", "experience": exp1})
        exp2 = [{"company": "A公司", "title": "工程师", "highlights": ["做了Y"]},  # 重复项
                {"company": "B公司", "title": "主管", "highlights": ["带了团队"]}]  # 新项
        merged = memory.upsert_profile(1, {"name": "张三", "experience": exp2})
        companies = [e["company"] for e in merged["experience"]]
        assert companies == ["B公司", "A公司"]  # 新项在前，重复去重

    def test_unknown_fields_rejected(self, memory):
        merged = memory.upsert_profile(1, {"name": "张三", "evil_field": "不该写入"})
        assert "evil_field" not in merged

    def test_get_nonexistent(self, memory):
        assert memory.get_profile(999) is None

    def test_preferences_empty(self, memory):
        assert memory.get_preferences(1) == {}


class TestBuildSummary:
    def test_summary_contains_profile_and_preferences(self, memory):
        memory.upsert_profile(1, {"name": "张三", "skills": ["Python"]})
        summary = memory.build_summary(1)
        assert summary["profile"]["name"] == "张三"
        assert "preferences" in summary

    def test_summary_no_user(self, memory):
        summary = memory.build_summary(999)
        assert summary["profile"] == {}


class TestConsolidate:
    """consolidate 提炼（LLM 一步 + 白名单校验 + 落库）。"""

    class MockLLM:
        def __init__(self, response: str):
            self._response = response
            self.call_count = 0

        async def chat(self, messages, **kwargs):
            self.call_count += 1
            return Response(content=self._response)

    def _valid_response(self):
        return json.dumps({
            "updates": [
                {"op": "add", "field": "skills", "value": "Docker", "reason": "用户提到"},
                {"op": "update", "field": "target_roles", "value": "项目经理", "reason": "明确目标"},
            ]
        })

    @pytest.mark.asyncio
    async def test_consolidate_merges_and_persists(self, memory):
        memory.upsert_profile(1, {"name": "张三", "skills": ["Python"]})
        llm = self.MockLLM(self._valid_response())
        merged = await memory.consolidate(llm, 1, "我最近在学 Docker，想转项目经理")
        assert "Docker" in merged["skills"]
        assert merged["target_roles"] == "项目经理"
        # 已落库
        assert "Docker" in memory.get_profile(1)["skills"]

    @pytest.mark.asyncio
    async def test_consolidate_invalid_field_rejected(self, memory):
        memory.upsert_profile(1, {"name": "张三"})
        llm = self.MockLLM(json.dumps({
            "updates": [
                {"op": "add", "field": "evil_field", "value": "不该写入", "reason": "x"},
            ]
        }))
        merged = await memory.consolidate(llm, 1, "随便")
        assert "evil_field" not in merged

    @pytest.mark.asyncio
    async def test_consolidate_no_changes_keeps_profile(self, memory):
        memory.upsert_profile(1, {"name": "张三", "skills": ["Python"]})
        llm = self.MockLLM(json.dumps({"updates": []}))
        merged = await memory.consolidate(llm, 1, "没什么新信息")
        assert merged["name"] == "张三"

    @pytest.mark.asyncio
    async def test_consolidate_invalid_output_graceful(self, memory):
        memory.upsert_profile(1, {"name": "张三", "skills": ["Python"]})
        llm = self.MockLLM("完全不是 JSON")
        merged = await memory.consolidate(llm, 1, "测试")
        # 校验失败静默返回现有档案，不抛异常
        assert merged["name"] == "张三"
