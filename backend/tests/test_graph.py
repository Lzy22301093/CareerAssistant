"""Graph 层测试 — 测试 LangGraph 工作流编排。"""

import json

import pytest

from app.agents import create_agents
from app.graph.edges import (
    route_after_planner,
    route_after_reviewer,
    route_after_interview_review,
    rule_based_route,
)
from app.graph.reflection import MAX_ITERATIONS
from app.graph.nodes import (
    _build_session_state,
    clarifier_node,
    content_generator_node,
    cover_letter_node,
    gap_analyzer_node,
    html_renderer_node,
    interview_qa_node,
    interview_reviewer_node,
    jd_analyzer_node,
    parallel_analysis_node,
    parallel_post_node,
    planner_node,
    profile_extractor_node,
    question_node,
    reviewer_node,
)
from app.graph.reflection import PASS_SCORE
from app.graph.state import GraphState
from app.graph.workflow import build_graph
from app.llm import LLMProvider, Message, Response, Role


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

SAMPLE_REVIEW_PASS = json.dumps({
    "score": 82,
    "dimensions": {
        "keyword_coverage": {"score": 85, "comment": "良好"},
        "achievement_quantification": {"score": 75, "comment": "一般"},
        "relevance": {"score": 85, "comment": "良好"},
        "clarity": {"score": 80, "comment": "良好"},
        "completeness": {"score": 80, "comment": "良好"},
    },
    "issues": [],
    "suggestions": [],
    "summary": "质量合格",
}, ensure_ascii=False)

SAMPLE_REVIEW_FAIL = json.dumps({
    "score": 55,
    "dimensions": {
        "keyword_coverage": {"score": 50, "comment": "不足"},
        "achievement_quantification": {"score": 40, "comment": "缺少量化"},
        "relevance": {"score": 60, "comment": "一般"},
        "clarity": {"score": 60, "comment": "一般"},
        "completeness": {"score": 55, "comment": "不完整"},
    },
    "issues": [{"severity": "high", "description": "缺少量化数据", "section": "工作经历"}],
    "suggestions": [{"priority": "high", "suggestion": "添加百分比数据", "section": "工作经历"}],
    "summary": "需要改进",
}, ensure_ascii=False)

SAMPLE_CLARIFIER = json.dumps({
    "missing_items": ["jd"],
    "question": "请提供目标职位的 JD。",
    "suggestions": ["粘贴 JD 文本"],
    "context_type": "initial",
}, ensure_ascii=False)

SAMPLE_INTERVIEW_REVIEW_PASS = json.dumps({
    "score": 82,
    "dimensions": {
        "jd_coverage": {"score": 85, "comment": "覆盖良好"},
        "category_balance": {"score": 80, "comment": "均衡"},
        "difficulty_distribution": {"score": 80, "comment": "合理"},
        "answer_quality": {"score": 82, "comment": "良好"},
        "relevance": {"score": 85, "comment": "贴合"},
    },
    "issues": [],
    "suggestions": [],
    "summary": "面试题质量合格",
}, ensure_ascii=False)

SAMPLE_INTERVIEW_REVIEW_FAIL = json.dumps({
    "score": 55,
    "dimensions": {
        "jd_coverage": {"score": 50, "comment": "覆盖不足"},
        "category_balance": {"score": 50, "comment": "偏科"},
        "difficulty_distribution": {"score": 60, "comment": "一般"},
        "answer_quality": {"score": 55, "comment": "答案过简"},
        "relevance": {"score": 60, "comment": "一般"},
    },
    "issues": [{"severity": "high", "description": "缺少系统设计题", "section": "技术题"}],
    "suggestions": [{"priority": "high", "suggestion": "补充系统设计类题目", "section": "技术题"}],
    "summary": "需要改进",
}, ensure_ascii=False)


