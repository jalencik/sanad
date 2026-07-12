from app.core.config import Settings


def test_bare_postgresql_url_gets_asyncpg_driver():
    settings = Settings(database_url="postgresql://user:pass@host.render.com/dbname", _env_file=None)
    assert settings.database_url == "postgresql+asyncpg://user:pass@host.render.com/dbname"


def test_already_async_url_is_left_unchanged():
    settings = Settings(database_url="postgresql+asyncpg://user:pass@host/dbname", _env_file=None)
    assert settings.database_url == "postgresql+asyncpg://user:pass@host/dbname"


def test_non_postgres_url_is_left_unchanged():
    settings = Settings(database_url="sqlite+aiosqlite:///./test.db", _env_file=None)
    assert settings.database_url == "sqlite+aiosqlite:///./test.db"
