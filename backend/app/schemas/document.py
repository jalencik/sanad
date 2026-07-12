import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size: int
    status: DocumentStatus
    progress_percent: int
    document_type: str | None
    document_number: str | None
    detected_language: str | None
    created_at: datetime


class DocumentDetail(DocumentSummary):
    error_message: str | None
    ocr_text: str | None
    ocr_confidence: float | None
    issuing_authority: str | None
    issue_date: str | None
    expiry_date: str | None
    key_fields: dict | None
    summary_original: str | None
    summary_english: str | None
    updated_at: datetime
