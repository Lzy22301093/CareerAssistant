"""面试记录 schema（v3 M3）— 解析输出与复习计划的 Pydantic 模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InterviewParseOutput(BaseModel):
    """从用户回复中提取的面试信息（字段缺失即未提供）。"""

    company: str | None = None
    job_title: str | None = None
    result: Literal["passed", "failed", "pending"] | None = None
    questions: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    feedback: str | None = None


class ReviewPlanItem(BaseModel):
    topic: str
    reason: str
    suggestion: str


class ReviewPlanOutput(BaseModel):
    items: list[ReviewPlanItem] = Field(default_factory=list)
