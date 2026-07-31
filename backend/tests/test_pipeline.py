import asyncio
import time
import uuid
from unittest.mock import patch

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services import pipeline
from app.services.ai import DocumentAnalysis, KeyField
from app.services.ocr import OcrResult
from app.services.pipeline import (
    CANCELLED_MESSAGE,
    PROGRESS_COMPLETE,
    PROGRESS_OCR_DONE,
    process_document,
    recover_stuck_documents,
)


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
            file_content=b"fake image bytes",
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
        assert refreshed.progress_percent == PROGRESS_COMPLETE


async def test_process_document_never_holds_one_session_across_the_ocr_and_ai_calls():
    # Regression guard: process_document used to open a single DB session
    # and hold it for the entire pipeline, including the (potentially
    # minutes-long) OCR/AI calls. Under concurrent uploads that exhausted
    # the connection pool and hung unrelated requests (login, cancel,
    # refresh). Each database touch must now be its own short-lived
    # session - proven here by counting how many times a session is opened
    # during one successful run: mark-processing, OCR-done write, and
    # mark-done, at minimum.
    user_id = await _create_test_user()

    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="passport.png",
            file_content=b"fake image bytes",
            mime_type="image/png",
            file_size=10,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    fake_analysis = DocumentAnalysis(
        document_type="passport", detected_language="Uzbek", summary_original="s", summary_english="s"
    )

    session_open_count = 0
    real_factory = async_session_factory

    def _counting_factory():
        nonlocal session_open_count
        session_open_count += 1
        return real_factory()

    with (
        patch("app.services.pipeline.ocr.run_ocr", return_value=OcrResult(text="text", confidence=0.9)),
        patch("app.services.pipeline.ai.analyze_document_text", return_value=fake_analysis),
        patch("app.services.pipeline.async_session_factory", side_effect=_counting_factory),
    ):
        await process_document(document_id)

    assert session_open_count >= 3

    async with async_session_factory() as session:
        refreshed = await session.get(Document, document_id)
        assert refreshed.status == DocumentStatus.DONE


async def test_process_document_marks_error_on_empty_ocr():
    user_id = await _create_test_user()

    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="blank.png",
            file_content=b"fake image bytes",
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
        assert refreshed.progress_percent == PROGRESS_OCR_DONE


async def test_process_document_reports_ocr_failure_distinctly_from_ai_failure():
    # Regression guard: an unexpected exception from OCR and one from the AI
    # call used to collapse into the exact same generic "something went
    # wrong" message - impossible to tell which stage actually broke without
    # server logs. Each stage now gets its own specific, still-safe message.
    user_id = await _create_test_user()

    async def _make_document(name: str) -> uuid.UUID:
        async with async_session_factory() as session:
            document = Document(
                user_id=user_id,
                original_filename=name,
                file_content=b"fake image bytes",
                mime_type="image/png",
                file_size=10,
            )
            session.add(document)
            await session.commit()
            await session.refresh(document)
            return document.id

    ocr_failure_id = await _make_document("a.png")
    with patch("app.services.pipeline.ocr.run_ocr", side_effect=RuntimeError("tesseract exploded")):
        await process_document(ocr_failure_id)

    ai_failure_id = await _make_document("b.png")
    with (
        patch("app.services.pipeline.ocr.run_ocr", return_value=OcrResult(text="some text", confidence=0.9)),
        patch("app.services.pipeline.ai.analyze_document_text", side_effect=RuntimeError("every provider down")),
    ):
        await process_document(ai_failure_id)

    async with async_session_factory() as session:
        ocr_failure = await session.get(Document, ocr_failure_id)
        ai_failure = await session.get(Document, ai_failure_id)

    assert "read this document" in ocr_failure.error_message
    assert "analyze it right now" in ai_failure.error_message
    assert ocr_failure.error_message != ai_failure.error_message


async def test_process_document_reports_password_protected_pdfs_definitively():
    # A password-protected PDF isn't corrupted or unsupported - it's a
    # known, specific condition (see ocr.PasswordProtectedError) and the
    # user should hear that as a fact, not as one guess among three.
    user_id = await _create_test_user()

    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="locked.pdf",
            file_content=b"fake pdf bytes",
            mime_type="application/pdf",
            file_size=10,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    from app.services.ocr import PasswordProtectedError

    with patch("app.services.pipeline.ocr.run_ocr", side_effect=PasswordProtectedError("needs a password")):
        await process_document(document_id)

    async with async_session_factory() as session:
        refreshed = await session.get(Document, document_id)
        assert refreshed.status == DocumentStatus.ERROR
        assert refreshed.error_message == (
            "This PDF is password-protected. Please remove the password and upload again."
        )


