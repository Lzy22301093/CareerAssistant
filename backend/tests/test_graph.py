"""Graph 层测试 — 测试 LangGraph 工作流编排（v3 线性流水线架构）。"""

import json

import pytest

from app.agents import create_agents
from app.graph.edges import INTENT_PLAN, advance_plan, build_execution_plan
from app.graph.nodes import (
    clarifier_node,
    content_generator_node,
    cover_letter_node,
    gap_analyzer_node,
    html_renderer_node,
    interview_qa_node,
    jd_analyzer_node,
    planner_node,
    profile_extractor_node,
    question_node,
)
from app.graph.state import GraphState
from app.graph.workflow import build_graph
from app.llm import Message, Response, Role


# === Mock LLM ===

class MockLLM:
    """可编程 Mock LLM。"""

    def __init__(self, default_response: str = "{}"):
        self._rules: list[tuple[str, str]] = []
        self._default = default_response
        self.call_count = 0
        self.last_messages: list[Message] = []

    def when(self, contains: str, response: str) -> "MockLLM":
        self._rules.append((contains, response))
        return self

    async def chat(self, messages: list[Message], **kwargs) -> Response:
        self.call_count += 1
        self.last_messages = messages
        content = " ".join(m.content for m in messages)
        for pattern, resp in self._rules:
            if pattern in content:
                return Response(content=resp)
        return Response(content=self._default)

    async def generate(self, prompt: str, **kwargs) -> str:
        resp = await self.chat([Message(role=Role.USER, content=prompt)], **kwargs)
        return resp.content


# === 样本数据 ===

SAMPLE_JD = json.dumps({
    "job_title": "Python 工程师",
    "company": "示例科技",
    "requirements": [{"category": "skill", "content": "Python", "importance": "high"}],
    "keywords": ["Python", "FastAPI"],
}, ensure_ascii=False)

SAMPLE_PROFILE = json.dumps({
    "name": "张三",
    "skills": ["Python", "FastAPI", "MySQL"],
    "experience": [{"company": "ABC", "title": "工程师", "duration": "2022-2024", "highlights": []}],
}, ensure_ascii=False)

SAMPLE_GAP = json.dumps({
    "overall_score": 80.0,
    "strengths": ["Python 经验"],
    "gaps": [{"category": "skill", "requirement": "K8s", "current_level": "无", "gap_severity": "minor", "suggestion": "学习"}],
    "recommendations": ["补充 K8s"],
}, ensure_ascii=False)

SAMPLE_CONTENT = json.dumps({
    "sections": [{"title": "个人信息", "content": "张三"}],
    "raw_text": "张三的简历",
}, ensure_ascii=False)

SAMPLE_RENDER = json.dumps({
    "template": "modern",
    "font_size": 11,
}, ensure_ascii=False)

SAMPLE_INTERVIEW = json.dumps({
    "questions": [{"question": "介绍一下 Python 经验", "category": "behavioral", "difficulty": "medium", "answer_points": [], "sample_answer": ""}],
}, ensure_ascii=False)

SAMPLE_CLARIFIER = json.dumps({
    "missing_items": ["company", "job_title"],
    "question": "请问面试的是哪家公司？什么岗位？",
    "suggestions": ["提供公司名和岗位"],
    "context_type": "interview_record",
}, ensure_ascii=False)


def _create_mock_llm() -> MockLLM:
    """创建预设好的 Mock LLM，匹配所有 Agent 的 prompt。"""
    llm = MockLLM("{}")
    # 意图分类（匹配 INTENT_CLASSIFICATION_PROMPT）
    llm.when("你是一个求职助手的意图分类器", json.dumps({"intent": "upload_jd", "confidence": 0.95, "reason": "用户提供了 JD"}, ensure_ascii=False))
    llm.when("提取关键词和短语", json.dumps({"keywords": ["Python", "FastAPI"]}, ensure_ascii=False))
    llm.when("分析以下职位描述", SAMPLE_JD)
    llm.when("请解析以下简历", SAMPLE_PROFILE)
    llm.when("分析两者的匹配度", SAMPLE_GAP)
    llm.when("生成针对性的简历内容", SAMPLE_CONTENT)
    llm.when("生成渲染配置", SAMPLE_RENDER)
    llm.when("生成面试题", SAMPLE_INTERVIEW)
    llm.when("判断缺少什么信息", SAMPLE_CLARIFIER)
    return llm


