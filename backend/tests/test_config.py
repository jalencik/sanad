from app.core.config import Settings


def test_gemini_keys_splits_comma_separated_list():
    settings = Settings(gemini_api_keys="key1, key2 ,key3", _env_file=None)
    assert settings.gemini_keys == ["key1", "key2", "key3"]


def test_gemini_keys_falls_back_to_singular_key_when_list_unset():
    settings = Settings(gemini_api_key="solo-key", gemini_api_keys="", _env_file=None)
    assert settings.gemini_keys == ["solo-key"]


def test_gemini_keys_empty_when_nothing_configured():
    settings = Settings(gemini_api_key="", gemini_api_keys="", _env_file=None)
    assert settings.gemini_keys == []


def test_bare_postgresql_url_gets_asyncpg_driver():
    settings = Settings(database_url="postgresql://user:pass@host.render.com/dbname", _env_file=None)
    assert settings.database_url == "postgresql+asyncpg://user:pass@host.render.com/dbname"


def test_already_async_url_is_left_unchanged():
    settings = Settings(database_url="postgresql+asyncpg://user:pass@host/dbname", _env_file=None)
    assert settings.database_url == "postgresql+asyncpg://user:pass@host/dbname"


def test_non_postgres_url_is_left_unchanged():
    settings = Settings(database_url="sqlite+aiosqlite:///./test.db", _env_file=None)
    assert settings.database_url == "sqlite+aiosqlite:///./test.db"
