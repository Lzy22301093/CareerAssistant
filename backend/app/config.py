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

    # 语音模型（共享 base_url / api_key）
    asr_model: str = "mimo-v2.5-asr"
    tts_model: str = "mimo-v2.5-tts"
    # TTS 默认音色 / 语速（用户可在语音面试页覆盖）
    # 官网示例音色：Chloe / Mia / Milo / Dean
    tts_default_voice: str = "Chloe"
    tts_default_speed: float = 1.1

    # JWT Auth（同样必须从环境注入，空值在 AuthService 使用时抛出明确错误）
    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # File storage
    upload_dir: str = "uploads"

    # 单次 LLM API 请求超时（秒）：略低于单 Agent 超时 120s（agents/base.py），
    # 让 SDK 先超时抛 APITimeoutError（可分类、可重试），而不是 agent 级 wait_for
    # 先取消成裸 asyncio.TimeoutError。
    llm_timeout: int = 110

    # Graph 执行总超时（秒）：单 Agent 120s，整条流水线兜底
    graph_timeout: int = 600

    # Plan 路由模式（Track B 4.5 分步切换）：
    # - legacy: 固定图单步路由（原行为）
    # - shadow: 影子期——构建 Plan 与旧路由并行对比，仅告警不切换（S1，默认）
    # - plan_first: 灰度——仅 plan_grayscale_intents 中的意图走 Plan 执行器（S3）
    # - plan_only: 全量——所有流水线意图走 Plan 执行器（S4），兜底仍回退旧路由
    plan_routing_mode: str = "shadow"
    # plan_first 灰度阶段的意图白名单
    plan_grayscale_intents: list[str] = [
        "upload_jd", "upload_profile", "fallback",
        "gap_analysis", "content_edit", "render_edit",
    ]

    # extra="ignore"：容忍 .env 中为 docker compose 等提供的额外变量
    # （如 MYSQL_PASSWORD / MYSQL_ROOT_PASSWORD），避免从项目根启动时崩溃
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