class SmartMockLLM(MockLLM):
    """能根据状态智能路由的 Mock LLM。"""

    async def chat(self, messages: list[Message], **kwargs) -> Response:
        self.call_count += 1
        content = " ".join(m.content for m in messages)

        # 检查是否是 Planner 的路由决策
        if "路由决策规则" in content:
            # 根据状态决定路由
            if '"has_gap_analysis": true' in content and '"has_resume_content": false' in content:
                return Response(content=json.dumps({"route": "content_generator", "reason": "可以生成简历内容"}))
            if '"has_resume_content": true' in content and '"has_render_config": false' in content:
                return Response(content=json.dumps({"route": "html_renderer", "reason": "可以渲染HTML"}))
            if '"has_render_config": true' in content and '"has_interview_questions": false' in content:
                return Response(content=json.dumps({"route": "interview_qa", "reason": "可以生成面试题"}))
            if '"has_jd": true' in content and '"has_profile": true' in content and '"has_gap_analysis": false' in content:
                return Response(content=json.dumps({"route": "gap_analyzer", "reason": "可以进行差距分析"}))
            if '"has_jd": true' in content and '"has_profile": false' in content:
                return Response(content=json.dumps({"route": "profile_extractor", "reason": "需要提取简历画像"}))
            if '"has_jd": false' in content:
                return Response(content=json.dumps({"route": "jd_analyzer", "reason": "用户提供了 JD"}))

        # 其他规则
        for pattern, resp in self._rules:
            if pattern in content:
                return Response(content=resp)
        return Response(content=self._default)


def _create_mock_llm() -> MockLLM:
    """创建预设好的 Mock LLM，匹配所有 Agent 的 prompt。"""
    llm = SmartMockLLM("{}")
    # 按优先级排列：先匹配更具体的关键词
    llm.when("提取关键词和短语", json.dumps({"keywords": ["Python", "FastAPI"]}, ensure_ascii=False))
    llm.when("分析以下职位描述", SAMPLE_JD)
    llm.when("请解析以下简历", SAMPLE_PROFILE)
    llm.when("分析两者的匹配度", SAMPLE_GAP)
    llm.when("生成针对性的简历内容", SAMPLE_CONTENT)
    llm.when("生成渲染配置", SAMPLE_RENDER)
    llm.when("生成面试题", SAMPLE_INTERVIEW)
    llm.when("评审简历内容", SAMPLE_REVIEW_PASS)
    llm.when("评审面试题", SAMPLE_INTERVIEW_REVIEW_PASS)
    llm.when("判断缺少什么信息", SAMPLE_CLARIFIER)
    return llm


# === State 辅助函数测试 ===

class TestBuildSessionState:
    def test_empty_state(self):
        state: GraphState = {}
        result = _build_session_state(state)
        assert result["has_jd"] is False
        assert result["has_profile"] is False
        assert result["content_iterations"] == 0

    def test_partial_state(self):
        state: GraphState = {"jd_analysis": {"job_title": "test"}, "content_iterations": 2}
        result = _build_session_state(state)
        assert result["has_jd"] is True
        assert result["has_profile"] is False
        assert result["content_iterations"] == 2


# === 条件边测试 ===

