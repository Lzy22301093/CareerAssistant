"""consolidate 输出 schema（v3）— 长期档案变更建议的 Pydantic 模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConsolidationUpdate(BaseModel):
    """一条档案变更建议。"""

    op: Literal["add", "update"]
    field: Literal["skills", "experience", "preferences", "gaps", "target_roles", "summary"]
    value: Any
    reason: str = ""


class ConsolidationOutput(BaseModel):
    """consolidate 提炼结果。"""

    updates: list[ConsolidationUpdate] = Field(default_factory=list)


# 可合并的字段白名单（与 _ALLOWED_FIELDS 对齐的子集）
CONSOLIDATION_FIELDS = {
    "skills", "experience", "preferences", "gaps", "target_roles", "summary",
}
