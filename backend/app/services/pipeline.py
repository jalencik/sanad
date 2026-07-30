import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.services import ai, ocr

logger = logging.getLogger(__name__)

# Real pipeline checkpoints, not a time-based estimate: each number is set
# the instant that stage actually finishes, so the percentage a user sees
# always reflects genuine progress rather than a guess.
PROGRESS_QUEUED = 10
PROGRESS_OCR_DONE = 55
PROGRESS_ANALYSIS_DONE = 90
PROGRESS_COMPLETE = 100

# OCR is CPU-heavy (Tesseract + 300-DPI page rasterization). Running it via
# to_thread keeps the event loop free, but Render's free tier gives this
# whole app a fractional (0.1) vCPU - two Tesseract processes fighting over
# that isn't real parallelism, it's both jobs running slower, which only
# makes the PROCESS_TIMEOUT_SECONDS race below worse for both. One at a time
# is both safer and, in practice, not meaningfully slower end to end; further
# uploads simply wait their turn in "queued".
_ocr_slots = asyncio.Semaphore(1)

# A single document should never legitimately take longer than this. Without
# a cap, a hung OCR call or a stalled network connection to Gemini holds its
# thread (and the user's progress bar) forever - this turns a silent freeze
# into an honest, visible failure the user can just retry.
#
# This has to stay honest about the pipeline's own worst case, or it fires
# on a document that was never actually stuck: OCR alone can legitimately
# take up to max_pdf_pages * _PAGE_TIMEOUT_SECONDS (app/services/ocr.py) -
# 8 * 60s = 480s today - before the AI call even starts, and that call can
# itself retry across every configured Groq/Gemini key (app/services/ai.py)
# before giving up. 900s leaves real headroom above that combined worst
# case instead of quietly assuming OCR would always be fast.
PROCESS_TIMEOUT_SECONDS = 900

CANCELLED_MESSAGE = "Cancelled."


class PipelineError(Exception):
    """A pipeline failure whose message is already safe to show the user
    as-is, as opposed to an arbitrary exception that might repeat back
    internal details (file paths, a library's raw error body, ...)."""


# Keeps strong references to startup-recovery tasks so they can't be
# garbage-collected mid-flight (asyncio only holds a weak reference to a
# bare create_task() result) - re-losing a "resumed" document to the exact
# bug this exists to fix would be a bad way to find that out.
_background_tasks: set[asyncio.Task] = set()

# Lets a cancel request find the task actually processing a given document,
# and lets that task's own cooperative checkpoints (see _run_pipeline) notice
# a cancellation that arrived mid-OCR or mid-AI-call, when the underlying
# blocking call can't be interrupted immediately.
_running_tasks: dict[uuid.UUID, asyncio.Task] = {}
_cancel_requested: set[uuid.UUID] = set()


def _spawn(document_id: uuid.UUID) -> asyncio.Task[None]:
    task = asyncio.create_task(process_document(document_id))
    _background_tasks.add(task)
    _running_tasks[document_id] = task

    def _cleanup(_task: asyncio.Task) -> None:
        _background_tasks.discard(_task)
        _running_tasks.pop(document_id, None)
        _cancel_requested.discard(document_id)

    task.add_done_callback(_cleanup)
    return task


def request_cancel(document_id: uuid.UUID) -> bool:
    """Best-effort cancellation of a document currently being processed.

    Returns True if a task was found and asked to stop. The task may still
    be mid-way through a single blocking OCR/AI call that can't be
    interrupted immediately (Python can't force-kill a thread) - it will
    stop at the next cooperative checkpoint in _run_pipeline, bounded by the
    same PROCESS_TIMEOUT_SECONDS cap as any other hang. Callers that want the
    document's status to flip to cancelled immediately (rather than whenever
    the task next checks in) should update the row themselves too - see the
    cancel endpoint in app/api/documents.py.
    """
    task = _running_tasks.get(document_id)
    if task is None or task.done():
        return False
    _cancel_requested.add(document_id)
    task.cancel()
    return True


async def _mark_processing(document_id: uuid.UUID) -> tuple[bytes | None, str, str | None] | None:
    """Flips a document to PROCESSING and hands back just the plain values
    _run_pipeline needs - never a live ORM object - so this is the only
    database round-trip before the (potentially minutes-long) OCR/AI work
    begins. Returns None if the document no longer exists."""
    async with async_session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return None

        document.status = DocumentStatus.PROCESSING
        document.progress_percent = PROGRESS_QUEUED
        document.processing_started_at = datetime.now(UTC)
        await session.commit()

        return document.file_content, document.mime_type, document.ocr_text


