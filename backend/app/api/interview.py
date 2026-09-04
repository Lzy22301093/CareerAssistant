"""面试 REST API — 创建面试、提交回答、获取报告。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user, require_auth

router = APIRouter()
logger = logging.getLogger(__name__)

# 全局 handler 实例（在 main.py startup 中初始化）
_handler = None


def set_handler(handler):
    """设置全局 InterviewHandler 实例。"""
    global _handler
    _handler = handler


def _get_handler():
    if _handler is None:
        raise HTTPException(status_code=503, detail="Interview service not initialized")
    return _handler


# === Request/Response Models ===

class InterviewStartRequest(BaseModel):
    jd_analysis: dict[str, Any] = Field(..., description="JD 分析结果")
    profile: dict[str, Any] = Field(..., description="候选人画像")
    referenced_questions: list[str] = Field(default_factory=list, description="已参考的面试题")
    max_turns: int = Field(default=10, ge=3, le=30)


class InterviewStartResponse(BaseModel):
    interview_id: str
    question: str


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, description="候选人回答")


class InterviewAnswerResponse(BaseModel):
    question: str | None = None
    is_complete: bool = False
    report: dict[str, Any] | None = None


class InterviewStateResponse(BaseModel):
    interview_id: str
    is_active: bool
    is_complete: bool
    turn_count: int
    phase: str
    current_question: str
    dimension_scores: dict[str, float]
    difficulty_level: str


# === Endpoints ===

@router.post("/start", response_model=InterviewStartResponse)
async def start_interview(
    req: InterviewStartRequest,
    user: dict = Depends(require_auth),
):
    """创建新的模拟面试。"""
    handler = _get_handler()
    try:
        result = await handler.start_interview(
            jd_analysis=req.jd_analysis,
            profile=req.profile,
            referenced_questions=req.referenced_questions,
            max_turns=req.max_turns,
            user_id=user.get("id"),  # require_auth 返回的 user 字典以 "id" 标识
        )
        return InterviewStartResponse(
            interview_id=result["interview_id"],
            question=result["question"],
        )
    except Exception as e:
        logger.error(f"start_interview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{interview_id}/answer", response_model=InterviewAnswerResponse)
async def submit_answer(
    interview_id: str,
    req: InterviewAnswerRequest,
    user: dict = Depends(require_auth),
):
    """提交候选人回答，获取下一个问题或报告。"""
    handler = _get_handler()
    try:
        result = await handler.process_answer(
            interview_id=interview_id,
            answer=req.answer,
        )
        return InterviewAnswerResponse(
            question=result.get("question"),
            is_complete=result.get("is_complete", False),
            report=result.get("report"),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"submit_answer failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{interview_id}", response_model=InterviewStateResponse)
async def get_interview_state(
    interview_id: str,
    user: dict = Depends(require_auth),
):
    """获取面试当前状态。"""
    handler = _get_handler()
    state = await handler.get_state(interview_id)
    if not state:
        raise HTTPException(status_code=404, detail="Interview not found")
    return InterviewStateResponse(
        interview_id=interview_id,
        is_active=state.get("is_active", False),
        is_complete=state.get("is_complete", False),
        turn_count=state.get("turn_count", 0),
        phase=state.get("phase", ""),
        current_question=state.get("current_question", ""),
        dimension_scores=state.get("dimension_scores", {}),
        difficulty_level=state.get("difficulty_level", "medium"),
    )


@router.get("/{interview_id}/report")
async def get_interview_report(
    interview_id: str,
    user: dict = Depends(require_auth),
):
    """获取面试报告。"""
    handler = _get_handler()
    state = await handler.get_state(interview_id)
    if not state:
        raise HTTPException(status_code=404, detail="Interview not found")
    if not state.get("is_complete"):
        raise HTTPException(status_code=400, detail="Interview not yet completed")
    return state.get("final_report", {})
