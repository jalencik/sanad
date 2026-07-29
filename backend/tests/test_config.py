import pytest
from pydantic import ValidationError

from app.core.config import Settings

_VALID_JWT_SECRET = "a" * 32


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


def test_groq_keys_splits_comma_separated_list():
    settings = Settings(groq_api_keys="key1, key2 ,key3", jwt_secret_key=_VALID_JWT_SECRET, _env_file=None)
    assert settings.groq_keys == ["key1", "key2", "key3"]


def test_groq_keys_empty_when_unconfigured():
    settings = Settings(groq_api_keys="", jwt_secret_key=_VALID_JWT_SECRET, _env_file=None)
    assert settings.groq_keys == []


def test_ai_provider_auto_prefers_groq_when_configured():
    settings = Settings(groq_api_keys="key1", gemini_api_keys="key2", jwt_secret_key=_VALID_JWT_SECRET, _env_file=None)
    assert settings.resolved_ai_provider == "groq"


def test_ai_provider_auto_falls_back_to_gemini_when_groq_unconfigured():
    settings = Settings(groq_api_keys="", gemini_api_keys="key2", jwt_secret_key=_VALID_JWT_SECRET, _env_file=None)
    assert settings.resolved_ai_provider == "gemini"


def test_ai_provider_can_be_forced_to_gemini_even_when_groq_is_configured():
    settings = Settings(
        groq_api_keys="key1", ai_provider="gemini", jwt_secret_key=_VALID_JWT_SECRET, _env_file=None
    )
    assert settings.resolved_ai_provider == "gemini"


def test_default_jwt_secret_is_rejected():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(jwt_secret_key="dev-only-insecure-secret-change-me", _env_file=None)


def test_short_jwt_secret_is_rejected():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(jwt_secret_key="too-short", _env_file=None)


def test_valid_jwt_secret_is_accepted():
    settings = Settings(jwt_secret_key=_VALID_JWT_SECRET, _env_file=None)
    assert settings.jwt_secret_key == _VALID_JWT_SECRET
