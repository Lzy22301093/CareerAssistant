"""Agent 层单元测试 — Mock LLM 测试所有 Agent。"""

import json

import pytest

from app.agents.base import BaseAgent
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.profile_extractor import ProfileExtractorAgent
from app.agents.gap_analyzer import GapAnalyzerAgent
from app.agents.content_generator import ContentGeneratorAgent
from app.agents.html_renderer import HTMLRendererAgent
from app.agents.interview_qa import InterviewQAAgent
from app.agents.interview_reviewer import InterviewReviewerAgent
from app.agents.planner import PlannerAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.clarifier import ClarifierAgent
from app.agents import create_agents
from app.llm import LLMProvider, Message, Response, Role, ToolCall
from app.tools.base import Tool, ToolResult


# === Mock LLM ===

class MockLLM:
    """可编程的 Mock LLM，按优先级匹配 prompt 内容返回预设响应。"""

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


# === BaseAgent 测试 ===

class TestBaseAgent:
    """测试 BaseAgent 的通用功能。"""

    def test_extract_json_pure(self):
        """纯 JSON 字符串直接解析。"""
        text = '{"key": "value", "num": 42}'
        result = BaseAgent.extract_json(text)
        assert result == {"key": "value", "num": 42}

    def test_extract_json_markdown_block(self):
        """```json 包裹的 JSON。"""
        text = '这是分析结果：\n```json\n{"key": "value"}\n```\n以上是结果。'
        result = BaseAgent.extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_nested(self):
        """嵌套 JSON 对象。"""
        text = '结果：\n{"data": {"nested": true}, "list": [1, 2, 3]}'
        result = BaseAgent.extract_json(text)
        assert result is not None
        assert result["data"]["nested"] is True
        assert result["list"] == [1, 2, 3]

    def test_extract_json_invalid(self):
        """非 JSON 文本返回 None。"""
        result = BaseAgent.extract_json("这是一段普通文本，没有 JSON。")
        assert result is None

    def test_create_agents_registry(self):
        """create_agents 创建所有 12 个 Agent。"""
        llm = MockLLM()
        agents = create_agents(llm)
        assert len(agents) == 12
        expected_names = [
            "jd_analyzer", "profile_extractor", "gap_analyzer",
            "content_generator", "html_renderer", "interview_qa",
            "interview_reviewer", "planner", "question", "cover_letter",
        ]
        for name in expected_names:
            assert name in agents
            assert isinstance(agents[name], BaseAgent)


# === JDAnalyzerAgent 测试 ===

SAMPLE_JD_RESPONSE = json.dumps({
    "job_title": "Python 后端工程师",
    "company": "示例科技",
    "location": "北京",
    "salary_range": "25-40K",
    "summary": "负责后端服务开发",
    "requirements": [
        {"category": "skill", "content": "Python 3.8+", "importance": "high"},
        {"category": "skill", "content": "FastAPI/Django", "importance": "high"},
        {"category": "experience", "content": "3年以上后端开发经验", "importance": "medium"},
    ],
    "nice_to_have": ["Kubernetes", "Rust"],
    "keywords": ["Python", "FastAPI", "MySQL", "Redis", "Docker"],
}, ensure_ascii=False)


class TestJDAnalyzerAgent:
    def test_build_messages(self):
        llm = MockLLM()
        agent = JDAnalyzerAgent(llm)
        messages = agent.build_messages(jd_text="Python 后端工程师，要求 3 年经验")
        assert len(messages) == 2
        assert messages[0].role == Role.SYSTEM
        assert messages[1].role == Role.USER
        assert "Python 后端工程师" in messages[1].content

    @pytest.mark.asyncio
    async def test_parse_valid_json(self):
        llm = MockLLM(SAMPLE_JD_RESPONSE)
        agent = JDAnalyzerAgent(llm)
        result = await agent.run(jd_text="Python 后端工程师")
        assert result["job_title"] == "Python 后端工程师"
        assert len(result["requirements"]) == 3
        assert "Python" in result["keywords"]

    @pytest.mark.asyncio
    async def test_parse_json_with_markdown(self):
        wrapped = f"```json\n{SAMPLE_JD_RESPONSE}\n```"
        llm = MockLLM(wrapped)
        agent = JDAnalyzerAgent(llm)
        result = await agent.run(jd_text="test")
        assert result["job_title"] == "Python 后端工程师"

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        llm = MockLLM("这不是 JSON")
        agent = JDAnalyzerAgent(llm)
        result = await agent.run(jd_text="test")
        assert result.get("_parse_error") is True
        assert result["job_title"] == ""


