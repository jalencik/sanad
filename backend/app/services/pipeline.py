import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.services import ai, ocr

logger = logging.getLogger(__name__)
settings = get_settings()

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


# Bounds how many documents can be actively in flight through _run_pipeline
# at once - not just during OCR. Without this, nothing stops every document
# recover_stuck_documents() resumes on startup from running at once: a
# document that already has OCR text skips _ocr_slots entirely and loads its
# full original file straight into memory for the analysis step, so a
# restart with several stuck documents loads all of their files in parallel,
# with no limit. On a memory-constrained host, that burst is enough to OOM
# the process again right after it restarts - which restarts it again,
# straight into the same burst. Kept as its own, separate semaphore from
# _ocr_slots (which still exists to keep the CPU-heavy rendering/Tesseract
# step serialized) so a document waiting on the AI provider doesn't need to
# fully block another's OCR - this only caps the total number resident at
# once. Sourced from settings (PIPELINE_CONCURRENCY) rather than hardcoded -
# see Settings.pipeline_concurrency - so this can be tightened with a
# restart, not a code deploy, if the default isn't safe on a given host's
# actual memory budget.
_PIPELINE_CONCURRENCY = settings.pipeline_concurrency
_pipeline_slots = asyncio.Semaphore(_PIPELINE_CONCURRENCY)


def reset_ocr_slots() -> None:
    """Rebind the OCR and pipeline permits to the current event loop.

    Test isolation only - never called in app code, which runs one long-lived
    loop. asyncio.Semaphore binds itself to a loop the first time a caller
    actually has to *wait* on it, and every test gets a fresh loop, so without
    this the first test that makes two documents contend leaves the permit
    bound to a loop that no later test still has.
    """
    global _ocr_slots, _pipeline_slots
    _ocr_slots = asyncio.Semaphore(1)
    _pipeline_slots = asyncio.Semaphore(_PIPELINE_CONCURRENCY)

# A stage should never legitimately take longer than its budget here. Without
# a cap, a hung OCR call or a stalled network connection to the AI provider
# holds its thread (and the user's progress bar) forever - these turn a silent
# freeze into an honest, visible failure the user can just retry.
#
# These are per-stage rather than one whole-document cap, because a single cap
# had to start counting before the document could reach _ocr_slots: with one
# permit, a document queued behind another spent its budget waiting rather
# than working, so a burst of uploads made later documents fail a "timeout"
# they never got a chance at (and skewed their ETA by the same amount). Each
# budget below starts only once that stage actually holds what it needs, so
# queue time is unbounded but uncounted - waiting isn't a failure.
#
# The individual numbers stay honest about the pipeline's own worst case, or
# they fire on a document that was never stuck: OCR can legitimately take
# max_pdf_pages * _PAGE_TIMEOUT_SECONDS (app/services/ocr.py) = 8 * 90s = 720s
# today, and the AI call can retry across every configured Groq/Gemini key
# (app/services/ai.py) before giving up. Together these still sum to the same
# 1140s ceiling a single document faced before.
OCR_TIMEOUT_SECONDS = 780
ANALYSIS_TIMEOUT_SECONDS = 360

CANCELLED_MESSAGE = "Cancelled."

# How many times recover_stuck_documents() will resume the same document
# across separate restarts before giving up on it. Without this cap, a
# document that reliably crashes the whole process while being worked on -
# for any reason, not necessarily memory - gets retried by every single
# restart forever: crash, restart, resume the same poison-pill document,
# crash again. A cap this low means real, temporary blips (a network hiccup
# talking to the AI provider, one bad restart) still get retried, while a
# document that's genuinely fatal to process stops taking the whole service
# down with it within a few restarts instead of indefinitely.
MAX_RECOVERY_ATTEMPTS = 3


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


async def _needs_ocr(document_id: uuid.UUID) -> bool | None:
    """Whether this document still needs OCR, or None if it no longer exists.

    Deliberately selects the single column instead of loading the row: the
    documents table now carries the uploaded file itself (file_content), and
    pulling those bytes just to answer a yes/no question would hold a whole
    PDF in memory per queued document, before any of them has started work.
    """
    async with async_session_factory() as session:
        result = await session.execute(select(Document.ocr_text).where(Document.id == document_id))
        row = result.first()
        if row is None:
            return None
        return row[0] is None


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