async def test_process_document_skips_ocr_when_text_already_saved():
    # Simulates resuming a document a previous process got partway through:
    # OCR text is already on the row, so re-running OCR would waste the
    # free-tier host's scarce CPU for no reason.
    user_id = await _create_test_user()

    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="resumed.png",
            mime_type="image/png",
            file_size=10,
            status=DocumentStatus.PROCESSING,
            progress_percent=PROGRESS_OCR_DONE,
            ocr_text="already extracted text",
            ocr_confidence=0.8,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    fake_analysis = DocumentAnalysis(
        document_type="passport",
        detected_language="Uzbek",
        summary_original="s",
        summary_english="s",
    )

    with (
        patch("app.services.pipeline.ocr.run_ocr") as mock_ocr,
        patch("app.services.pipeline.ai.analyze_document_text", return_value=fake_analysis) as mock_ai,
    ):
        await process_document(document_id)

    mock_ocr.assert_not_called()
    mock_ai.assert_called_once_with("already extracted text")

    async with async_session_factory() as session:
        refreshed = await session.get(Document, document_id)
        assert refreshed.status == DocumentStatus.DONE


def _slow_ocr(*args, **kwargs) -> OcrResult:
    time.sleep(0.3)
    return OcrResult(text="text", confidence=0.9)


async def test_process_document_marks_error_on_timeout(monkeypatch):
    # A hung OCR/network call must fail loudly instead of holding its slot
    # (and the user's progress bar) forever.
    monkeypatch.setattr(pipeline, "PROCESS_TIMEOUT_SECONDS", 0.05)

    user_id = await _create_test_user()
    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="slow.png",
            file_content=b"fake image bytes",
            mime_type="image/png",
            file_size=10,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    with patch("app.services.pipeline.ocr.run_ocr", side_effect=_slow_ocr):
        await process_document(document_id)

    async with async_session_factory() as session:
        refreshed = await session.get(Document, document_id)
        assert refreshed.status == DocumentStatus.ERROR
        assert "too long" in refreshed.error_message.lower()


async def test_request_cancel_returns_false_when_nothing_is_running():
    assert pipeline.request_cancel(uuid.uuid4()) is False


async def test_request_cancel_stops_a_running_task_and_marks_it_cancelled():
    user_id = await _create_test_user()

    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="scan.png",
            file_content=b"fake image bytes",
            mime_type="image/png",
            file_size=10,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    started = asyncio.Event()
    release = asyncio.Event()

    def _blocking_ocr(*args, **kwargs):
        # Runs on a real OS thread via to_thread - a plain blocking wait
        # here is the honest equivalent of a stuck Tesseract call, and lets
        # this test control exactly when it's "still running" vs "finished"
        # relative to the cancel request.
        started.set()
        while not release.is_set():
            time.sleep(0.01)
        return OcrResult(text="text", confidence=0.9)

    with patch("app.services.pipeline.ocr.run_ocr", side_effect=_blocking_ocr):
        task = pipeline._spawn(document_id)
        await asyncio.wait_for(started.wait(), timeout=2)

        assert pipeline.request_cancel(document_id) is True

        release.set()
        await asyncio.wait_for(task, timeout=2)

    async with async_session_factory() as session:
        refreshed = await session.get(Document, document_id)
        assert refreshed.status == DocumentStatus.ERROR
        assert refreshed.error_message == CANCELLED_MESSAGE


async def test_recover_stuck_documents_requeues_only_pending_and_processing():
    user_id = await _create_test_user()

    async def _make_document(status: DocumentStatus, progress: int) -> uuid.UUID:
        async with async_session_factory() as session:
            document = Document(
                user_id=user_id,
                original_filename="doc.png",
                file_content=b"fake image bytes",
                mime_type="image/png",
                file_size=10,
                status=status,
                progress_percent=progress,
            )
            session.add(document)
            await session.commit()
            await session.refresh(document)
            return document.id

    pending_id = await _make_document(DocumentStatus.PENDING, 0)
    processing_id = await _make_document(DocumentStatus.PROCESSING, 10)
    await _make_document(DocumentStatus.DONE, 100)

    fake_analysis = DocumentAnalysis(
        document_type="passport",
        detected_language="Uzbek",
        summary_original="s",
        summary_english="s",
    )

    with (
        patch(
            "app.services.pipeline.ocr.run_ocr", return_value=OcrResult(text="text", confidence=0.9)
        ) as mock_ocr,
        patch("app.services.pipeline.ai.analyze_document_text", return_value=fake_analysis) as mock_ai,
    ):
        tasks = await recover_stuck_documents()
        await asyncio.gather(*tasks)

    assert mock_ocr.call_count == 2
    assert mock_ai.call_count == 2

    async with async_session_factory() as session:
        pending_doc = await session.get(Document, pending_id)
        processing_doc = await session.get(Document, processing_id)

    assert pending_doc.status == DocumentStatus.DONE
    assert processing_doc.status == DocumentStatus.DONE
