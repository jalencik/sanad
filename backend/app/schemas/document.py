import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.document import DocumentStatus


def _tag_utc(value: datetime | None) -> datetime | None:
    # SQLite (tests/local dev) hands datetimes back naive, even for columns
    # written as UTC-aware - a naive value serialized straight to JSON has no
    # offset, and JavaScript's Date parser then reads it as *local* time
    # instead of UTC. Every datetime this API returns is genuinely UTC, so
    # tag it explicitly rather than let the client guess wrong.
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


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
    processing_started_at: datetime | None
    estimated_completion_at: datetime | None = None

    @field_validator("created_at", "processing_started_at", "estimated_completion_at", mode="after")
    @classmethod
    def _created_processing_eta_are_utc(cls, value: datetime | None) -> datetime | None:
        return _tag_utc(value)


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

    @field_validator("updated_at", mode="after")
    @classmethod
    def _updated_at_is_utc(cls, value: datetime) -> datetime:
        return _tag_utc(value)