# === INTENT_PLAN 查表测试 ===

class TestIntentPlan:
    """测试意图 → 执行计划查表。"""

    def test_all_intents_have_entries(self):
        """所有 9 个意图都有对应的计划。"""
        expected_intents = {
            "upload_jd", "upload_profile", "gap_analysis", "content_edit",
            "render_edit", "export", "ask_question", "generate_cover_letter",
            "record_interview",
        }
        assert set(INTENT_PLAN.keys()) == expected_intents

    def test_upload_jd_plan(self):
        assert INTENT_PLAN["upload_jd"] == ["jd_analyzer", "profile_extractor", "gap_analyzer", "content_generator", "html_renderer", "interview_qa"]

    def test_upload_profile_plan(self):
        assert INTENT_PLAN["upload_profile"] == ["profile_extractor", "content_generator", "html_renderer", "interview_qa"]

    def test_export_empty_plan(self):
        assert INTENT_PLAN["export"] == []

    def test_ask_question_plan(self):
        assert INTENT_PLAN["ask_question"] == ["question"]

    def test_record_interview_plan(self):
        assert INTENT_PLAN["record_interview"] == ["clarifier"]


# === build_execution_plan 测试 ===

class TestBuildExecutionPlan:
    """测试执行计划构建（含状态感知截断）。"""

    def test_upload_jd_with_resume(self):
        """有简历的 JD 上传 → 完整流水线（节点 guard 处理运行时依赖）。"""
        state: GraphState = {"jd_text": "Python 工程师", "resume_text": "张三简历"}
        plan = build_execution_plan("upload_jd", state)
        assert plan == ["jd_analyzer", "profile_extractor", "gap_analyzer", "content_generator", "html_renderer", "interview_qa"]

    def test_upload_jd_without_resume(self):
        """无简历的 JD 上传 → 只有 jd_analyzer（防数据伪造）。"""
        state: GraphState = {"jd_text": "Python 工程师"}
        plan = build_execution_plan("upload_jd", state)
        assert plan == ["jd_analyzer"]

    def test_upload_profile_only(self):
        """只有简历上传无 JD → 截断为 profile_extractor。"""
        state: GraphState = {"resume_text": "张三简历"}
        plan = build_execution_plan("upload_profile", state)
        assert plan == ["profile_extractor"]

    def test_upload_profile_with_jd(self):
        """有简历且有 JD 分析 → 完整流水线。"""
        state: GraphState = {"resume_text": "张三简历", "jd_analysis": {"job_title": "test"}}
        plan = build_execution_plan("upload_profile", state)
        assert plan == ["profile_extractor", "content_generator", "html_renderer", "interview_qa"]

    def test_content_edit_without_content(self):
        """无简历内容时 content_edit → 空计划。"""
        state: GraphState = {}
        plan = build_execution_plan("content_edit", state)
        assert plan == []

    def test_content_edit_with_content(self):
        """有简历内容时 content_edit → content_generator + html_renderer。"""
        state: GraphState = {"resume_content": {"sections": []}}
        plan = build_execution_plan("content_edit", state)
        assert plan == ["content_generator", "html_renderer"]

    def test_content_edit_missing_deps(self):
        """content_edit 有 resume_content 但缺 profile/jd_analysis → 仍返回计划（节点 guard 处理）。"""
        state: GraphState = {"resume_content": {"sections": []}, "profile": {"name": "张三"}}
        plan = build_execution_plan("content_edit", state)
        assert plan == ["content_generator", "html_renderer"]

    def test_interview_qa_full_plan(self):
        """upload_jd 有简历 → 完整计划（节点 guard 在运行时检查依赖）。"""
        state: GraphState = {"jd_text": "Python 工程师", "resume_text": "张三简历"}
        plan = build_execution_plan("upload_jd", state)
        assert "interview_qa" in plan
        assert "jd_analyzer" in plan

    def test_unknown_intent(self):
        """未知意图 → 空计划。"""
        plan = build_execution_plan("unknown_intent", {})
        assert plan == []

    def test_gap_analysis_without_deps(self):
        """gap_analysis 无数据 → 空计划（编辑类意图需要上游数据已存在）。"""
        state: GraphState = {}
        plan = build_execution_plan("gap_analysis", state)
        assert plan == []

    def test_gap_analysis_with_deps(self):
        """gap_analysis 有数据 → 执行 gap_analyzer。"""
        state: GraphState = {"jd_analysis": {"job_title": "test"}, "profile": {"name": "test"}}
        plan = build_execution_plan("gap_analysis", state)
        assert plan == ["gap_analyzer"]


