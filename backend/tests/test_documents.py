import io
from unittest.mock import AsyncMock, patch


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
