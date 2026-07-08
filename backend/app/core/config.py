from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://sanad:sanad@localhost:5432/sanad"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    upload_dir: Path = BASE_DIR / "uploads"
    max_upload_size_mb: int = 25
    allowed_mime_types: tuple[str, ...] = (
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/webp",
    )

    tesseract_languages: str = "eng+rus+uzb+uzb_cyrl"
    max_pdf_pages: int = 8

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost",
    ]

    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
