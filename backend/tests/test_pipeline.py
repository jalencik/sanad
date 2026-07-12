import uuid
from unittest.mock import patch

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.ai import DocumentAnalysis, KeyField
from app.services.ocr import OcrResult
from app.services.pipeline import process_document


async def _create_test_user() -> uuid.UUID:
    async with async_session_factory() as session:
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            hashed_password=hash_password("correct-horse-battery"),
            full_name="Pipeline Test User",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def test_process_document_success():
    user_id = await _create_test_user()

    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="passport.png",
            stored_filename="stored.png",
            mime_type="image/png",
            file_size=10,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    fake_analysis = DocumentAnalysis(
        document_type="passport",
        document_number="AB1234567",
        issuing_authority="Ministry of Internal Affairs",
        issue_date="2020-01-01",
        expiry_date="2030-01-01",
        detected_language="Uzbek",
        key_fields=[KeyField(key="full_name", value="John Doe")],
        summary_original="Original summary.",
        summary_english="English summary.",
    )

    with (
        patch("app.services.pipeline.ocr.run_ocr", return_value=OcrResult(text="sample text", confidence=0.9)),
        patch("app.services.pipeline.ai.analyze_document_text", return_value=fake_analysis),
    ):
        await process_document(document_id)

    async with async_session_factory() as session:
        refreshed = await session.get(Document, document_id)
        assert refreshed.status == DocumentStatus.DONE
        assert refreshed.document_number == "AB1234567"
        assert refreshed.summary_english == "English summary."


async def test_process_document_marks_error_on_empty_ocr():
    user_id = await _create_test_user()

    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="blank.png",
            stored_filename="blank.png",
            mime_type="image/png",
            file_size=10,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    with patch("app.services.pipeline.ocr.run_ocr", return_value=OcrResult(text="", confidence=0.0)):
        await process_document(document_id)

    async with async_session_factory() as session:
        refreshed = await session.get(Document, document_id)
        assert refreshed.status == DocumentStatus.ERROR
        assert refreshed.error_message