# === advance_plan 测试 ===

class TestAdvancePlan:
    """测试执行计划推进。"""

    def test_advance_pops_first(self):
        state: GraphState = {"execution_plan": ["jd_analyzer", "gap_analyzer"]}
        result = advance_plan(state)
        assert result == "jd_analyzer"

    def test_advance_returns_end_when_empty(self):
        state: GraphState = {"execution_plan": []}
        result = advance_plan(state)
        assert result == "__end__"

    def test_advance_returns_end_when_missing(self):
        state: GraphState = {}
        result = advance_plan(state)
        assert result == "__end__"


# === 节点函数测试 ===

class TestNodes:
    @pytest.mark.asyncio
    async def test_planner_node_upload_jd(self):
        """Planner：JD 上传意图 → 生成执行计划。"""
        llm = MockLLM(json.dumps({"intent": "upload_jd", "confidence": 0.95, "reason": "用户提供了 JD"}))
        agents = create_agents(llm)
        state: GraphState = {"user_message": "分析这个 JD", "session_id": "test", "jd_text": "Python 工程师"}
        result = await planner_node(state, agents)
        assert result["intent"] == "upload_jd"
        assert result["route"] == "jd_analyzer"
        assert "execution_plan" in result
        assert result["execution_plan"][0] == "jd_analyzer"

    @pytest.mark.asyncio
    async def test_planner_node_no_jd_no_resume(self):
        """Planner：无 JD 无简历 + 短消息 → 空计划。"""
        llm = MockLLM(json.dumps({"intent": "upload_jd", "confidence": 0.95, "reason": "用户要分析 JD"}))
        agents = create_agents(llm)
        state: GraphState = {"user_message": "帮我分析", "session_id": "test"}
        result = await planner_node(state, agents)
        # 短消息（< 50 字符）不作为 JD 文本 → 计划为空
        assert result["execution_plan"] == []

    @pytest.mark.asyncio
    async def test_planner_node_message_as_jd(self):
        """Planner：用户直接粘贴 JD 文本到消息中 → 提取为 jd_text，生成计划。"""
        jd_text = "岗位：Python 后端工程师。要求：3 年以上 Python 开发经验，熟悉 Django/Flask 框架，了解微服务架构和 Docker 容器化部署。"
        llm = MockLLM(json.dumps({"intent": "upload_jd", "confidence": 0.95, "reason": "用户提供了 JD"}))
        agents = create_agents(llm)
        state: GraphState = {"user_message": jd_text, "session_id": "test"}
        result = await planner_node(state, agents)
        assert result["intent"] == "upload_jd"
        assert result["jd_text"] == jd_text  # 消息被提取为 JD 文本
        assert result["execution_plan"][0] == "jd_analyzer"  # 计划非空

    @pytest.mark.asyncio
    async def test_planner_node_message_as_resume(self):
        """Planner：用户直接粘贴简历文本到消息中 → 提取为 resume_text，生成计划。"""
        resume_text = "张三，5 年 Python 开发经验，曾就职于阿里巴巴，负责后端架构设计，熟悉分布式系统和高并发处理。"
        llm = MockLLM(json.dumps({"intent": "upload_profile", "confidence": 0.95, "reason": "用户提供了简历"}))
        agents = create_agents(llm)
        state: GraphState = {"user_message": resume_text, "session_id": "test"}
        result = await planner_node(state, agents)
        assert result["intent"] == "upload_profile"
        assert result["resume_text"] == resume_text  # 消息被提取为简历文本
        assert result["execution_plan"][0] == "profile_extractor"  # 计划非空

    @pytest.mark.asyncio
    async def test_planner_gap_analysis_missing_data_falls_back_to_question(self):
        """gap_analysis 缺少 JD/画像 → 回落 question 自由问答，而不是空计划 END。"""
        llm = MockLLM(json.dumps({
            "intent": "gap_analysis",
            "confidence": 0.9,
            "reason": "用户问测试岗位要调整什么",
        }))
        agents = create_agents(llm)
        state: GraphState = {
            "user_message": "这是我的简历，我想找一份测试的工作，有哪些需要调整？",
            "session_id": "test",
        }
        result = await planner_node(state, agents)
        assert result["intent"] == "gap_analysis"
        assert result["execution_plan"] == ["question"]
        assert result["route"] == "question"

    @pytest.mark.asyncio
    async def test_jd_analyzer_node(self):
        llm = MockLLM(SAMPLE_JD)
        agents = create_agents(llm)
        state: GraphState = {"user_message": "Python 后端工程师", "jd_text": "Python 后端工程师"}
        result = await jd_analyzer_node(state, agents)
        assert "jd_analysis" in result
        assert result["jd_analysis"]["job_title"] == "Python 工程师"

    @pytest.mark.asyncio
    async def test_profile_extractor_node(self):
        llm = MockLLM(SAMPLE_PROFILE)
        agents = create_agents(llm)
        state: GraphState = {"user_message": "张三简历", "resume_text": "张三简历"}
        result = await profile_extractor_node(state, agents)
        assert "profile" in result
        assert result["profile"]["name"] == "张三"

    @pytest.mark.asyncio
    async def test_gap_analyzer_node(self):
        llm = MockLLM(SAMPLE_GAP)
        agents = create_agents(llm)
        state: GraphState = {
            "jd_analysis": {"job_title": "Python 工程师"},
            "profile": {"name": "张三"},
        }
        result = await gap_analyzer_node(state, agents)
        assert "gap_analysis" in result
        assert result["gap_analysis"]["overall_score"] == 80.0

    @pytest.mark.asyncio
    async def test_content_generator_node(self):
        llm = MockLLM(SAMPLE_CONTENT)
        agents = create_agents(llm)
        state: GraphState = {
            "profile": {"name": "张三"},
            "jd_analysis": {"job_title": "Python 工程师"},
        }
        result = await content_generator_node(state, agents)
        assert "resume_content" in result
        assert result["content_iterations"] == 1

    @pytest.mark.asyncio
    async def test_content_generator_guard_no_profile(self):
        """防伪造 guard：无 profile 时跳过。"""
        llm = MockLLM(SAMPLE_CONTENT)
        agents = create_agents(llm)
        state: GraphState = {"jd_analysis": {"job_title": "Python 工程师"}}
        result = await content_generator_node(state, agents)
        # guard 返回空 resume_content + skipped trace
        assert result.get("resume_content") == {}
        assert result.get("content_iterations", 0) == 0

    @pytest.mark.asyncio
    async def test_content_generator_guard_no_jd(self):
        """防伪造 guard：无 jd_analysis 时跳过。"""
        llm = MockLLM(SAMPLE_CONTENT)
        agents = create_agents(llm)
        state: GraphState = {"profile": {"name": "张三"}}
        result = await content_generator_node(state, agents)
        assert result.get("resume_content") == {}

    @pytest.mark.asyncio
    async def test_html_renderer_node(self):
        llm = MockLLM(SAMPLE_RENDER)
        agents = create_agents(llm)
        state: GraphState = {"resume_content": {"sections": []}}
        result = await html_renderer_node(state, agents)
        assert "render_config" in result
        assert result["render_config"]["template"] == "modern"

    @pytest.mark.asyncio
    async def test_interview_qa_node(self):
        llm = MockLLM(SAMPLE_INTERVIEW)
        agents = create_agents(llm)
        state: GraphState = {
            "jd_analysis": {"job_title": "Python 工程师"},
            "profile": {"name": "张三"},
            "gap_analysis": {"overall_score": 80},
        }
        result = await interview_qa_node(state, agents)
        assert "interview_questions" in result
        assert len(result["interview_questions"]["questions"]) == 1

    @pytest.mark.asyncio
    async def test_interview_qa_guard_no_jd(self):
        """降级 guard：无 jd_analysis 但有 profile 时仍然生成（降级模式）。"""
        llm = MockLLM(SAMPLE_INTERVIEW)
        agents = create_agents(llm)
        state: GraphState = {"profile": {"name": "张三", "skills": ["Python"]}}
        result = await interview_qa_node(state, agents)
        # 降级模式：有 profile 就尝试生成，不跳过
        questions = result.get("interview_questions", {}).get("questions", [])
        assert len(questions) > 0

    @pytest.mark.asyncio
    async def test_interview_qa_guard_no_profile(self):
        """降级 guard：无 profile 但有 jd_analysis 时仍然生成（降级模式）。"""
        llm = MockLLM(SAMPLE_INTERVIEW)
        agents = create_agents(llm)
        state: GraphState = {"jd_analysis": {"job_title": "Python 工程师", "keywords": ["Python"]}}
        result = await interview_qa_node(state, agents)
        questions = result.get("interview_questions", {}).get("questions", [])
        assert len(questions) > 0

    @pytest.mark.asyncio
    async def test_interview_qa_guard_both_missing(self):
        """防伪造 guard：JD 和 profile 均为空时跳过。"""
        llm = MockLLM(SAMPLE_INTERVIEW)
        agents = create_agents(llm)
        state: GraphState = {}
        result = await interview_qa_node(state, agents)
        assert result.get("interview_questions", {}).get("questions") == []
        trace = result.get("workflow_trace", [])
        assert trace and trace[0]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_clarifier_node_record_interview(self):
        """Clarifier：仅用于 record_interview 多轮追问。"""
        llm = MockLLM(json.dumps({"company": "腾讯", "job_title": "后端工程师", "result": "passed"}, ensure_ascii=False))
        agents = create_agents(llm)
        state: GraphState = {"intent": "record_interview", "user_message": "我面试过了"}
        result = await clarifier_node(state, agents)
        # 信息齐全 → 返回 interview_draft + 空计划
        assert "interview_draft" in result
        assert result.get("execution_plan") == []

    @pytest.mark.asyncio
    async def test_question_node(self):
        """自由问答节点：返回 answer。"""
        llm = MockLLM("你的 Python 经验与岗位匹配度较高。")
        agents = create_agents(llm)
        state: GraphState = {
            "user_message": "我匹配这个岗位吗",
            "jd_analysis": {"job_title": "Python 工程师", "keywords": ["Python"]},
            "profile": {"name": "张三", "skills": ["Python", "FastAPI"]},
        }
        result = await question_node(state, agents)
        assert "answer" in result
        assert "Python" in result["answer"]

    @pytest.mark.asyncio
    async def test_cover_letter_node(self):
        """求职信节点：生成指定渠道的文案。"""
        llm = MockLLM(json.dumps({
            "channel": "email", "subject": "应聘 Python 工程师",
            "body": "您好，我有 5 年 Python 开发经验。",
            "tone": "professional", "highlights": ["5年Python经验"],
        }, ensure_ascii=False))
        agents = create_agents(llm)
        state: GraphState = {
            "jd_analysis": {"job_title": "Python 工程师", "keywords": ["Python"]},
            "profile": {"name": "张三", "skills": ["Python"], "experience": []},
            "gap_analysis": {"overall_score": 80},
            "cover_letter_channel": "email",
            "user_message": "帮我写个求职信",
        }
        result = await cover_letter_node(state, agents)
        assert result["cover_letter"]["channel"] == "email"
        assert "body" in result["cover_letter"]


