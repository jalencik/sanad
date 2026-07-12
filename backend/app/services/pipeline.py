import asyncio
import logging
import uuid

from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.services import ai, ocr, storage

logger = logging.getLogger(__name__)

# Real pipeline checkpoints, not a time-based estimate: each number is set
# the instant that stage actually finishes, so the percentage a user sees
# always reflects genuine progress rather than a guess.
PROGRESS_QUEUED = 10
PROGRESS_OCR_DONE = 55
PROGRESS_ANALYSIS_DONE = 90
PROGRESS_COMPLETE = 100

# OCR is CPU-heavy (Tesseract + 300-DPI page rasterization). Running it via
# to_thread keeps the event loop free, but unbounded parallel Tesseract on a
# small host (Render free tier: fractional CPU, 512MB) would thrash or OOM -
# cap concurrent jobs; further uploads simply wait their turn in "queued".
_ocr_slots = asyncio.Semaphore(2)


async def process_document(document_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        document.progress_percent = PROGRESS_QUEUED
        await session.commit()

        try:
            path = storage.resolve_path(document.stored_filename)

            # Both OCR and the Gemini call are synchronous, seconds-long
            # blocking calls. Awaiting them directly on the event loop froze
            # the WHOLE API (polls, logins, everything) for the duration of
            # every document - to_thread moves them off the loop so the
            # server stays responsive while documents process.
            async with _ocr_slots:
                ocr_result = await asyncio.to_thread(ocr.run_ocr, path, document.mime_type)

            document.ocr_text = ocr_result.text
            document.ocr_confidence = ocr_result.confidence
            document.progress_percent = PROGRESS_OCR_DONE
            await session.commit()

            if not ocr_result.text.strip():
                raise ValueError("No text could be extracted from this document")

            analysis = await asyncio.to_thread(ai.analyze_document_text, ocr_result.text)

            document.document_type = analysis.document_type
            document.document_number = analysis.document_number
            document.issuing_authority = analysis.issuing_authority
            document.issue_date = analysis.issue_date
            document.expiry_date = analysis.expiry_date
            document.detected_language = analysis.detected_language
            document.key_fields = {field.key: field.value for field in analysis.key_fields}
            document.summary_original = analysis.summary_original
            document.summary_english = analysis.summary_english
            document.progress_percent = PROGRESS_ANALYSIS_DONE
            document.status = DocumentStatus.DONE
            document.progress_percent = PROGRESS_COMPLETE

        except Exception as exc:  # noqa: BLE001 - pipeline boundary, persist any failure
            logger.exception("Document processing failed for %s", document_id)
            document.status = DocumentStatus.ERROR
            document.error_message = str(exc)

        await session.commit()
