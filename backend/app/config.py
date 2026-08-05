"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings


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
    openai_api_key: str = "tp-c43d5n48zwz32jbqbq6kvb039wpbedr8slb1s9r37igtbsj6"
    llm_base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"
    llm_model: str = "mimo-v2.5-pro"

    # File storage
    upload_dir: str = "uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