# === ProfileExtractorAgent 测试 ===

SAMPLE_PROFILE_RESPONSE = json.dumps({
    "name": "张三",
    "email": "zhangsan@example.com",
    "phone": "13800138000",
    "summary": "5年 Python 开发经验",
    "skills": ["Python", "FastAPI", "MySQL", "Redis", "Docker", "Git"],
    "experience": [
        {
            "company": "示例科技",
            "title": "高级后端工程师",
            "duration": "2022-2024",
            "highlights": ["主导微服务架构重构", "API 性能提升 40%"],
        }
    ],
    "projects": [
        {
            "name": "电商系统",
            "description": "高并发电商后端",
            "tech_stack": ["Python", "FastAPI", "Redis"],
            "highlights": ["支撑 10 万 QPS"],
        }
    ],
    "education": [
        {"school": "北京大学", "degree": "本科", "major": "计算机科学", "year": "2019"}
    ],
    "certifications": ["AWS Solutions Architect"],
}, ensure_ascii=False)


class TestProfileExtractorAgent:
    def test_build_messages(self):
        llm = MockLLM()
        agent = ProfileExtractorAgent(llm)
        messages = agent.build_messages(resume_text="张三，5年 Python 经验")
        assert len(messages) == 2
        assert "张三" in messages[1].content

    @pytest.mark.asyncio
    async def test_parse_valid_json(self):
        llm = MockLLM(SAMPLE_PROFILE_RESPONSE)
        agent = ProfileExtractorAgent(llm)
        result = await agent.run(resume_text="张三简历")
        assert result["name"] == "张三"
        assert len(result["skills"]) == 6
        assert len(result["experience"]) == 1

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        llm = MockLLM("这不是 JSON")
        agent = ProfileExtractorAgent(llm)
        result = await agent.run(resume_text="test")
        assert result.get("_parse_error") is True


# === GapAnalyzerAgent 测试 ===

SAMPLE_GAP_RESPONSE = json.dumps({
    "overall_score": 75.0,
    "strengths": ["Python 经验丰富", "有微服务架构经验"],
    "gaps": [
        {
            "category": "skill",
            "requirement": "Kubernetes",
            "current_level": "无经验",
            "gap_severity": "major",
            "suggestion": "学习 K8s 基础并完成一个部署项目",
        }
    ],
    "recommendations": ["补充 K8s 知识", "准备系统设计面试"],
}, ensure_ascii=False)


class TestGapAnalyzerAgent:
    def test_build_messages(self):
        llm = MockLLM()
        agent = GapAnalyzerAgent(llm)
        messages = agent.build_messages(
            jd_analysis={"job_title": "Python 工程师"},
            profile={"name": "张三"},
        )
        assert len(messages) == 2
        assert "职位分析" in messages[1].content

    @pytest.mark.asyncio
    async def test_parse_valid_json(self):
        llm = MockLLM(SAMPLE_GAP_RESPONSE)
        agent = GapAnalyzerAgent(llm)
        result = await agent.run(
            jd_analysis={"job_title": "Python 工程师"},
            profile={"name": "张三"},
        )
        assert result["overall_score"] == 75.0
        assert len(result["gaps"]) == 1

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        llm = MockLLM("这不是 JSON")
        agent = GapAnalyzerAgent(llm)
        result = await agent.run(jd_analysis={}, profile={})
        assert result.get("_parse_error") is True
        assert result["overall_score"] == 0.0


