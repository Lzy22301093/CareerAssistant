"""Preferences API — 用户偏好管理。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import require_auth
from app.services.preference_service import PreferenceService

logger = logging.getLogger(__name__)
router = APIRouter()

pref_service = PreferenceService()


# === 请求模型 ===


class PreferenceUpdateRequest(BaseModel):
    preferred_template: str | None = None
    resume_style: str | None = None
    job_preferences: dict[str, Any] | None = None
    extra: dict[str, Any] | None = None


# === API 端点 ===


@router.get("/")
async def get_preferences(user: dict = Depends(require_auth)):
    """获取当前用户偏好。"""
    return pref_service.get_preferences(user["id"])


@router.put("/")
async def update_preferences(
    request: PreferenceUpdateRequest,
    user: dict = Depends(require_auth),
):
    """更新当前用户偏好。"""
    data = request.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    return pref_service.update_preferences(user["id"], data)


@router.get("/template")
async def get_template(user: dict = Depends(require_auth)):
    """获取用户偏好的简历模板。"""
    return {"template": pref_service.get_template_preference(user["id"])}
