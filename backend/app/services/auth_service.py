"""Auth Service — JWT 认证 + 密码哈希。"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import jwt
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.models.database import SessionLocal
from app.models.orm import User

logger = logging.getLogger(__name__)

# JWT 配置
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_expire_minutes


def _require_secret() -> str:
    """返回 JWT 密钥；未配置时抛出明确错误（避免用空密钥静默签发 token）。"""
    if not SECRET_KEY:
        raise RuntimeError(
            "JWT_SECRET_KEY 未配置：请在 .env 或环境变量中设置 JWT_SECRET_KEY。"
        )
    return SECRET_KEY


class AuthService:
    """认证服务。"""

    def __init__(self, db_factory=None) -> None:
        self._db_factory = db_factory or SessionLocal

    def _get_db(self) -> DBSession:
        return self._db_factory()

    # === 密码（PBKDF2-SHA256） ===

    @staticmethod
    def hash_password(password: str) -> str:
        """哈希密码（PBKDF2-SHA256）。"""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return salt.hex() + ":" + key.hex()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码。"""
        try:
            salt_hex, key_hex = hashed_password.split(":")
            salt = bytes.fromhex(salt_hex)
            key = bytes.fromhex(key_hex)
            new_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt, 100000)
            return hmac.compare_digest(key, new_key)
        except Exception:
            return False

    # === JWT ===

    @staticmethod
    def create_access_token(data: dict[str, Any], expires_delta: timedelta = None) -> str:
        """创建 JWT access token。"""
        from datetime import timezone
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, _require_secret(), algorithm=ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict[str, Any] | None:
        """解码 JWT token，失败返回 None。"""
        try:
            payload = jwt.decode(token, _require_secret(), algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    # === 用户操作 ===

    def register(self, username: str, email: str, password: str) -> dict[str, Any] | None:
        """注册新用户，成功返回用户信息，失败返回 None。"""
        db = self._get_db()
        try:
            # 检查用户名是否已存在
            if db.query(User).filter(User.username == username).first():
                return None
            # 检查邮箱是否已存在
            if db.query(User).filter(User.email == email).first():
                return None

            user = User(
                username=username,
                email=email,
                hashed_password=self.hash_password(password),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"User registered: {username}")
            return self._user_to_dict(user)
        except Exception as e:
            db.rollback()
            logger.error(f"Registration failed: {e}")
            raise
        finally:
            db.close()

    def login(self, username: str, password: str) -> dict[str, Any] | None:
        """登录，成功返回 {user, token}，失败返回 None。"""
        db = self._get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user or not self.verify_password(password, user.hashed_password):
                return None
            if not user.is_active:
                return None

            token = self.create_access_token({"sub": str(user.id), "username": user.username})
            logger.info(f"User logged in: {username}")
            return {"user": self._user_to_dict(user), "token": token}
        finally:
            db.close()

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """通过 ID 获取用户。"""
        db = self._get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            return self._user_to_dict(user)
        finally:
            db.close()

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """通过用户名获取用户。"""
        db = self._get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return None
            return self._user_to_dict(user)
        finally:
            db.close()

    @staticmethod
    def _user_to_dict(user: User) -> dict[str, Any]:
        """将 User ORM 对象转换为字典。"""
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