# === ContentGeneratorAgent 测试 ===

SAMPLE_CONTENT_RESPONSE = json.dumps({
    "sections": [
        {"title": "个人信息", "content": "张三 | zhangsan@example.com"},
        {"title": "专业技能", "content": "Python, FastAPI, MySQL, Redis, Docker"},
        {"title": "工作经历", "content": "示例科技 - 高级后端工程师 (2022-2024)"},
    ],
    "raw_text": "张三的简历内容...",
}, ensure_ascii=False)


class TestContentGeneratorAgent:
    def test_build_messages_with_gap(self):
        llm = MockLLM()
        agent = ContentGeneratorAgent(llm)
        messages = agent.build_messages(
            profile={"name": "张三"},
            jd_analysis={"job_title": "Python 工程师"},
            gap_analysis={"overall_score": 75},
            user_instructions="突出项目经验",
        )
        assert len(messages) == 2
        content = messages[1].content
        assert "候选人画像" in content
        assert "差距分析" in content
        assert "突出项目经验" in content

    def test_build_messages_without_gap(self):
        llm = MockLLM()
        agent = ContentGeneratorAgent(llm)
        messages = agent.build_messages(
            profile={"name": "张三"},
            jd_analysis={"job_title": "Python 工程师"},
        )
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_parse_valid_json(self):
        llm = MockLLM(SAMPLE_CONTENT_RESPONSE)
        agent = ContentGeneratorAgent(llm)
        result = await agent.run(profile={}, jd_analysis={})
        assert len(result["sections"]) == 3
        assert result["sections"][0]["title"] == "个人信息"

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        llm = MockLLM("这不是 JSON")
        agent = ContentGeneratorAgent(llm)
        result = await agent.run(profile={}, jd_analysis={})
        assert result.get("_parse_error") is True
        assert result["sections"] == []


# === HTMLRendererAgent 测试 ===

SAMPLE_RENDER_RESPONSE = json.dumps({
    "template": "modern",
    "font_size": 11,
    "line_spacing": 1.15,
    "margin_top": 1.0,
    "margin_bottom": 1.0,
    "margin_left": 1.0,
    "margin_right": 1.0,
    "accent_color": "#2563eb",
    "layout_notes": "使用现代风格，突出技术栈",
}, ensure_ascii=False)


class TestHTMLRendererAgent:
    def test_build_messages(self):
        llm = MockLLM()
        agent = HTMLRendererAgent(llm)
        messages = agent.build_messages(
            resume_content={"sections": []},
            style_preferences="简洁风格",
        )
        assert len(messages) == 2
        assert "简洁风格" in messages[1].content

    @pytest.mark.asyncio
    async def test_parse_valid_json(self):
        llm = MockLLM(SAMPLE_RENDER_RESPONSE)
        agent = HTMLRendererAgent(llm)
        result = await agent.run(resume_content={})
        assert result["template"] == "modern"
        assert result["font_size"] == 11

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        llm = MockLLM("这不是 JSON")
        agent = HTMLRendererAgent(llm)
        result = await agent.run(resume_content={})
        assert result.get("_parse_error") is True
        assert result["template"] == "modern"  # 降级默认值


# === InterviewQAAgent 测试 ===

SAMPLE_INTERVIEW_RESPONSE = json.dumps({
    "questions": [
        {
            "question": "请介绍一下你的微服务架构经验",
            "category": "behavioral",
            "difficulty": "medium",
            "answer_points": ["架构设计", "技术选型", "遇到的挑战", "解决方案"],
            "sample_answer": "在上一家公司，我主导了微服务架构重构...",
        },
        {
            "question": "如何优化 FastAPI 的性能？",
            "category": "technical",
            "difficulty": "hard",
            "answer_points": ["异步编程", "缓存策略", "数据库优化"],
            "sample_answer": "可以通过异步 IO、Redis 缓存、数据库连接池等方式优化...",
        },
    ],
}, ensure_ascii=False)


