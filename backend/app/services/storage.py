from fastapi import UploadFile


class UploadTooLarge(Exception):
    pass


class UploadContentMismatch(Exception):
    pass


def _looks_like(head: bytes, mime_type: str) -> bool:
    # Sniffs real file bytes rather than trusting the client-supplied
    # Content-Type header (trivially spoofable) - this is what actually
    # keeps a mislabeled file out of the pipeline.
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


_CHUNK_SIZE = 1024 * 1024


async def save_upload(file: UploadFile, mime_type: str, max_size_bytes: int) -> bytes:
    """Validates an upload as bytes arrive and returns the full content.

    Enforces the size cap incrementally (never buffers past it) and verifies
    the first chunk actually matches the declared MIME type, exactly as
    before - the only change is the validated bytes are handed back to the
    caller to persist (in the documents table) instead of being written to
    local disk, which Render's free tier doesn't preserve across a redeploy
    or a scale-to-zero cycle anyway.
    """
    chunks: list[bytes] = []
    size = 0
    first_chunk = True

    while chunk := await file.read(_CHUNK_SIZE):
        if first_chunk:
            if not _looks_like(chunk, mime_type):
                raise UploadContentMismatch(f"File content doesn't match declared type {mime_type}")
            first_chunk = False

        size += len(chunk)
        if size > max_size_bytes:
            raise UploadTooLarge(f"File exceeds {max_size_bytes} byte limit")

        chunks.append(chunk)

    return b"".join(chunks)
