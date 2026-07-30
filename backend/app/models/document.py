import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, LargeBinary, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    # The uploaded bytes themselves, not a path - Render's free tier (and
    # most free container hosts) gives the app no persistent disk, so a
    # redeploy, crash, or plain scale-to-zero wipes anything written to the
    # filesystem. Storing the file in Postgres instead means it survives
    # exactly as long as the row does. Nullable only because it can't be
    # backfilled for documents uploaded before this column existed - their
    # on-disk file is already long gone; see the None-handling in
    # app/services/pipeline.py and the file-download route.
    file_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda e: [m.value for m in e]),
        default=DocumentStatus.PENDING,
    )
    # Reflects real pipeline stages (queued/OCR done/analysis done/stored),
    # not a time-based animation - see PROGRESS_* constants in pipeline.py.
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Set once when processing actually begins (including on resume after a
    # restart) - lets the ETA estimate answer "how long has this really been
    # running", independent of progress_percent's coarse checkpoints.
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(50), nullable=True)

    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expiry_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    key_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    summary_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_english: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