class TestInterviewQAAgent:
    def test_build_messages(self):
        llm = MockLLM()
        agent = InterviewQAAgent(llm)
        messages = agent.build_messages(
            jd_analysis={"job_title": "Python 工程师"},
            profile={"name": "张三"},
        )
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_parse_valid_json(self):
        llm = MockLLM(SAMPLE_INTERVIEW_RESPONSE)
        agent = InterviewQAAgent(llm)
        result = await agent.run(jd_analysis={}, profile={})
        assert len(result["questions"]) == 2
        assert result["questions"][0]["category"] == "behavioral"

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        llm = MockLLM("这不是 JSON")
        agent = InterviewQAAgent(llm)
        result = await agent.run(jd_analysis={}, profile={})
        assert result.get("_parse_error") is True
        assert result["questions"] == []


# === PlannerAgent 测试 ===

class TestPlannerAgent:
    def test_build_messages(self):
        llm = MockLLM()
        agent = PlannerAgent(llm)
        messages = agent.build_messages(
            user_message="帮我分析这个 JD",
            session_state={"stage": "init"},
        )
        assert len(messages) == 2
        assert "帮我分析这个 JD" in messages[1].content
        assert "init" in messages[0].content

    @pytest.mark.asyncio
    async def test_route_jd_analyzer(self):
        response = json.dumps({"route": "jd_analyzer", "reason": "用户提供了 JD"})
        llm = MockLLM(response)
        agent = PlannerAgent(llm)
        result = await agent.run(user_message="分析 JD", session_state={})
        assert result["route"] == "jd_analyzer"

    @pytest.mark.asyncio
    async def test_route_profile_extractor(self):
        response = json.dumps({"route": "profile_extractor", "reason": "用户提供了简历"})
        llm = MockLLM(response)
        agent = PlannerAgent(llm)
        result = await agent.run(user_message="解析简历", session_state={})
        assert result["route"] == "profile_extractor"

    @pytest.mark.asyncio
    async def test_route_clarify(self):
        response = json.dumps({"route": "clarify", "reason": "信息不完整"})
        llm = MockLLM(response)
        agent = PlannerAgent(llm)
        result = await agent.run(user_message="帮我优化简历", session_state={})
        assert result["route"] == "clarify"

    @pytest.mark.asyncio
    async def test_route_fuzzy_match(self):
        """模糊匹配：返回的 route 名称不完全匹配时应尝试匹配。"""
        response = json.dumps({"route": "use jd_analyzer", "reason": "..."})
        llm = MockLLM(response)
        agent = PlannerAgent(llm)
        result = await agent.run(user_message="test", session_state={})
        assert result["route"] == "jd_analyzer"

    @pytest.mark.asyncio
    async def test_route_invalid_fallback(self):
        """无法识别的路由降级为 clarify。"""
        llm = MockLLM("这不是 JSON")
        agent = PlannerAgent(llm)
        result = await agent.run(user_message="test", session_state={})
        assert result["route"] == "clarify"
        assert result.get("_parse_error") is True


# === ClarifierAgent 测试 ===

SAMPLE_CLARIFIER_RESPONSE = json.dumps({
    "missing_items": ["jd", "resume"],
    "question": "您好！请提供目标职位的 JD 和您的简历信息。",
    "suggestions": ["粘贴 JD 文本", "上传简历文件"],
    "context_type": "initial",
}, ensure_ascii=False)


