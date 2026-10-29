from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def async_database_url(url: str) -> str:
    """Accept plain postgresql:// URLs, e.g. the one CloudNativePG puts into its app secret."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url.removeprefix(prefix)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: SecretStr
    database_url: str = "postgresql+asyncpg://belok:belok@localhost:5432/belok"
    redis_url: str = "redis://localhost:6379/0"

    llm_api_key: SecretStr
    llm_model: str = "claude-haiku-5-5"

    api_secret: SecretStr | None = None
    bot_username: str | None = None
    webapp_url: str | None = None

    trial_days: int = 4
    daily_analysis_limit: int = 20
    default_timezone: str = "Europe/Moscow"
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def use_asyncpg(cls, value: str) -> str:
        return async_database_url(value)
