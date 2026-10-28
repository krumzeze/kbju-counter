from belok.config import async_database_url


def test_database_url_is_converted_to_asyncpg():
    assert async_database_url("postgresql://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"
    assert async_database_url("postgres://u@h/db") == "postgresql+asyncpg://u@h/db"
    assert async_database_url("postgresql+asyncpg://h/db") == "postgresql+asyncpg://h/db"