class TestClarifierAgent:
    def test_build_messages(self):
        llm = MockLLM()
        agent = ClarifierAgent(llm)
        messages = agent.build_messages(
            user_message="帮我优化简历",
            session_state={"has_jd": False, "has_profile": False},
            route_reason="信息不完整",
        )
        assert len(messages) == 2
        assert "缺少" in messages[1].content

    @pytest.mark.asyncio
    async def test_parse_valid_json(self):
        llm = MockLLM(SAMPLE_CLARIFIER_RESPONSE)
        agent = ClarifierAgent(llm)
        result = await agent.run(user_message="test", session_state={})
        assert "JD" in result["question"]
        assert len(result["suggestions"]) == 2
        assert result["context_type"] == "initial"

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        llm = MockLLM("请提供更多信息")
        agent = ClarifierAgent(llm)
        result = await agent.run(user_message="test", session_state={})
        assert result.get("_parse_error") is True
        assert "请提供更多信息" in result["question"]

    @pytest.mark.asyncio
    async def test_detects_missing_jd(self):
        """检测缺少 JD。"""
        response = json.dumps({
            "missing_items": ["jd"],
            "question": "请提供目标职位描述。",
            "suggestions": ["粘贴 JD"],
            "context_type": "partial_resume",
        }, ensure_ascii=False)
        llm = MockLLM(response)
        agent = ClarifierAgent(llm)
        result = await agent.run(
            user_message="优化简历",
            session_state={"has_jd": False, "has_profile": True},
        )
        assert "jd" in result["missing_items"]
        assert result["context_type"] == "partial_resume"


# === ReviewerAgent 测试 ===

SAMPLE_REVIEWER_RESPONSE = json.dumps({
    "score": 78,
    "dimensions": {
        "keyword_coverage": {"score": 80, "comment": "关键词覆盖良好"},
        "achievement_quantification": {"score": 70, "comment": "部分成就缺少量化"},
        "relevance": {"score": 85, "comment": "与目标职位相关性强"},
        "clarity": {"score": 75, "comment": "表达清晰"},
        "completeness": {"score": 80, "comment": "板块齐全"},
    },
    "issues": [
        {"severity": "medium", "description": "工作经历缺少量化数据", "section": "工作经历"},
    ],
    "suggestions": [
        {"priority": "high", "suggestion": "为每个项目添加量化成果", "section": "项目经历"},
    ],
    "summary": "简历整体质量良好，建议增加量化数据",
}, ensure_ascii=False)


class TestReviewerAgent:
    def test_build_messages(self):
        llm = MockLLM()
        agent = ReviewerAgent(llm)
        messages = agent.build_messages(
            resume_content={"sections": [{"title": "技能", "content": "Python"}]},
            jd_analysis={"job_title": "Python 工程师"},
            profile={"name": "张三"},
        )
        assert len(messages) == 2
        assert "Python" in messages[1].content

    @pytest.mark.asyncio
    async def test_parse_valid_json(self):
        llm = MockLLM(SAMPLE_REVIEWER_RESPONSE)
        agent = ReviewerAgent(llm)
        result = await agent.run(resume_content={}, jd_analysis={}, profile={})
        assert result["score"] == 78
        assert len(result["dimensions"]) == 5
        assert result["dimensions"]["keyword_coverage"]["score"] == 80
        assert len(result["issues"]) == 1
        assert len(result["suggestions"]) == 1

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        llm = MockLLM("这不是 JSON")
        agent = ReviewerAgent(llm)
        result = await agent.run(resume_content={}, jd_analysis={}, profile={})
        assert result.get("_parse_error") is True
        assert result["score"] == 0
        assert result["dimensions"] == {}


# === 集成测试：Agent 管道 ===

