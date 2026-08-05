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

    # LLM providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    zhipuai_api_key: str = ""

    # File storage
    upload_dir: str = "uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
