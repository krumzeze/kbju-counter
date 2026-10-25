from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: SecretStr
    database_url: str = "postgresql+asyncpg://belok:belok@localhost:5432/belok"
    redis_url: str = "redis://localhost:6379/0"

    llm_api_key: SecretStr
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-5-mini"

    api_secret: SecretStr | None = None
    bot_username: str | None = None
    webapp_url: str | None = None

    trial_days: int = 4
    daily_analysis_limit: int = 20
    default_timezone: str = "Europe/Moscow"
    log_level: str = "INFO"