class TestAgentPipeline:
    """测试 Agent 之间的数据流转。"""

    @pytest.mark.asyncio
    async def test_jd_to_gap_pipeline(self):
        """JD 分析结果 → 差距分析的数据流。"""
        # 1. JD 分析
        jd_llm = MockLLM(SAMPLE_JD_RESPONSE)
        jd_agent = JDAnalyzerAgent(jd_llm)
        jd_result = await jd_agent.run(jd_text="Python 后端工程师")

        # 2. 画像提取
        profile_llm = MockLLM(SAMPLE_PROFILE_RESPONSE)
        profile_agent = ProfileExtractorAgent(profile_llm)
        profile_result = await profile_agent.run(resume_text="张三简历")

        # 3. 差距分析（用前两步的输出作为输入）
        gap_llm = MockLLM(SAMPLE_GAP_RESPONSE)
        gap_agent = GapAnalyzerAgent(gap_llm)
        gap_result = await gap_agent.run(
            jd_analysis=jd_result,
            profile=profile_result,
        )

        assert gap_result["overall_score"] == 75.0
        assert len(gap_result["gaps"]) > 0
        # 验证 gap_llm 收到了正确的上下文
        content = " ".join(m.content for m in gap_llm.last_messages)
        assert "Python 后端工程师" in content
        assert "张三" in content


# === Tool-calling 循环测试 ===

class ToolCallingLLM:
    """可编程 Mock LLM：前 N 次调用返回 tool_calls，之后返回最终内容。"""

    def __init__(self, final_response: str, tool_rounds: int = 1, tool_name: str = "fake_tool"):
        self._final = final_response
        self._tool_rounds = tool_rounds
        self._tool_name = tool_name
        self.call_count = 0
        self.last_tools = None
        self.received_tool_results: list[str] = []

    async def chat(self, messages: list[Message], **kwargs) -> Response:
        self.call_count += 1
        self.last_tools = kwargs.get("tools")
        # 记录收到的工具结果，供断言
        for m in messages:
            if m.role == Role.TOOL:
                self.received_tool_results.append(m.content)
        if self.call_count <= self._tool_rounds:
            return Response(
                content="",
                tool_calls=[ToolCall(id="call_1", name=self._tool_name, arguments='{"q": "x"}')],
            )
        return Response(content=self._final)


