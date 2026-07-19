from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://sanad:sanad@localhost:5432/sanad"

    # Single-key config, kept for back-compat with existing deployments/tests.
    gemini_api_key: str = ""
    # Preferred: up to 5 free-tier keys, comma-separated, rotated on failure -
    # see app/services/gemini_pool.py. Falls back to gemini_api_key above if unset.
    gemini_api_keys: str = ""
    gemini_model: str = "gemini-flash-latest"

    @property
    def gemini_keys(self) -> list[str]:
        if self.gemini_api_keys.strip():
            return [key.strip() for key in self.gemini_api_keys.split(",") if key.strip()]
        if self.gemini_api_key.strip():
            return [self.gemini_api_key.strip()]
        return []

    @field_validator("database_url")
    @classmethod
    def _use_async_driver(cls, value: str) -> str:
        # Managed Postgres providers (Render, Heroku, Railway, Supabase, ...)
        # hand out a bare postgresql:// URL, which resolves to the sync
        # psycopg2 driver - incompatible with the async engine this app uses
        # everywhere. Normalize it here so deploying anywhere doesn't depend
        # on remembering to hand-edit the connection string.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

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

    # Emails in this list are granted admin access on signup/login. Controlled
    # entirely by env var - no manual DB edits needed to promote an account.
    admin_emails: list[str] = []

    # "Continue with Google" is disabled (Google endpoints return a clear 503)
    # until all three of these are set - create the OAuth client yourself in
    # Google Cloud Console, this app never touches your Google account.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.google_redirect_uri)

    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