# === 完整图测试 ===

class TestWorkflow:
    @pytest.mark.asyncio
    async def test_build_graph(self):
        """测试图可以成功编译。"""
        llm = MockLLM()
        graph = build_graph(llm)
        assert graph is not None

    @pytest.mark.asyncio
    async def test_full_pipeline_jd_to_end(self):
        """测试完整流程：upload_jd 意图 → jd_analyzer → gap_analyzer → content_generator → html_renderer → interview_qa → END。"""
        llm = _create_mock_llm()
        graph = build_graph(llm)
        result = await graph.ainvoke({
            "user_message": "Python 后端工程师，要求 3 年经验",
            "session_id": "test-001",
            "jd_text": "Python 后端工程师，要求 3 年经验，熟悉 FastAPI",
            "resume_text": "张三，Python 工程师，3年经验",
        })
        # 验证各阶段输出
        assert result.get("jd_analysis", {}).get("job_title") == "Python 工程师"
        assert result.get("profile", {}).get("name") == "张三"
        assert result.get("gap_analysis", {}).get("overall_score") == 80.0
        assert result.get("resume_content", {}).get("sections") is not None
        assert result.get("render_config", {}).get("template") == "modern"
        assert result.get("interview_questions", {}).get("questions") is not None

    @pytest.mark.asyncio
    async def test_upload_jd_no_resume_short_circuit(self):
        """无简历时 JD 上传只跑 jd_analyzer，不伪造数据。"""
        llm = _create_mock_llm()
        graph = build_graph(llm)
        result = await graph.ainvoke({
            "user_message": "分析这个 JD",
            "session_id": "test-no-resume",
            "jd_text": "Python 后端工程师，要求 3 年经验",
        })
        assert result.get("jd_analysis") is not None
        # 无简历 → 不应生成 profile / resume_content / interview_questions
        assert result.get("profile") is None
        assert result.get("resume_content") is None
        assert result.get("interview_questions") is None

    @pytest.mark.asyncio
    async def test_ask_question_flow(self):
        """ask_question 意图 → question 节点 → END。"""
        llm = MockLLM("你与岗位匹配度较高。")
        llm.when("你是一个求职助手的意图分类器", json.dumps({"intent": "ask_question", "confidence": 0.95, "reason": "用户提问"}, ensure_ascii=False))
        graph = build_graph(llm)
        result = await graph.ainvoke({
            "user_message": "我匹配这个岗位吗",
            "session_id": "test-question",
            "jd_analysis": {"job_title": "Python 工程师", "keywords": ["Python"]},
            "profile": {"name": "张三", "skills": ["Python"]},
        })
        assert result.get("answer") is not None

    @pytest.mark.asyncio
    async def test_execution_plan_consumed(self):
        """执行计划在流程完成后应被清空。"""
        llm = _create_mock_llm()
        graph = build_graph(llm)
        result = await graph.ainvoke({
            "user_message": "分析 JD",
            "session_id": "test-plan-consumed",
            "jd_text": "Python 工程师",
            "resume_text": "张三简历",
        })
        assert result.get("execution_plan") == []
