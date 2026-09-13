"""调度/计划相关测试 — 测试执行计划构建与推进（v3 线性流水线）。"""

import json

import pytest

from app.agents import create_agents
from app.graph.edges import INTENT_PLAN, build_execution_plan
from app.graph.nodes import planner_node
from app.graph.state import GraphState
from app.llm import Message, Response, Role


# === Mock LLM ===

class MockLLM:
    def __init__(self, default_response: str = "{}"):
        self._rules: list[tuple[str, str]] = []
        self._default = default_response
        self.call_count = 0

    def when(self, contains: str, response: str) -> "MockLLM":
        self._rules.append((contains, response))
        return self

    async def chat(self, messages: list[Message], **kwargs) -> Response:
        self.call_count += 1
        content = " ".join(m.content for m in messages)
        for pattern, resp in self._rules:
            if pattern in content:
                return Response(content=resp)
        return Response(content=self._default)

    async def generate(self, prompt: str, **kwargs) -> str:
        resp = await self.chat([Message(role=Role.USER, content=prompt)], **kwargs)
        return resp.content


def _fresh_state(**overrides) -> GraphState:
    state: GraphState = {
        "user_message": "帮我优化简历",
        "session_id": "test-session",
        "uploaded_files": [],
        "content_iterations": 0,
        "interview_iterations": 0,
        "execution_plan": [],
        "workflow_trace": [],
        "clarification_history": [],
        "profile_input_version": 0,
        "profile_analyzed_version": -1,
        "jd_input_version": 0,
        "jd_analyzed_version": -1,
        "gap_based_jd": -1,
        "gap_based_profile": -1,
        "content_based_jd": -1,
        "content_based_profile": -1,
        "interview_based_jd": -1,
        "interview_based_profile": -1,
    }
    state.update(overrides)
    return state


# === build_execution_plan 测试 ===

class TestBuildExecutionPlan:
    def test_upload_jd_with_resume(self):
        """有简历的 JD 上传 → 完整流水线。"""
        state = _fresh_state(jd_text="Python 工程师", resume_text="张三简历")
        plan = build_execution_plan("upload_jd", state)
        assert plan == ["jd_analyzer", "profile_extractor", "gap_analyzer", "content_generator", "html_renderer", "interview_qa"]

    def test_upload_jd_without_resume(self):
        """无简历时只跑 jd_analyzer。"""
        state = _fresh_state(jd_text="Python 工程师")
        plan = build_execution_plan("upload_jd", state)
        assert plan == ["jd_analyzer"]

    def test_upload_jd_no_text(self):
        """无 JD 文本 → 空计划。"""
        state = _fresh_state()
        plan = build_execution_plan("upload_jd", state)
        assert plan == []

    def test_upload_profile_only(self):
        """有简历无 JD → 只跑 profile_extractor。"""
        state = _fresh_state(resume_text="张三简历")
        plan = build_execution_plan("upload_profile", state)
        assert plan == ["profile_extractor"]

    def test_upload_profile_no_text(self):
        """无简历文本 → 空计划。"""
        state = _fresh_state()
        plan = build_execution_plan("upload_profile", state)
        assert plan == []

    def test_gap_analysis_without_deps(self):
        """gap_analysis 无数据 → 空计划。"""
        state = _fresh_state()
        plan = build_execution_plan("gap_analysis", state)
        assert plan == []

    def test_gap_analysis_with_deps(self):
        """gap_analysis 有数据 → 执行 gap_analyzer。"""
        state = _fresh_state(jd_analysis={"job_title": "test"}, profile={"name": "test"})
        plan = build_execution_plan("gap_analysis", state)
        assert plan == ["gap_analyzer"]

    def test_content_edit_with_content(self):
        state = _fresh_state(resume_content={"sections": []}, profile={"name": "张三"}, jd_analysis={"keywords": []})
        plan = build_execution_plan("content_edit", state)
        assert plan == ["content_generator", "html_renderer"]

    def test_content_edit_without_content(self):
        """无 resume_content → 空计划。"""
        state = _fresh_state()
        plan = build_execution_plan("content_edit", state)
        assert plan == []

    def test_render_edit_without_content(self):
        """无 resume_content → 空计划。"""
        state = _fresh_state()
        plan = build_execution_plan("render_edit", state)
        assert plan == []

    def test_render_edit_with_content(self):
        """有 resume_content → 执行 html_renderer。"""
        state = _fresh_state(resume_content={"sections": []})
        plan = build_execution_plan("render_edit", state)
        assert plan == ["html_renderer"]

    def test_export_empty(self):
        plan = build_execution_plan("export", _fresh_state())
        assert plan == []

    def test_ask_question(self):
        plan = build_execution_plan("ask_question", _fresh_state())
        assert plan == ["question"]

    def test_generate_cover_letter(self):
        plan = build_execution_plan("generate_cover_letter", _fresh_state())
        assert plan == ["cover_letter"]

    def test_record_interview(self):
        plan = build_execution_plan("record_interview", _fresh_state())
        assert plan == ["clarifier"]


# === Planner 节点测试 ===

class TestPlannerNode:
    @pytest.mark.asyncio
    async def test_planner_generates_plan(self):
        """Planner 应生成 intent + execution_plan。"""
        llm = MockLLM(json.dumps({"intent": "upload_jd", "confidence": 0.95, "reason": "用户提供了 JD"}))
        agents = create_agents(llm)
        state = _fresh_state(jd_text="Python 工程师")
        result = await planner_node(state, agents)
        assert result["intent"] == "upload_jd"
        assert "execution_plan" in result
        assert result["execution_plan"]  # 非空

    @pytest.mark.asyncio
    async def test_planner_no_jd_no_resume(self):
        """无 JD 无简历时 upload_jd → 空计划。"""
        llm = MockLLM(json.dumps({"intent": "upload_jd", "confidence": 0.95, "reason": "用户要分析"}))
        agents = create_agents(llm)
        state = _fresh_state()
        result = await planner_node(state, agents)
        assert result["execution_plan"] == []
