"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # App
    app_title: str = "CareerAssistant API"
    debug: bool = False

    # Database
    database_url: str = "mysql+pymysql://root:root@localhost:3306/career_assistant"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM (OpenAI-compatible: MIMO, DeepSeek, etc.)
    # 注意：API Key 不提供默认值，必须通过环境变量 / .env 注入，
    # 缺失时 create_llm_provider() 会抛出明确的 ValueError。
    openai_api_key: str = ""
    llm_base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"
    llm_model: str = "mimo-v2.5-pro"
    # 快速模型：用于提取类 Agent（JD/画像/差距/评审/澄清），
    # 为空时回退到 llm_model。
    fast_model: str = ""

    # JWT Auth（同样必须从环境注入，空值在 AuthService 使用时抛出明确错误）
    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # File storage
    upload_dir: str = "uploads"

    # Graph 执行总超时（秒）：单 Agent 120s，整条流水线兜底
    graph_timeout: int = 600

    # extra="ignore"：容忍 .env 中为 docker compose 等提供的额外变量
    # （如 MYSQL_PASSWORD / MYSQL_ROOT_PASSWORD），避免从项目根启动时崩溃
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