class FakeTool(Tool):
    """测试用工具：记录调用参数并返回固定结果。"""

    name = "fake_tool"
    description = "测试工具"
    parameters = {
        "type": "object",
        "properties": {"q": {"type": "string"}},
        "required": ["q"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        self.called_with = kwargs
        return ToolResult.ok({"answer": "工具返回的数据"})


class TestToolCallingLoop:
    """测试 BaseAgent 的工具调用循环。"""

    @pytest.mark.asyncio
    async def test_run_calls_llm_with_tools(self):
        """注册了工具的 Agent 调用 LLM 时携带 tools 定义。"""
        llm = ToolCallingLLM(final_response='{"ok": true}')
        agent = SimpleEchoAgent(llm, tools=[FakeTool()])
        await agent.run()
        assert llm.last_tools is not None
        assert llm.last_tools[0].name == "fake_tool"

    @pytest.mark.asyncio
    async def test_tool_result_fed_back_to_llm(self):
        """工具调用后，工具结果以 TOOL 角色消息回填，且最终内容被解析。"""
        llm = ToolCallingLLM(final_response='{"ok": true}')
        agent = SimpleEchoAgent(llm, tools=[FakeTool()])
        result = await agent.run()

        assert result == {"ok": True}
        assert llm.call_count == 2  # 1 次带 tool_calls + 1 次最终内容
        assert llm.received_tool_results, "LLM 应收到工具执行结果"
        assert "工具返回的数据" in llm.received_tool_results[0]

    @pytest.mark.asyncio
    async def test_agent_without_tools_no_tool_loop(self):
        """未注册工具的 Agent 不传 tools，行为不变。"""
        llm = MockLLM(SAMPLE_JD_RESPONSE)
        agent = JDAnalyzerAgent(llm)
        result = await agent.run(jd_text="Python 工程师")
        assert result["job_title"] == "Python 后端工程师"
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_to_llm(self):
        """LLM 调用了未注册的工具 → 把错误返回给 LLM，不抛异常。"""
        llm = ToolCallingLLM(final_response='{"ok": true}', tool_name="no_such_tool")
        agent = SimpleEchoAgent(llm, tools=[FakeTool()])
        result = await agent.run()
        assert result == {"ok": True}
        assert any("未知工具" in r for r in llm.received_tool_results)


class SimpleEchoAgent(BaseAgent):
    """最小测试 Agent：把 LLM 返回的 JSON 原样解析。"""

    name = "simple_echo"

    def build_messages(self, **kwargs) -> list[Message]:
        return [Message(role=Role.USER, content="测试")]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        return result if result is not None else {"_raw": content}


# === 对话历史注入测试 ===

class _ChatAgent(BaseAgent):
    """带 system 消息的测试 Agent。"""

    name = "chat"

    def build_messages(self, **kwargs) -> list[Message]:
        return [
            Message(role=Role.SYSTEM, content="系统提示"),
            Message(role=Role.USER, content="当前问题"),
        ]

    def parse_response(self, content: str) -> dict:
        result = self.extract_json(content)
        return result if result is not None else {"_raw": content}


class TestConversationHistory:
    """测试 BaseAgent 的对话历史注入。"""

    @pytest.mark.asyncio
    async def test_history_injected_between_system_and_user(self):
        """历史消息应插在 system 与当前 user 之间，且保持顺序。"""
        llm = MockLLM('{"ok": true}')
        agent = _ChatAgent(llm)
        history = [
            {"role": "user", "content": "第一轮用户"},
            {"role": "assistant", "content": "第一轮助手"},
        ]
        await agent.run(conversation_history=history)

        roles = [(m.role.value, m.content) for m in llm.last_messages]
        assert roles[0] == ("system", "系统提示")
        assert roles[1] == ("user", "第一轮用户")
        assert roles[2] == ("assistant", "第一轮助手")
        assert roles[3] == ("user", "当前问题")

    @pytest.mark.asyncio
    async def test_history_truncated_to_last_8(self):
        """超过 8 条只保留最近 8 条。"""
        llm = MockLLM('{"ok": true}')
        agent = _ChatAgent(llm)
        history = [{"role": "user", "content": f"消息{i}"} for i in range(20)]
        await agent.run(conversation_history=history)

        injected = [m for m in llm.last_messages if m.role == Role.USER and m.content.startswith("消息")]
        assert len(injected) == 8
        assert injected[0].content == "消息12"

    @pytest.mark.asyncio
    async def test_no_history_no_change(self):
        """不传历史时消息结构不变。"""
        llm = MockLLM('{"ok": true}')
        agent = _ChatAgent(llm)
        await agent.run()

        roles = [m.role.value for m in llm.last_messages]
        assert roles == ["system", "user"]


# === Interview Reviewer Agent 测试 ===

SAMPLE_INTERVIEW_REVIEW = json.dumps({
    "score": 80,
    "dimensions": {
        "jd_coverage": {"score": 82, "comment": "覆盖良好"},
        "category_balance": {"score": 75, "comment": "一般"},
        "difficulty_distribution": {"score": 80, "comment": "合理"},
        "answer_quality": {"score": 78, "comment": "良好"},
        "relevance": {"score": 85, "comment": "贴合"},
    },
    "issues": [],
    "suggestions": [{"priority": "medium", "suggestion": "补充系统设计题", "section": "技术题"}],
    "summary": "质量良好",
}, ensure_ascii=False)


class TestInterviewReviewer:
    @pytest.mark.asyncio
    async def test_parse_valid(self):
        llm = MockLLM(SAMPLE_INTERVIEW_REVIEW)
        agent = InterviewReviewerAgent(llm)
        result = await agent.run(interview_questions={}, jd_analysis={}, profile={})
        assert result["score"] == 80
        assert len(result["dimensions"]) == 5
        assert len(result["suggestions"]) == 1

    @pytest.mark.asyncio
    async def test_parse_invalid(self):
        llm = MockLLM("这不是 JSON")
        agent = InterviewReviewerAgent(llm)
        result = await agent.run(interview_questions={}, jd_analysis={}, profile={})
        assert result.get("_parse_error") is True
        assert result["score"] == 0
        assert result["dimensions"] == {}
