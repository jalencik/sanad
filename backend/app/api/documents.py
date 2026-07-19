import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
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
from app.services.pipeline import process_document
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

    stored_filename, size = await storage.save_upload(file)

    if size > settings.max_upload_size_mb * 1024 * 1024:
        storage.resolve_path(stored_filename).unlink(missing_ok=True)
        raise HTTPException(413, f"File exceeds {settings.max_upload_size_mb}MB limit")

    document = Document(
        user_id=current_user.id,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        mime_type=file.content_type,
        file_size=size,
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


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    document = await _get_owned_document(document_id, current_user, db)

    path = storage.resolve_path(document.stored_filename)
    if not path.exists():
        raise HTTPException(404, "File missing on disk")

    return FileResponse(path, media_type=document.mime_type, filename=document.original_filename)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    document = await _get_owned_document(document_id, current_user, db)

    storage.resolve_path(document.stored_filename).unlink(missing_ok=True)
    await db.delete(document)
    await db.commit()