class TestEdges:
    def test_route_after_planner(self):
        """规则引擎：有待分析的 JD 文本 → 路由到 jd_analyzer。"""
        state: GraphState = {"jd_text": "Python 工程师，要求 3 年经验"}
        assert route_after_planner(state) == "jd_analyzer"

    def test_route_after_planner_clarify(self):
        state: GraphState = {"route": "clarify"}
        assert route_after_planner(state) == "clarifier"

    def test_route_after_planner_unknown(self):
        state: GraphState = {"route": "unknown"}
        assert route_after_planner(state) == "clarifier"

    def test_file_processing_precedes_intent(self):
        """回归：上传文件待处理时，意图误判不得短路输入处理。"""
        state: GraphState = {
            "intent": "ask_question",  # 意图被误判
            "user_message": "帮我看看",
            "resume_text": "张三，Python 工程师，5年经验",
            "profile_input_version": 1,
            "profile_analyzed_version": -1,  # 从未提取
            "jd_input_version": 0,
        }
        assert rule_based_route(state) == "profile_extractor"

        # JD 待处理同理
        state2: GraphState = {
            "intent": "ask_question",
            "user_message": "帮我看看",
            "jd_text": "Python 工程师，要求 3 年经验",
            "jd_input_version": 1,
            "jd_analyzed_version": -1,
            "profile_input_version": 0,
        }
        assert rule_based_route(state2) == "jd_analyzer"

    def test_clarification_does_not_block_new_jd(self):
        """回归：澄清未完成时，用户发 JD 应放行，而不是继续卡在澄清。"""
        state: GraphState = {
            "intent": "upload_jd",  # 意图正确识别为 JD
            "user_message": "职位描述：项目经理，要求5年经验，负责项目规划与团队管理",
            "jd_text": "",
            "resume_text": "",
            "clarification_history": [{"question": "请提供职位描述"}],  # 上一轮澄清未完成
            "ready_to_proceed": False,
            "jd_input_version": 0,
            "profile_input_version": 0,
        }
        assert rule_based_route(state) == "jd_analyzer"

    def test_clarification_still_blocks_non_input(self):
        """澄清中且新消息不是 JD/简历 → 仍继续澄清。"""
        state: GraphState = {
            "intent": "ask_question",
            "user_message": "好的知道了",
            "clarification_history": [{"question": "请提供职位描述"}],
            "ready_to_proceed": False,
        }
        assert rule_based_route(state) == "clarifier"

    def test_route_after_reviewer_pass(self):
        """高分通过。"""
        state: GraphState = {
            "review_result": {"score": PASS_SCORE + 5, "suggestions": [], "issues": []},
            "content_iterations": 1,
        }
        assert route_after_reviewer(state) == "proceed"

    def test_route_after_reviewer_iterate(self):
        """低分迭代。"""
        state: GraphState = {
            "review_result": {"score": 50, "suggestions": [{"priority": "high"}], "issues": []},
            "content_iterations": 1,
        }
        assert route_after_reviewer(state) == "iterate"

    def test_route_after_reviewer_max_iterations(self):
        """达到最大迭代强制通过。"""
        state: GraphState = {
            "review_result": {"score": 30, "suggestions": [], "issues": []},
            "content_iterations": MAX_ITERATIONS,
        }
        assert route_after_reviewer(state) == "proceed"

    def test_route_after_interview_review_pass(self):
        """面试题评审高分通过。"""
        state: GraphState = {
            "interview_review_result": {"score": PASS_SCORE + 5, "suggestions": [], "issues": []},
            "interview_iterations": 1,
        }
        assert route_after_interview_review(state) == "proceed"

    def test_route_after_interview_review_iterate(self):
        """面试题评审低分迭代。"""
        state: GraphState = {
            "interview_review_result": {
                "score": 50,
                "suggestions": [{"priority": "high"}],
                "issues": [],
            },
            "interview_iterations": 1,
        }
        assert route_after_interview_review(state) == "iterate"

    def test_route_after_interview_review_max_iterations(self):
        """面试题评审达到最大迭代强制通过。"""
        state: GraphState = {
            "interview_review_result": {"score": 30, "suggestions": [], "issues": []},
            "interview_iterations": MAX_ITERATIONS,
        }
        assert route_after_interview_review(state) == "proceed"


# === 节点函数测试 ===

