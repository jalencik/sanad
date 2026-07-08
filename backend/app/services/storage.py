import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

settings = get_settings()


def ensure_upload_dir() -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings.upload_dir


async def save_upload(file: UploadFile) -> tuple[str, int]:
    upload_dir = ensure_upload_dir()
    suffix = Path(file.filename or "").suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    destination = upload_dir / stored_name

    size = 0
    with destination.open("wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            out_file.write(chunk)

    return stored_name, size


def resolve_path(stored_filename: str) -> Path:
    return settings.upload_dir / stored_filename
