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

    # Any OpenAI-compatible speech-to-text API; voice messages are off without a key.
    stt_api_key: SecretStr | None = None
    stt_base_url: str = "https://api.openai.com/v1"
    stt_model: str = "whisper-1"

    # Cloudflare R2 (S3 API) for meal photos; photos are not kept without it.
    r2_endpoint: str | None = None
    r2_bucket: str | None = None
    r2_access_key_id: SecretStr | None = None
    r2_secret_access_key: SecretStr | None = None
    # Must match the bucket lifecycle rule in infra/terraform.
    photo_retention_days: int = 90

    api_secret: SecretStr | None = None
    bot_username: str | None = None
    webapp_url: str | None = None
    admin_id: int | None = None

    tribute_api_key: SecretStr | None = None
    # Comma-separated "<product code from the web.tribute.tg/p/ link>:<days>".
    tribute_plans: str = "IMK:30,IMM:90,IMO:365"
    # Comma-separated "<days>:<price in Telegram Stars>".
    stars_plans: str = "30:150,90:375,365:1250"

    trial_days: int = 4
    referral_trial_days: int = 7
    referral_reward_days: int = 7
    daily_analysis_limit: int = 20
    free_daily_analyses: int = 2
    free_history_days: int = 30
    default_timezone: str = "Europe/Moscow"
    log_level: str = "INFO"

    @field_validator(
        "admin_id",
        "tribute_api_key",
        "stt_api_key",
        "r2_endpoint",
        "r2_bucket",
        "r2_access_key_id",
        "r2_secret_access_key",
        mode="before",
    )
    @classmethod
    def empty_as_none(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def photos_enabled(self) -> bool:
        return bool(
            self.r2_endpoint
            and self.r2_bucket
            and self.r2_access_key_id
            and self.r2_secret_access_key
        )

    @field_validator("database_url")
    @classmethod
    def use_asyncpg(cls, value: str) -> str:
        return async_database_url(value)