async def _mark_done(document_id: uuid.UUID, analysis: ai.DocumentAnalysis) -> None:
    async with async_session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:  # deleted mid-processing
            return

        document.document_type = analysis.document_type
        document.document_number = analysis.document_number
        document.issuing_authority = analysis.issuing_authority
        document.issue_date = analysis.issue_date
        document.expiry_date = analysis.expiry_date
        document.detected_language = analysis.detected_language
        document.key_fields = {field.key: field.value for field in analysis.key_fields}
        document.summary_original = analysis.summary_original
        document.summary_english = analysis.summary_english
        document.progress_percent = PROGRESS_COMPLETE
        document.status = DocumentStatus.DONE
        await session.commit()


async def _mark_failed(document_id: uuid.UUID, message: str) -> None:
    async with async_session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:  # deleted mid-processing
            return
        document.status = DocumentStatus.ERROR
        document.error_message = message
        await session.commit()


async def process_document(document_id: uuid.UUID) -> None:
    try:
        started = await _mark_processing(document_id)
        if started is None:
            return
        file_content, mime_type, ocr_text = started

        await asyncio.wait_for(
            _run_pipeline(document_id, file_content, mime_type, ocr_text),
            timeout=PROCESS_TIMEOUT_SECONDS,
        )
    except asyncio.CancelledError:
        logger.info("Document processing cancelled for %s", document_id)
        await _mark_failed(document_id, CANCELLED_MESSAGE)
    except asyncio.TimeoutError:
        logger.error("Document processing timed out for %s", document_id)
        await _mark_failed(document_id, "Processing took too long. Please try uploading again.")
    except PipelineError as exc:
        logger.warning("Document processing failed for %s: %s", document_id, exc)
        await _mark_failed(document_id, str(exc))
    except Exception:  # noqa: BLE001 - pipeline boundary, persist any failure
        logger.exception("Document processing failed for %s", document_id)
        # The real exception is logged above for debugging - what reaches
        # the user should never repeat back internal details (a stray file
        # path, a library's raw error body, a raw DB error, ...).
        await _mark_failed(document_id, "Something went wrong while processing this document. Please try again.")


def _check_not_cancelled(document_id: uuid.UUID) -> None:
    # task.cancel() interrupts a pure-asyncio await (waiting on the OCR
    # semaphore, for instance) immediately, but Python can't force-kill a
    # thread - a cancellation that arrives while a to_thread() call is
    # actually running Tesseract or waiting on the AI provider has to wait
    # for that call to return before this checkpoint can raise on its behalf.
    if document_id in _cancel_requested:
        raise asyncio.CancelledError()


async def _run_pipeline(document_id: uuid.UUID, file_content: bytes | None, mime_type: str, ocr_text: str | None) -> None:
    # Both OCR and the AI call are synchronous, seconds-long-to-minutes-long
    # blocking calls. Awaiting them directly on the event loop froze the
    # WHOLE API (polls, logins, everything) for the duration of every
    # document - to_thread moves them off the loop so the server stays
    # responsive. Just as important: no database session is held open across
    # either call. A session checked out for the full processing cap, times
    # several documents processing at once, was enough to exhaust the
    # connection pool and hang unrelated requests (login, cancel, refresh) -
    # every database touch here is its own short-lived session instead.
    if ocr_text is None:
        if file_content is None:
            # Only possible for a document uploaded before file bytes moved
            # into the documents table (see the model + 0006 migration) -
            # its on-disk file is gone for good on a host with no
            # persistent disk. A clear, specific failure here beats letting
            # this reach OCR and blow up as an unhandled FileNotFoundError.
            raise PipelineError("This document's uploaded file is no longer available. Please re-upload it.")

        async with _ocr_slots:
            try:
                ocr_result = await asyncio.to_thread(ocr.run_ocr, file_content, mime_type)
            except Exception:
                # Distinct from the AI-analysis failure below on purpose: the
                # two used to collapse into one generic "something went
                # wrong" message, which made it impossible to tell - from the
                # user-visible result alone - which stage actually broke.
                # The real exception is still logged in full here; only the
                # user-facing text stays generic (never repeat back a raw
                # file path or library error to the browser).
                logger.exception("OCR failed for %s", document_id)
                raise PipelineError(
                    "We couldn't read this document. It may be corrupted, password-protected, "
                    "or in an unsupported format - please try a different file."
                ) from None

        _check_not_cancelled(document_id)

        ocr_text = ocr_result.text
        async with async_session_factory() as session:
            document = await session.get(Document, document_id)
            if document is None:  # deleted mid-processing
                return
            document.ocr_text = ocr_result.text
            document.ocr_confidence = ocr_result.confidence
            document.progress_percent = PROGRESS_OCR_DONE
            await session.commit()

    if not ocr_text.strip():
        raise PipelineError("No text could be extracted from this document")

    _check_not_cancelled(document_id)

    try:
        analysis = await asyncio.to_thread(ai.analyze_document_text, ocr_text)
    except Exception:
        logger.exception("AI analysis failed for %s", document_id)
        raise PipelineError(
            "We read this document but couldn't analyze it right now - this is usually "
            "temporary, please try again in a few minutes."
        ) from None

    _check_not_cancelled(document_id)

    await _mark_done(document_id, analysis)


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