async def _mark_processing_for_analysis(document_id: uuid.UUID) -> str | None:
    """Same status/progress/timestamp bookkeeping as _mark_processing, for a
    resumed document that already has OCR text and is going straight to
    analysis. Returns only ocr_text - not file_content/mime_type, which this
    path never uses - so the caller's stack frame never ends up holding a
    reference to the document's full original file for the whole AI call.
    Returns None if the document no longer exists."""
    async with async_session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return None

        document.status = DocumentStatus.PROCESSING
        document.progress_percent = PROGRESS_QUEUED
        document.processing_started_at = datetime.now(UTC)
        await session.commit()

        return document.ocr_text


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
        # Read first, mark second: _run_pipeline only flips the row to
        # PROCESSING (and starts both the ETA and the timeout clock) once it
        # holds the OCR permit, so a document waiting its turn keeps showing
        # the "queued" state it is genuinely in.
        needs_ocr = await _needs_ocr(document_id)
        if needs_ocr is None:  # deleted before processing began
            return

        await _run_pipeline(document_id, needs_ocr)
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


async def _run_pipeline(document_id: uuid.UUID, needs_ocr: bool) -> None:
    # Both OCR and the AI call are synchronous, seconds-long-to-minutes-long
    # blocking calls. Awaiting them directly on the event loop froze the
    # WHOLE API (polls, logins, everything) for the duration of every
    # document - to_thread moves them off the loop so the server stays
    # responsive. Just as important: no database session is held open across
    # either call. A session checked out for the full processing cap, times
    # several documents processing at once, was enough to exhaust the
    # connection pool and hang unrelated requests (login, cancel, refresh) -
    # every database touch here is its own short-lived session instead.
    #
    # Each stage's timeout starts *inside* whatever it had to wait for, never
    # around it: the permit below is acquired before any clock runs, so time
    # spent queued behind another document is unbounded but never counted
    # against this one. The permit is also released as soon as OCR is done
    # rather than being held through analysis, so a document waiting on the AI
    # provider's network round-trips doesn't block another document's OCR.
    #
    # _pipeline_slots wraps the entire function, before either branch below:
    # it's the one thing bounding how many documents - queued via a normal
    # upload burst, or all resumed at once by recover_stuck_documents() on
    # restart - can be holding their full file bytes in memory at the same
    # time. _ocr_slots is a second, tighter cap nested inside it, just for
    # the CPU-bound rendering step.
    async with _pipeline_slots:
        ocr_text: str | None = None

        if needs_ocr:
            async with _ocr_slots:
                # Marked only now that this document can genuinely make
                # progress - this is what sets processing_started_at, which
                # drives both the user's ETA and the "Analyzing" state,
                # neither of which should start ticking while it was still
                # queued (behind _pipeline_slots or _ocr_slots).
                _check_not_cancelled(document_id)
                started = await _mark_processing(document_id)
                if started is None:  # deleted while queued
                    return
                file_content, mime_type, ocr_text = started

                if file_content is None:
                    # Only possible for a document uploaded before file bytes
                    # moved into the documents table (see the model + 0006
                    # migration) - its on-disk file is gone for good on a host
                    # with no persistent disk. A clear, specific failure here
                    # beats letting this reach OCR and blow up as an
                    # unhandled FileNotFoundError.
                    raise PipelineError(
                        "This document's uploaded file is no longer available. Please re-upload it."
                    )

                try:
                    ocr_result = await asyncio.wait_for(
                        asyncio.to_thread(ocr.run_ocr, file_content, mime_type),
                        timeout=OCR_TIMEOUT_SECONDS,
                    )
                except ocr.PasswordProtectedError:
                    # Checked and known for certain (see ocr._iter_pdf_pages),
                    # not a guess bundled in with "or who knows what else" - a
                    # user who sees this can actually act on it immediately.
                    logger.info("Document %s is password-protected", document_id)
                    raise PipelineError(
                        "This PDF is password-protected. Please remove the password and upload again."
                    ) from None
                except ocr.PageTooLargeError:
                    # The file is intact - it just declares a page too large
                    # to rasterize without putting the whole instance at risk
                    # (see ocr._safe_pixmap). Saying "corrupted" here would
                    # send the user off fixing a file that isn't broken.
                    logger.warning("Document %s has an unrenderably large page", document_id)
                    raise PipelineError(
                        "One of this document's pages is too large for us to process. Please try "
                        "a version with smaller page dimensions."
                    ) from None
                except ocr.OcrTimeoutError:
                    # Tesseract itself reported the timeout (see
                    # ocr.OcrTimeoutError) - a genuinely too-big-or-complex
                    # document, not corruption, so it gets its own honest
                    # message instead of the generic OCR-failure guess below.
                    logger.info("OCR timed out for %s", document_id)
                    raise PipelineError(
                        "This document is too large or complex for our current server limits to "
                        "process in time. Please try extracting text from a smaller file or a "
                        "direct image."
                    ) from None
                except asyncio.TimeoutError:
                    # Our OCR_TIMEOUT_SECONDS cap, not Tesseract's own
                    # per-page one. Re-raised untouched so process_document
                    # maps it to the honest "took too long" message -
                    # asyncio.TimeoutError is a plain Exception subclass, so
                    # without this it would be swallowed by the generic OCR
                    # handler below and reported as an unreadable file
                    # instead.
                    raise
                except Exception:
                    # Distinct from the AI-analysis failure below on purpose:
                    # the two used to collapse into one generic "something
                    # went wrong" message, which made it impossible to tell -
                    # from the user-visible result alone - which stage
                    # actually broke. The real exception is still logged in
                    # full here; only the user-facing text stays generic
                    # (never repeat back a raw file path or library error to
                    # the browser).
                    logger.exception("OCR failed for %s", document_id)
                    raise PipelineError(
                        "We couldn't read this document. It may be corrupted or in an unsupported "
                        "format - please try a different file."
                    ) from None
                finally:
                    # The rendered page bitmap is already gone once run_ocr
                    # returns, but the ORIGINAL FILE BYTES (up to
                    # max_upload_size_mb) are still referenced by this local
                    # variable, and this frame stays alive through the AI
                    # call below - dropping the reference here, the moment
                    # OCR is done with it, is what actually frees that
                    # memory rather than just leaving it dead weight for
                    # however long the AI provider call takes.
                    file_content = None

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
        else:
            # A resumed document that already has OCR text goes straight to
            # analysis, so it never competes for an OCR permit it doesn't
            # need - queueing it behind documents that do would delay it for
            # nothing. _mark_processing_for_analysis (unlike _mark_processing)
            # never loads this document's file bytes at all, since this path
            # has no use for them.
            # None only ever means "deleted while queued" here: this branch
            # only runs when needs_ocr was already False, i.e. ocr_text was
            # confirmed non-null moments ago in process_document, and nothing
            # in this pipeline ever clears it back to null once set.
            ocr_text = await _mark_processing_for_analysis(document_id)
            if ocr_text is None:
                return

        if ocr_text is None or not ocr_text.strip():
            raise PipelineError("No text could be extracted from this document")

        _check_not_cancelled(document_id)

        try:
            analysis = await asyncio.wait_for(
                asyncio.to_thread(ai.analyze_document_text, ocr_text),
                timeout=ANALYSIS_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            # Same reasoning as the OCR stage: let process_document report
            # this as a timeout rather than as an analysis failure.
            raise
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
    every one of these was abandoned and pick it back up.

    A document already at MAX_RECOVERY_ATTEMPTS is the exception: it gets
    marked failed here instead of resumed again. recovery_attempts and this
    decision both live in the same transaction as everything else read here,
    and _spawn() is only ever called after that transaction has committed
    and the session has closed - matching the ordering this function already
    relied on before recovery_attempts existed, so a freshly spawned task's
    own (separate) session is never racing this one's writes.
    """
    to_resume: list[uuid.UUID] = []

    async with async_session_factory() as session:
        result = await session.execute(
            select(Document).where(Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING]))
        )

        for document in result.scalars().all():
            if document.recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
                logger.error(
                    "Document %s failed to complete after %d recovery attempts - giving up",
                    document.id,
                    document.recovery_attempts,
                )
                document.status = DocumentStatus.ERROR
                document.error_message = (
                    "This document couldn't be processed after several attempts. Please try re-uploading it."
                )
                continue

            document.recovery_attempts += 1
            to_resume.append(document.id)

        await session.commit()

    if to_resume:
        logger.info("Resuming %d document(s) left mid-processing by a previous run", len(to_resume))

    return [_spawn(document_id) for document_id in to_resume]
