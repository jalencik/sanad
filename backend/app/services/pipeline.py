import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

# A single document should never legitimately take longer than this. Without
# a cap, a hung OCR call or a stalled network connection to Gemini holds its
# thread (and the user's progress bar) forever - this turns a silent freeze
# into an honest, visible failure the user can just retry.
PROCESS_TIMEOUT_SECONDS = 300

# Keeps strong references to startup-recovery tasks so they can't be
# garbage-collected mid-flight (asyncio only holds a weak reference to a
# bare create_task() result) - re-losing a "resumed" document to the exact
# bug this exists to fix would be a bad way to find that out.
_background_tasks: set[asyncio.Task] = set()


def _spawn(document_id: uuid.UUID) -> asyncio.Task[None]:
    task = asyncio.create_task(process_document(document_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def process_document(document_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        document.progress_percent = PROGRESS_QUEUED
        await session.commit()

        try:
            await asyncio.wait_for(_run_pipeline(document, session), timeout=PROCESS_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.error("Document processing timed out for %s", document_id)
            document.status = DocumentStatus.ERROR
            document.error_message = "Processing took too long. Please try uploading again."
        except Exception as exc:  # noqa: BLE001 - pipeline boundary, persist any failure
            logger.exception("Document processing failed for %s", document_id)
            document.status = DocumentStatus.ERROR
            document.error_message = str(exc)

        await session.commit()


async def _run_pipeline(document: Document, session: AsyncSession) -> None:
    # Both OCR and the Gemini call are synchronous, seconds-long blocking
    # calls. Awaiting them directly on the event loop froze the WHOLE API
    # (polls, logins, everything) for the duration of every document -
    # to_thread moves them off the loop so the server stays responsive.
    if document.ocr_text is None:
        path = storage.resolve_path(document.stored_filename)

        async with _ocr_slots:
            ocr_result = await asyncio.to_thread(ocr.run_ocr, path, document.mime_type)

        document.ocr_text = ocr_result.text
        document.ocr_confidence = ocr_result.confidence
        document.progress_percent = PROGRESS_OCR_DONE
        await session.commit()

    if not document.ocr_text.strip():
        raise ValueError("No text could be extracted from this document")

    analysis = await asyncio.to_thread(ai.analyze_document_text, document.ocr_text)

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


async def recover_stuck_documents() -> list[asyncio.Task[None]]:
    """Runs once at startup. Document processing lives only in this
    process's memory (FastAPI BackgroundTasks, no durable queue) - anything
    still pending/processing belongs to a process that no longer exists (a
    redeploy, a crash, a free-tier instance recycle), so it's safe to assume
    every one of these was abandoned and pick it back up."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Document.id).where(Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING]))
        )
        stuck_ids = [row[0] for row in result.all()]

    if stuck_ids:
        logger.info("Resuming %d document(s) left mid-processing by a previous run", len(stuck_ids))

    return [_spawn(document_id) for document_id in stuck_ids]
