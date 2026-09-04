"""SectionRewrite 输出 schema（阶段2 指令2-2 区域改写）。

LLM 输出经 SectionRewriteOutput.model_validate 校验后才能进入落库/前端流程。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RewriteCandidate(BaseModel):
    """单条改写候选。"""

    rewrite: str = Field(..., min_length=1, description="改写后的区域全文")
    approach: str = Field(..., description="改写思路（一句话，给用户看）")
    changes: list[str] = Field(default_factory=list, description="关键改动点")


class SectionRewriteOutput(BaseModel):
    """区域改写输出（多候选）。"""

    candidates: list[RewriteCandidate] = Field(..., min_length=1, max_length=5)
    needs_source_confirmation: bool = Field(default=False, description="LLM 自报：候选是否引入了画像外内容")
    new_numbers: list[str] = Field(default_factory=list, description="引入的画像/原文中不存在的数字")
    new_claims: list[str] = Field(default_factory=list, description="引入的画像/原文中不存在的经历或事实")
    advice: str | None = Field(default=None, description="给用户的一句话建议")
