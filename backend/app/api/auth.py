"""Auth API — 注册、登录、用户信息。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr

from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter()

auth_service = AuthService()


# === 请求/响应模型 ===


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


# === 认证依赖 ===


def get_current_user(authorization: str = Header(None)) -> dict[str, Any] | None:
    """从 Authorization header 提取当前用户。

    格式：Bearer <token>
    返回用户信息字典，未认证返回 None。
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    payload = auth_service.decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return auth_service.get_user_by_id(int(user_id))


def require_auth(authorization: str = Header(None)) -> dict[str, Any]:
    """要求认证的依赖，未认证抛出 401。"""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未认证，请先登录")
    return user


# === API 端点 ===


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """注册新用户。"""
    if len(request.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少 3 个字符")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 个字符")

    user = auth_service.register(request.username, request.email, request.password)
    if not user:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    token = auth_service.create_access_token({"sub": str(user["id"]), "username": user["username"]})
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """用户登录。"""
    result = auth_service.login(request.username, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return TokenResponse(access_token=result["token"], user=result["user"])


@router.get("/me")
async def get_me(user: dict = Depends(require_auth)):
    """获取当前用户信息。"""
    return user
