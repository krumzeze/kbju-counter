from belok.config import Settings, async_database_url


def test_database_url_is_converted_to_asyncpg():
    assert async_database_url("postgresql://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"
    assert async_database_url("postgres://u@h/db") == "postgresql+asyncpg://u@h/db"
    assert async_database_url("postgresql+asyncpg://h/db") == "postgresql+asyncpg://h/db"


def test_empty_admin_id_means_unset():
    settings = Settings(bot_token="1:x", llm_api_key="k", admin_id="")
    assert settings.admin_id is None
