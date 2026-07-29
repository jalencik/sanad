import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

settings = get_settings()

_CHUNK_SIZE = 1024 * 1024


class UploadTooLarge(Exception):
    pass


class UploadContentMismatch(Exception):
    pass


def _looks_like(head: bytes, mime_type: str) -> bool:
    # Sniffs real file bytes rather than trusting the client-supplied
    # Content-Type header (trivially spoofable) - this is what actually
    # keeps a mislabeled file out of the pipeline and off disk.
    if mime_type == "application/pdf":
        return head.startswith(b"%PDF-")
    if mime_type == "image/png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return head.startswith(b"\xff\xd8\xff")
    if mime_type == "image/tiff":
        return head.startswith((b"II*\x00", b"MM\x00*"))
    if mime_type == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


def ensure_upload_dir() -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings.upload_dir


async def save_upload(file: UploadFile, mime_type: str, max_size_bytes: int) -> tuple[str, int]:
    """Streams the upload to disk, enforcing the size cap as bytes arrive
    (not after the fact) and verifying the first chunk actually matches the
    declared MIME type. Raises UploadTooLarge/UploadContentMismatch and
    cleans up the partial file on either failure."""
    upload_dir = ensure_upload_dir()
    suffix = Path(file.filename or "").suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    destination = upload_dir / stored_name

    size = 0
    first_chunk = True
    try:
        with destination.open("wb") as out_file:
            while chunk := await file.read(_CHUNK_SIZE):
                if first_chunk:
                    if not _looks_like(chunk, mime_type):
                        raise UploadContentMismatch(f"File content doesn't match declared type {mime_type}")
                    first_chunk = False

                size += len(chunk)
                if size > max_size_bytes:
                    raise UploadTooLarge(f"File exceeds {max_size_bytes} byte limit")

                out_file.write(chunk)
    except (UploadTooLarge, UploadContentMismatch):
        destination.unlink(missing_ok=True)
        raise

    return stored_name, size


def resolve_path(stored_filename: str) -> Path:
    return settings.upload_dir / stored_filename
