import io
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.models.user import User


async def test_reject_unsupported_file_type(client):
    response = await client.post(
        "/api/documents",
        files={"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 415


async def test_upload_creates_pending_document(client):
    with patch("app.api.documents.process_document", new=AsyncMock()):
        response = await client.post(
            "/api/documents",
            files={"file": ("scan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["original_filename"] == "scan.png"


async def test_list_and_get_document(client):
    with patch("app.api.documents.process_document", new=AsyncMock()):
        upload = await client.post(
            "/api/documents",
            files={"file": ("scan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )
    document_id = upload.json()["id"]

    listing = await client.get("/api/documents")
    assert listing.status_code == 200
    assert any(doc["id"] == document_id for doc in listing.json())

    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == document_id


async def test_get_missing_document_returns_404(client):
    response = await client.get("/api/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_processing_document_has_no_eta_without_history(client):
    with patch("app.api.documents.process_document", new=AsyncMock()):
        upload = await client.post(
            "/api/documents",
            files={"file": ("scan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )
    document_id = upload.json()["id"]

    async with async_session_factory() as session:
        document = await session.get(Document, uuid.UUID(document_id))
        document.status = DocumentStatus.PROCESSING
        document.processing_started_at = datetime.now(UTC)
        await session.commit()

    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.json()["estimated_completion_at"] is None


async def test_processing_document_gets_eta_once_history_exists(client):
    async with async_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "test.user@example.com"))).scalar_one()
        now = datetime.now(UTC)
        session.add(
            Document(
                user_id=user.id,
                original_filename="prior.png",
                stored_filename=f"{uuid.uuid4()}.png",
                mime_type="image/png",
                file_size=10,
                status=DocumentStatus.DONE,
                processing_started_at=now - timedelta(seconds=15),
                updated_at=now,
            )
        )
        await session.commit()

    with patch("app.api.documents.process_document", new=AsyncMock()):
        upload = await client.post(
            "/api/documents",
            files={"file": ("scan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )
    document_id = upload.json()["id"]

    async with async_session_factory() as session:
        document = await session.get(Document, uuid.UUID(document_id))
        document.status = DocumentStatus.PROCESSING
        document.processing_started_at = datetime.now(UTC)
        await session.commit()

    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.json()["estimated_completion_at"] is not None

    listing = await client.get("/api/documents")
    listed = next(doc for doc in listing.json() if doc["id"] == document_id)
    assert listed["estimated_completion_at"] is not None


async def test_cancel_processing_document_marks_it_cancelled(client):
    with patch("app.api.documents.process_document", new=AsyncMock()):
        upload = await client.post(
            "/api/documents",
            files={"file": ("scan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )
    document_id = upload.json()["id"]

    async with async_session_factory() as session:
        document = await session.get(Document, uuid.UUID(document_id))
        document.status = DocumentStatus.PROCESSING
        document.processing_started_at = datetime.now(UTC)
        await session.commit()

    response = await client.post(f"/api/documents/{document_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error_message"] == "Cancelled."

    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.json()["status"] == "error"
    assert detail.json()["error_message"] == "Cancelled."


async def test_cancel_already_finished_document_is_rejected(client):
    with patch("app.api.documents.process_document", new=AsyncMock()):
        upload = await client.post(
            "/api/documents",
            files={"file": ("scan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )
    document_id = upload.json()["id"]

    async with async_session_factory() as session:
        document = await session.get(Document, uuid.UUID(document_id))
        document.status = DocumentStatus.DONE
        await session.commit()

    response = await client.post(f"/api/documents/{document_id}/cancel")
    assert response.status_code == 409

    detail = await client.get(f"/api/documents/{document_id}")
    assert detail.json()["status"] == "done"


async def test_upload_rejects_content_that_does_not_match_declared_type(client):
    response = await client.post(
        "/api/documents",
        files={"file": ("scan.png", io.BytesIO(b"not actually a png"), "image/png")},
    )
    assert response.status_code == 415


async def test_upload_rate_limited_after_repeated_attempts(client):
    with patch("app.api.documents.process_document", new=AsyncMock()):
        for _ in range(20):
            response = await client.post(
                "/api/documents",
                files={"file": ("scan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
            )
            assert response.status_code == 201

        response = await client.post(
            "/api/documents",
            files={"file": ("scan.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )
    assert response.status_code == 429
