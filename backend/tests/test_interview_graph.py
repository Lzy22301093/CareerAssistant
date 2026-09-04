"""Interview Graph 测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.evaluator import EvaluatorAgent
from app.agents.interviewer import InterviewerAgent
from app.interview.graph import build_continue_graph, build_interview_graph
from app.interview.nodes import (
    evaluate_node,
    finish_node,
    open_interview_node,
    ask_question_node,
)
from app.interview.state import InterviewState


# === Fixtures ===

@pytest.fixture
def mock_evaluator():
    agent = AsyncMock(spec=EvaluatorAgent)
    agent.name = "evaluator"
    agent.run = AsyncMock(return_value={
        "score": 7.5,
        "dimension_scores": {"专业知识": 8.0, "问题分析": 7.0},
        "strengths": ["回答清晰"],
        "weaknesses": ["缺少案例"],
        "feedback": "整体不错",
        "next_action": "切换话题",
        "reason": "当前话题已充分考察",
        "follow_up_question": None,
        "next_topic": "性能优化",
        "next_question": "如何优化 React 组件性能？",
        "new_difficulty": None,
    })
    return agent


@pytest.fixture
def mock_interviewer():
    agent = AsyncMock(spec=InterviewerAgent)
    agent.name = "interviewer"
    agent.run = AsyncMock(return_value={
        "question": "请介绍一下你最近做的一个项目。",
        "category": "behavioral",
    })
    return agent


@pytest.fixture
def agents(mock_evaluator, mock_interviewer):
    return {
        "evaluator": mock_evaluator,
        "interviewer": mock_interviewer,
    }


@pytest.fixture
def sample_jd():
    return {
        "job_title": "前端工程师",
        "company": "测试公司",
        "requirements": [
            {"content": "React", "importance": "high"},
            {"content": "TypeScript", "importance": "high"},
            {"content": "性能优化", "importance": "medium"},
        ],
    }


@pytest.fixture
def sample_profile():
    return {
        "name": "测试候选人",
        "skills": ["React", "Vue", "TypeScript"],
    }


# === 节点测试 ===

@pytest.mark.asyncio
async def test_open_interview(agents, sample_jd, sample_profile):
    state: InterviewState = {
        "jd_analysis": sample_jd,
        "profile": sample_profile,
        "target_position": "前端工程师",
        "referenced_questions": [],
        "difficulty_level": "medium",
        "max_turns": 10,
    }

    result = await open_interview_node(state, agents)

    assert result["phase"] == "opening"
    assert result["is_active"] is True
    assert result["turn_count"] == 0
    assert "前端工程师" in result.get("current_question", "") or len(result.get("current_question", "")) > 0
    assert len(result["conversation_history"]) == 1
    assert result["conversation_history"][0]["role"] == "assistant"
    agents["interviewer"].run.assert_called_once()


@pytest.mark.asyncio
async def test_evaluate(agents, sample_jd):
    state: InterviewState = {
        "current_question": "请介绍一下 React hooks。",
        "current_answer": "React hooks 是 React 16.8 引入的新特性...",
        "difficulty_level": "medium",
        "turn_count": 0,
        "max_turns": 10,
        "covered_topics": [],
        "pending_topics": ["React", "TypeScript"],
        "dimension_scores": {},
        "conversation_history": [],
        "referenced_questions": [],
    }

    result = await evaluate_node(state, agents)

    assert "current_evaluation" in result
    assert result["turn_count"] == 1
    assert "dimension_scores" in result
    assert "next_action" in result
    agents["evaluator"].run.assert_called_once()


@pytest.mark.asyncio
async def test_ask_question(agents):
    state: InterviewState = {
        "current_evaluation": {
            "next_action": "切换话题",
            "reason": "话题已充分考察",
            "next_topic": "性能优化",
        },
        "target_position": "前端工程师",
        "difficulty_level": "medium",
        "pending_topics": ["React", "TypeScript"],
        "covered_topics": [],
        "referenced_questions": [],
        "current_question": "",
        "current_answer": "",
    }

    result = await ask_question_node(state, agents)

    assert "current_question" in result
    assert result["phase"] == "core_probing"
    agents["interviewer"].run.assert_called_once()


@pytest.mark.asyncio
async def test_finish():
    state: InterviewState = {
        "turn_count": 10,
        "max_turns": 10,
        "pending_topics": [],
    }

    result = await finish_node(state, {})

    assert result["is_active"] is False
    assert result["is_complete"] is True
    assert result["completion_reason"] == "max_turns"


# === Graph 测试 ===

@pytest.mark.asyncio
async def test_start_graph(agents, sample_jd, sample_profile):
    graph = build_interview_graph(agents).compile()

    state: InterviewState = {
        "session_id": "test-123",
        "interview_id": "test-123",
        "jd_analysis": sample_jd,
        "profile": sample_profile,
        "target_position": "前端工程师",
        "referenced_questions": [],
        "difficulty_level": "medium",
        "interview_mode": "mixed",
        "max_turns": 10,
    }

    result = await graph.ainvoke(state)

    assert result["is_active"] is True
    # open_interview 设置 phase=opening, ask_question 覆盖为 core_probing
    assert result["phase"] == "core_probing"
    assert len(result["current_question"]) > 0
    assert result["turn_count"] == 0
    # open_interview 和 ask_question 都会调用 interviewer
    assert agents["interviewer"].run.call_count == 2


@pytest.mark.asyncio
async def test_continue_graph(agents, sample_jd):
    graph = build_continue_graph(agents).compile()

    state: InterviewState = {
        "current_question": "请介绍一下 React hooks。",
        "current_answer": "React hooks 是...",
        "difficulty_level": "medium",
        "turn_count": 1,
        "max_turns": 10,
        "covered_topics": [],
        "pending_topics": ["React", "TypeScript"],
        "dimension_scores": {},
        "conversation_history": [],
        "referenced_questions": [],
    }

    result = await graph.ainvoke(state)

    # evaluate 决定切换话题 → ask_question
    assert result["turn_count"] == 2
    assert "current_question" in result
    agents["evaluator"].run.assert_called_once()
    agents["interviewer"].run.assert_called_once()


@pytest.mark.asyncio
async def test_continue_graph_finish(agents, sample_jd):
    """测试达到最大轮数时结束面试。"""
    # mock evaluator 返回结束面试
    agents["evaluator"].run.return_value = {
        "score": 8.0,
        "dimension_scores": {"专业知识": 8.0},
        "strengths": ["优秀"],
        "weaknesses": [],
        "feedback": "很好",
        "next_action": "结束面试",
        "reason": "已充分考察",
        "follow_up_question": None,
        "next_topic": None,
        "next_question": None,
        "new_difficulty": None,
    }

    # mock llm.generate for report
    agents["evaluator"].llm = AsyncMock()
    agents["evaluator"].llm.generate = AsyncMock(return_value='{"overall_score": 8.0, "summary": "表现优秀", "suggestions": ["继续保持"]}')
    agents["evaluator"].extract_json = staticmethod(lambda text: {
        "overall_score": 8.0,
        "summary": "表现优秀",
        "suggestions": ["继续保持"],
    })

    graph = build_continue_graph(agents).compile()

    state: InterviewState = {
        "current_question": "最后一个问题",
        "current_answer": "回答...",
        "difficulty_level": "medium",
        "turn_count": 9,
        "max_turns": 10,
        "covered_topics": ["React", "TypeScript"],
        "pending_topics": [],
        "dimension_scores": {"专业知识": 7.5},
        "conversation_history": [],
        "referenced_questions": [],
        "strengths": [],
        "weaknesses": [],
        "target_position": "前端工程师",
    }

    result = await graph.ainvoke(state)

    assert result["is_complete"] is True
    assert "final_report" in result