class TestNodes:
    @pytest.mark.asyncio
    async def test_planner_node(self):
        llm = MockLLM(json.dumps({"route": "jd_analyzer", "reason": "用户提供了 JD"}))
        agents = create_agents(llm)
        state: GraphState = {"user_message": "分析这个 JD", "session_id": "test"}
        result = await planner_node(state, agents)
        assert result["route"] == "jd_analyzer"
        assert "route_reason" in result

    @pytest.mark.asyncio
    async def test_jd_analyzer_node(self):
        llm = MockLLM(SAMPLE_JD)
        agents = create_agents(llm)
        state: GraphState = {"user_message": "Python 后端工程师"}
        result = await jd_analyzer_node(state, agents)
        assert "jd_analysis" in result
        assert result["jd_analysis"]["job_title"] == "Python 工程师"

    @pytest.mark.asyncio
    async def test_profile_extractor_node(self):
        llm = MockLLM(SAMPLE_PROFILE)
        agents = create_agents(llm)
        state: GraphState = {"user_message": "张三简历"}
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
    async def test_content_generator_with_review_feedback(self):
        """迭代时应包含评审改进建议。"""
        llm = MockLLM(SAMPLE_CONTENT)
        agents = create_agents(llm)
        state: GraphState = {
            "profile": {"name": "张三"},
            "jd_analysis": {"job_title": "Python 工程师"},
            "review_result": {
                "score": 55,
                "suggestions": [{"priority": "high", "suggestion": "添加量化数据", "section": "工作经历"}],
                "issues": [{"severity": "high", "description": "缺少量化", "section": "工作经历"}],
            },
            "content_iterations": 1,
        }
        result = await content_generator_node(state, agents)
        assert result["content_iterations"] == 2

    @pytest.mark.asyncio
    async def test_reviewer_node(self):
        llm = MockLLM(SAMPLE_REVIEW_PASS)
        agents = create_agents(llm)
        state: GraphState = {
            "resume_content": {"sections": []},
            "jd_analysis": {"job_title": "Python 工程师"},
            "profile": {"name": "张三"},
        }
        result = await reviewer_node(state, agents)
        assert "review_result" in result
        assert result["review_result"]["score"] == 82

    @pytest.mark.asyncio
    async def test_reviewer_node_rule_precheck_skips_llm(self):
        """规则预检通过（板块完整+量化+关键词覆盖）时跳过 LLM 评审。"""
        llm = MockLLM(SAMPLE_REVIEW_FAIL)  # 若被误调用会返回低分
        agents = create_agents(llm)
        state: GraphState = {
            "resume_content": {"sections": [{"title": "工作经历", "content": "主导重构，响应时间降低 30%"}]},
            "jd_analysis": {"keywords": ["重构", "响应时间"]},
        }
        result = await reviewer_node(state, agents)
        assert result["review_result"].get("rule_passed") is True
        assert llm.call_count == 0  # 未调用 LLM

    @pytest.mark.asyncio
    async def test_reviewer_node_rule_precheck_not_passed(self):
        """无量化数字时规则预检不通过，走 LLM 评审。"""
        llm = MockLLM(SAMPLE_REVIEW_PASS)
        agents = create_agents(llm)
        state: GraphState = {
            "resume_content": {"sections": [{"title": "工作经历", "content": "负责系统开发"}]},
            "jd_analysis": {"keywords": ["重构"]},
        }
        result = await reviewer_node(state, agents)
        assert result["review_result"].get("rule_passed") is not True
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_parallel_post_node_parallel_review_and_interview(self):
        """parallel_post：评审与面试题并行产出；规则预检通过时只调 1 次 LLM。"""
        llm = MockLLM("{}")
        llm.when("生成面试题", SAMPLE_INTERVIEW)
        agents = create_agents(llm)
        state: GraphState = {
            "resume_content": {"sections": [{"title": "技能", "content": "Python 3 年经验"}]},
            "jd_analysis": {"job_title": "Python 工程师", "keywords": ["Python"]},
            "profile": {"name": "张三"},
            "gap_analysis": {"overall_score": 80},
        }
        result = await parallel_post_node(state, agents)
        assert result["review_result"].get("rule_passed") is True
        assert "interview_questions" in result
        assert llm.call_count == 1  # 只有面试题生成一次调用

    @pytest.mark.asyncio
    async def test_parallel_post_node_interview_not_repeated(self):
        """评审迭代时面试题不重复生成。"""
        llm = MockLLM("{}")
        llm.when("生成面试题", SAMPLE_INTERVIEW)
        llm.when("评审简历内容", SAMPLE_REVIEW_FAIL)
        agents = create_agents(llm)
        state: GraphState = {
            "resume_content": {"sections": [{"title": "技能", "content": "Python"}]},  # 无数字 → 走 LLM 评审
            "jd_analysis": {"job_title": "Python 工程师", "keywords": ["Python"]},
            "profile": {"name": "张三"},
            "gap_analysis": {"overall_score": 80},
            "interview_questions": {"questions": [{"question": "已有题目"}]},  # 已存在
        }
        result = await parallel_post_node(state, agents)
        # 面试题已存在 → 不重复生成，只做 LLM 评审
        assert llm.call_count == 1
        assert "interview_questions" not in result

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
        }
        result = await interview_qa_node(state, agents)
        assert "interview_questions" in result
        assert len(result["interview_questions"]["questions"]) == 1

    @pytest.mark.asyncio
    async def test_interview_qa_node_with_review_feedback(self):
        """迭代时应包含评审改进建议，并递增迭代次数。"""
        llm = MockLLM(SAMPLE_INTERVIEW)
        agents = create_agents(llm)
        state: GraphState = {
            "jd_analysis": {"job_title": "Python 工程师"},
            "profile": {"name": "张三"},
            "interview_review_result": {
                "score": 55,
                "suggestions": [{"priority": "high", "suggestion": "补充系统设计题", "section": "技术题"}],
                "issues": [{"severity": "high", "description": "缺少系统设计题", "section": "技术题"}],
            },
            "interview_iterations": 1,
        }
        result = await interview_qa_node(state, agents)
        assert result["interview_iterations"] == 2
        # 验证改进建议进入了 prompt
        content = " ".join(m.content for m in llm.last_messages)
        assert "补充系统设计题" in content

    @pytest.mark.asyncio
    async def test_interview_reviewer_node(self):
        llm = MockLLM(SAMPLE_INTERVIEW_REVIEW_PASS)
        agents = create_agents(llm)
        state: GraphState = {
            "interview_questions": {"questions": []},
            "jd_analysis": {"job_title": "Python 工程师"},
            "profile": {"name": "张三"},
        }
        result = await interview_reviewer_node(state, agents)
        assert "interview_review_result" in result
        assert result["interview_review_result"]["score"] == 82

    @pytest.mark.asyncio
    async def test_clarifier_node(self):
        llm = MockLLM(SAMPLE_CLARIFIER)
        agents = create_agents(llm)
        state: GraphState = {"route_reason": "需要更多信息", "user_message": "帮我优化简历"}
        result = await clarifier_node(state, agents)
        assert "clarification_question" in result
        assert "JD" in result["clarification_question"]

    @pytest.mark.asyncio
    async def test_clarifier_node_fallback(self):
        """LLM 返回无效 JSON 时的降级。"""
        llm = MockLLM("plain text")
        agents = create_agents(llm)
        state: GraphState = {}
        result = await clarifier_node(state, agents)
        assert "clarification_question" in result

    @pytest.mark.asyncio
    async def test_clarifier_channel_selection(self):
        """求职信渠道未选时，clarifier 直接给选项（不调 LLM）。"""
        llm = MockLLM("{}")
        agents = create_agents(llm)
        state: GraphState = {
            "intent": "generate_cover_letter",
            "cover_letter_channel": "",
            "user_message": "帮我写个求职信",
        }
        result = await clarifier_node(state, agents)
        assert "文案" in result["clarification_question"]
        assert llm.call_count == 0  # 未调用 LLM

    @pytest.mark.asyncio
    async def test_clarifier_interview_record_progress(self):
        """面试记录（M3）多轮追问：首轮追问，回复后解析并完成。"""
        llm = MockLLM(json.dumps({
            "company": "腾讯", "job_title": "后端工程师", "result": "failed",
        }))
        agents = create_agents(llm)

        # 首轮：无历史 → 追问第一个缺失字段
        state: GraphState = {"intent": "record_interview", "user_message": "我面试挂了"}
        r1 = await clarifier_node(state, agents)
        assert r1.get("clarification_question")
        assert r1["ready_to_proceed"] is False

        # 第二轮：有历史 + 用户回复 → LLM 解析 → 信息齐全
        state2: GraphState = {
            "intent": "record_interview",
            "user_message": "腾讯的后端工程师，挂了",
            "clarification_history": [{"question": "面试的是哪家公司？", "detected_intent": "interview_record"}],
        }
        r2 = await clarifier_node(state2, agents)
        assert r2["ready_to_proceed"] is True
        assert r2["interview_draft"]["company"] == "腾讯"
        assert r2["interview_draft"]["result"] == "failed"

    @pytest.mark.asyncio
    async def test_question_node(self):
        """自由问答节点：返回 answer。"""
        llm = MockLLM("你目前的画像中有 Python、FastAPI 技能，与岗位要求匹配度较高。")
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
            "body": "您好，我有 5 年 Python 开发经验，期待面试机会。",
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
        """测试完整流程：Planner → JD → Gap → Content → Review(pass) → HTML → Interview → END。"""
        llm = _create_mock_llm()
        graph = build_graph(llm)
        result = await graph.ainvoke({
            "user_message": "Python 后端工程师，要求 3 年经验",
            "session_id": "test-001",
            "jd_text": "Python 后端工程师，要求 3 年经验，熟悉 FastAPI",
            "resume_text": "张三，Python 工程师，3年经验",
        })
        # 验证各阶段输出（流程完成后，route 字段会被更新到最后执行的路由）
        assert result.get("jd_analysis", {}).get("job_title") == "Python 工程师"
        assert result.get("profile", {}).get("name") == "张三"
        assert result.get("gap_analysis", {}).get("overall_score") == 80.0
        assert result.get("resume_content", {}).get("sections") is not None
        assert result.get("review_result", {}).get("score") == 82
        assert result.get("render_config", {}).get("template") == "modern"
        assert result.get("interview_questions", {}).get("questions") is not None
        assert result.get("interview_review_result", {}).get("score") == 82

    @pytest.mark.asyncio
    async def test_review_triggers_iteration(self):
        """低分评审应触发迭代。"""
        # 创建一个会返回低分评审的 MockLLM
        llm = SmartMockLLM("{}")
        llm.when("提取关键词和短语", json.dumps({"keywords": ["Python", "FastAPI"]}, ensure_ascii=False))
        llm.when("分析以下职位描述", SAMPLE_JD)
        llm.when("请解析以下简历", SAMPLE_PROFILE)
        llm.when("分析两者的匹配度", SAMPLE_GAP)
        llm.when("生成针对性的简历内容", SAMPLE_CONTENT)
        llm.when("生成渲染配置", SAMPLE_RENDER)
        llm.when("生成面试题", SAMPLE_INTERVIEW)
        llm.when("评审简历内容", SAMPLE_REVIEW_FAIL)  # 低分评审
        llm.when("评审面试题", SAMPLE_INTERVIEW_REVIEW_FAIL)  # 面试题低分评审
        llm.when("判断缺少什么信息", SAMPLE_CLARIFIER)

        graph = build_graph(llm)
        result = await graph.ainvoke({
            "user_message": "Python 后端工程师",
            "session_id": "test-iter",
            "jd_text": "Python 后端工程师，要求 3 年经验",
            "resume_text": "张三，Python 工程师，3年经验",
        })
        # 简历和面试题都应有迭代
        assert result.get("content_iterations", 0) > 1
        assert result.get("interview_iterations", 0) > 1

    @pytest.mark.asyncio
    async def test_clarifier_route(self):
        """测试 Planner 路由到 Clarifier。"""
        llm = MockLLM(json.dumps({"route": "clarify", "reason": "需要上传简历"}))
        llm.when("判断缺少什么信息", SAMPLE_CLARIFIER)
        graph = build_graph(llm)
        result = await graph.ainvoke({
            "user_message": "帮我优化简历",
            "session_id": "test-002",
        })
        assert result.get("route") == "clarifier"
        assert result.get("clarification_question") is not None

    @pytest.mark.asyncio
    async def test_incremental_jd_change_reanalyzes(self):
        """增量编辑（v3）：换岗位 → JD/差距/内容/面试题全部级联重算。"""
        llm = _create_mock_llm()
        graph = build_graph(llm)

        # 第一轮：上传 JD A + 简历
        r1 = await graph.ainvoke({
            "user_message": "岗位描述：Python 工程师",
            "session_id": "test-incr-1",
            "jd_text": "Python 工程师，要求 3 年经验",
            "resume_text": "张三，Python 工程师，3年经验",
            "jd_input_version": 1,
            "profile_input_version": 1,
        })
        assert r1.get("jd_analyzed_version") == 1
        assert r1.get("gap_based_jd") == 1
        assert r1.get("content_based_jd") == 1
        assert r1.get("interview_based_jd") == 1

        # 第二轮：换 JD B（jd_input_version=2），其余状态保持（含版本字段，模拟会话持久化）
        r2 = await graph.ainvoke({
            "user_message": "岗位描述：项目经理",
            "session_id": "test-incr-2",
            "jd_text": "项目经理，要求 5 年管理经验",
            "resume_text": "",
            "jd_analysis": r1.get("jd_analysis", {}),
            "profile": r1.get("profile", {}),
            "gap_analysis": r1.get("gap_analysis", {}),
            "resume_content": r1.get("resume_content", {}),
            "render_config": r1.get("render_config", {}),
            "jd_input_version": 2,
            "profile_input_version": 1,
            "jd_analyzed_version": 1,
            "profile_analyzed_version": 1,
            "gap_based_jd": 1, "gap_based_profile": 1,
            "content_based_jd": 1, "content_based_profile": 1,
            "interview_based_jd": 1, "interview_based_profile": 1,
        })
        # JD 重算：基于新版本
        assert r2.get("jd_analyzed_version") == 2
        # 级联：gap/content/interview 全部基于新 JD 版本重算
        assert r2.get("gap_based_jd") == 2
        assert r2.get("content_based_jd") == 2
        assert r2.get("interview_based_jd") == 2

    @pytest.mark.asyncio
    async def test_incremental_no_change_skips(self):
        """增量编辑（v3）：输入未变化时不重跑分析。"""
        llm = _create_mock_llm()
        graph = build_graph(llm)

        # 全量数据就绪且版本一致
        r = await graph.ainvoke({
            "user_message": "帮我优化简历",
            "session_id": "test-skip",
            "jd_text": "",
            "resume_text": "",
            "jd_analysis": {"job_title": "Python 工程师", "keywords": ["Python"]},
            "profile": {"name": "张三", "skills": ["Python"]},
            "gap_analysis": {"overall_score": 80},
            "resume_content": {"sections": [{"title": "技能", "content": "Python"}]},
            "render_config": {"template": "modern"},
            "interview_questions": {"questions": []},
            "jd_input_version": 1,
            "profile_input_version": 1,
            "jd_analyzed_version": 1,
            "profile_analyzed_version": 1,
            "gap_based_jd": 1, "gap_based_profile": 1,
            "content_based_jd": 1, "content_based_profile": 1,
            "interview_based_jd": 1, "interview_based_profile": 1,
        })
        # 未触发任何重算（版本保持 1）
        assert r.get("jd_analyzed_version", 1) == 1
        assert r.get("gap_based_jd", 1) == 1
