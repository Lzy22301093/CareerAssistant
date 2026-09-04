"""VoiceInterviewHandler 打断机制测试。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.voice.interview_handler import VoiceInterviewHandler


def _make_handler():
    """构造 mock InterviewHandler。"""
    handler = MagicMock()
    handler.agents = {
        "evaluator": MagicMock(),
        "interviewer": MagicMock(),
    }
    handler.session_service = AsyncMock()
    handler.on_complete = AsyncMock()
    return handler


def _make_state(**overrides):
    """构造默认面试状态。"""
    state = {
        "interview_id": "test-id",
        "session_id": "test-id",
        "target_position": "后端工程师",
        "difficulty_level": "medium",
        "interview_mode": "mixed",
        "phase": "core_probing",
        "current_question": "请介绍一下你最近的项目",
        "current_answer": "",
        "turn_count": 1,
        "max_turns": 10,
        "conversation_history": [],
        "dimension_scores": {},
        "current_evaluation": {},
        "strengths": [],
        "weaknesses": [],
        "next_action": "",
        "covered_topics": [],
        "pending_topics": ["微服务", "数据库"],
        "is_active": True,
        "is_complete": False,
        "completion_reason": "",
        "final_report": {},
        "referenced_questions": [],
        "jd_analysis": {"job_title": "后端工程师"},
        "profile": {},
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_normal_pipeline():
    """正常流程：evaluate → decide → ask_question。"""
    handler = _make_handler()
    state = _make_state()

    # mock session_service.load
    handler.session_service.load.return_value = state

    # mock evaluate_node, ask_question_node
    with patch("app.voice.interview_handler.evaluate_node", new_callable=AsyncMock) as mock_eval, \
         patch("app.voice.interview_handler.decide_next", return_value="追问"), \
         patch("app.voice.interview_handler.ask_question_node", new_callable=AsyncMock) as mock_ask:

        mock_eval.return_value = {
            "current_evaluation": {"score": 8, "dimension_scores": {"专业知识": 8}},
            "turn_count": 2,
            "strengths": ["回答清晰"],
            "weaknesses": [],
        }
        mock_ask.return_value = {
            "current_question": "能详细说说吗？",
            "phase": "core_probing",
        }

        voice_handler = VoiceInterviewHandler(handler)
        interrupt = asyncio.Event()
        result = await voice_handler.process_answer_interruptible("test-id", "我的项目用了微服务", interrupt)

    assert result is not None
    assert result["question"] == "能详细说说吗？"
    assert result["is_complete"] is False
    handler.session_service.save.assert_called_once()


@pytest.mark.asyncio
async def test_interrupt_before_evaluate():
    """打断发生在 evaluate 之前。"""
    handler = _make_handler()
    state = _make_state()
    handler.session_service.load.return_value = state

    voice_handler = VoiceInterviewHandler(handler)
    interrupt = asyncio.Event()
    interrupt.set()  # 预设打断

    result = await voice_handler.process_answer_interruptible("test-id", "回答", interrupt)

    assert result is None
    # 验证保存了 checkpoint
    save_call = handler.session_service.save.call_args
    saved_state = save_call[0][1]
    assert saved_state["interrupt_checkpoint"] == "pending_evaluate"


@pytest.mark.asyncio
async def test_interrupt_during_evaluate():
    """打断发生在 evaluate 进行中（CancelledError）。"""
    handler = _make_handler()
    state = _make_state()
    handler.session_service.load.return_value = state

    with patch("app.voice.interview_handler.evaluate_node", new_callable=AsyncMock) as mock_eval:
        # 模拟 evaluate 被取消
        mock_eval.side_effect = asyncio.CancelledError()

        voice_handler = VoiceInterviewHandler(handler)
        interrupt = asyncio.Event()
        result = await voice_handler.process_answer_interruptible("test-id", "回答", interrupt)

    assert result is None
    save_call = handler.session_service.save.call_args
    saved_state = save_call[0][1]
    assert saved_state["interrupt_checkpoint"] == "pending_evaluate"


@pytest.mark.asyncio
async def test_resume_from_pending_ask_question():
    """从 pending_ask_question checkpoint 恢复。"""
    handler = _make_handler()
    state = _make_state(interrupt_checkpoint="pending_ask_question")
    handler.session_service.load.return_value = state

    with patch("app.voice.interview_handler.ask_question_node", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = {
            "current_question": "下一个问题",
            "phase": "core_probing",
        }

        voice_handler = VoiceInterviewHandler(handler)
        interrupt = asyncio.Event()
        result = await voice_handler.process_answer_interruptible("test-id", "回答", interrupt)

    assert result is not None
    assert result["question"] == "下一个问题"
    # checkpoint 应该被清除
    save_call = handler.session_service.save.call_args
    saved_state = save_call[0][1]
    assert "interrupt_checkpoint" not in saved_state


@pytest.mark.asyncio
async def test_resume_from_pending_evaluate():
    """从 pending_evaluate checkpoint 恢复 → 重新走完整流水线。"""
    handler = _make_handler()
    state = _make_state(interrupt_checkpoint="pending_evaluate")
    handler.session_service.load.return_value = state

    with patch("app.voice.interview_handler.evaluate_node", new_callable=AsyncMock) as mock_eval, \
         patch("app.voice.interview_handler.decide_next", return_value="追问"), \
         patch("app.voice.interview_handler.ask_question_node", new_callable=AsyncMock) as mock_ask:

        mock_eval.return_value = {
            "current_evaluation": {"score": 7, "dimension_scores": {}},
            "turn_count": 2,
        }
        mock_ask.return_value = {"current_question": "恢复后的问题"}

        voice_handler = VoiceInterviewHandler(handler)
        interrupt = asyncio.Event()
        result = await voice_handler.process_answer_interruptible("test-id", "回答", interrupt)

    assert result is not None
    assert result["question"] == "恢复后的问题"


@pytest.mark.asyncio
async def test_already_complete():
    """面试已完成，直接返回报告。"""
    handler = _make_handler()
    state = _make_state(is_complete=True, final_report={"overall_score": 8})
    handler.session_service.load.return_value = state

    voice_handler = VoiceInterviewHandler(handler)
    interrupt = asyncio.Event()
    result = await voice_handler.process_answer_interruptible("test-id", "回答", interrupt)

    assert result is not None
    assert result["is_complete"] is True
    assert result["report"]["overall_score"] == 8


@pytest.mark.asyncio
async def test_finish_action():
    """evaluate 决策结束面试 → finish → report。"""
    handler = _make_handler()
    state = _make_state()
    handler.session_service.load.return_value = state

    with patch("app.voice.interview_handler.evaluate_node", new_callable=AsyncMock) as mock_eval, \
         patch("app.voice.interview_handler.decide_next", return_value="结束面试"), \
         patch("app.voice.interview_handler.finish_node", new_callable=AsyncMock) as mock_finish, \
         patch("app.voice.interview_handler.generate_report_node", new_callable=AsyncMock) as mock_report:

        mock_eval.return_value = {
            "current_evaluation": {"score": 9},
            "turn_count": 10,
        }
        mock_finish.return_value = {
            "is_complete": True,
            "completion_reason": "max_turns",
        }
        mock_report.return_value = {
            "final_report": {"overall_score": 8.5, "summary": "表现不错"},
        }

        voice_handler = VoiceInterviewHandler(handler)
        interrupt = asyncio.Event()
        result = await voice_handler.process_answer_interruptible("test-id", "回答", interrupt)

    assert result is not None
    assert result["is_complete"] is True
    assert result["report"]["overall_score"] == 8.5
    handler.on_complete.assert_called_once()


@pytest.mark.asyncio
async def test_not_found():
    """面试不存在时抛出异常。"""
    handler = _make_handler()
    handler.session_service.load.return_value = None

    voice_handler = VoiceInterviewHandler(handler)
    interrupt = asyncio.Event()

    with pytest.raises(ValueError, match="not found"):
        await voice_handler.process_answer_interruptible("bad-id", "回答", interrupt)
