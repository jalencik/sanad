import re
import uuid
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.schemas.document import DocumentDetail, DocumentSummary
from app.services import storage
from app.services.eta import estimate_completion, typical_processing_seconds
from app.services.pipeline import CANCELLED_MESSAGE, process_document, request_cancel
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()

# Each upload triggers a real OCR pass plus a billed/quota-metered Gemini API
# call, so this route needs its own (looser than login's) cap - protects the
# free-tier quota and server CPU from a runaway client without blocking
# normal interactive use.
UPLOAD_MAX_ATTEMPTS = 20
UPLOAD_WINDOW_SECONDS = 300.0


async def _get_owned_document(document_id: uuid.UUID, user: User, db: AsyncSession) -> Document:
    document = await db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(404, "Document not found")
    return document


async def _attach_eta(documents: list[Document], db: AsyncSession) -> list[Document]:
    # One history lookup covers every processing document in this response -
    # no need to repeat it per row.
    if not any(doc.status == DocumentStatus.PROCESSING for doc in documents):
        return documents
    typical_seconds = await typical_processing_seconds(db)
    for document in documents:
        document.estimated_completion_at = estimate_completion(document, typical_seconds)
    return documents


@router.post("", response_model=DocumentDetail, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    check_rate_limit(
        f"upload:{current_user.id}",
        max_attempts=UPLOAD_MAX_ATTEMPTS,
        window_seconds=UPLOAD_WINDOW_SECONDS,
        message="Too many uploads. Please wait a few minutes and try again.",
    )

    if file.content_type not in settings.allowed_mime_types:
        raise HTTPException(415, f"Unsupported file type: {file.content_type}")

    try:
        content = await storage.save_upload(file, file.content_type, settings.max_upload_size_mb * 1024 * 1024)
    except storage.UploadTooLarge as exc:
        raise HTTPException(413, f"File exceeds {settings.max_upload_size_mb}MB limit") from exc
    except storage.UploadContentMismatch as exc:
        raise HTTPException(415, "This file's content doesn't match its declared type") from exc

    document = Document(
        user_id=current_user.id,
        original_filename=file.filename or "document",
        file_content=content,
        mime_type=file.content_type,
        file_size=len(content),
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    background_tasks.add_task(process_document, document.id)

    return document


@router.get("", response_model=list[DocumentSummary])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Document]:
    # Paginated so the sidebar (and its 2-second poll while documents are
    # processing) never drags the user's full history over the wire - only
    # the most recent page.
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return await _attach_eta(list(result.scalars().all()), db)


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    document = await _get_owned_document(document_id, current_user, db)
    await _attach_eta([document], db)
    return document


def _content_disposition(filename: str) -> str:
    # filename is the client-supplied original filename - safe to put in a
    # header's UTF-8-encoded form (RFC 5987/6266), but never interpolated
    # raw: an unescaped quote or CRLF in it could break out of the
    # filename="..." param or inject a second header. The plain ASCII
    # fallback (for clients that ignore filename*) gets the same treatment,
    # stripped down to characters that can't do either.
    ascii_fallback = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "document"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    document = await _get_owned_document(document_id, current_user, db)

    if document.file_content is None:
        # Either uploaded before file bytes moved into the documents table
        # (see the model + 0006 migration), or - now unreachable in normal
        # operation - some other gap. Either way there's no file to serve.
        raise HTTPException(404, "This document's file is no longer available. Please re-upload it.")

    # mime_type is stored from the upload's declared Content-Type, which is
    # client-controlled - forcing a download (rather than letting a browser
    # render it inline) means a mislabeled file can't turn into an
    # in-browser script/HTML execution risk merely by opening this link.
    return Response(
        content=document.file_content,
        media_type=document.mime_type,
        headers={"Content-Disposition": _content_disposition(document.original_filename)},
    )


@router.post("/{document_id}/cancel", response_model=DocumentDetail)
async def cancel_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Document:
    document = await _get_owned_document(document_id, current_user, db)

    if document.status not in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        raise HTTPException(409, "This document isn't currently processing")

    # Update the row directly rather than waiting for the background task to
    # notice - the task may be mid-way through a blocking OCR/AI call it
    # can't be interrupted out of immediately (see pipeline.request_cancel),
    # so this is what makes cancellation feel instant to the user.
    document.status = DocumentStatus.ERROR
    document.error_message = CANCELLED_MESSAGE
    await db.commit()
    await db.refresh(document)

    request_cancel(document.id)

    return document


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    document = await _get_owned_document(document_id, current_user, db)

    # file_content lives on the row itself now - deleting it deletes the
    # file, no separate disk cleanup needed.
    await db.delete(document)
    await db.commit()
