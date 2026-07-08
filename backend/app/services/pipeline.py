import logging
import uuid

from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.services import ai, ocr, storage

logger = logging.getLogger(__name__)


async def process_document(document_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        await session.commit()

        try:
            path = storage.resolve_path(document.stored_filename)
            ocr_result = ocr.run_ocr(path, document.mime_type)

            document.ocr_text = ocr_result.text
            document.ocr_confidence = ocr_result.confidence

            if not ocr_result.text.strip():
                raise ValueError("No text could be extracted from this document")

            analysis = ai.analyze_document_text(ocr_result.text)

            document.document_type = analysis.document_type
            document.document_number = analysis.document_number
            document.issuing_authority = analysis.issuing_authority
            document.issue_date = analysis.issue_date
            document.expiry_date = analysis.expiry_date
            document.detected_language = analysis.detected_language
            document.key_fields = analysis.key_fields
            document.summary_original = analysis.summary_original
            document.summary_english = analysis.summary_english
            document.status = DocumentStatus.DONE

        except Exception as exc:  # noqa: BLE001 - pipeline boundary, persist any failure
            logger.exception("Document processing failed for %s", document_id)
            document.status = DocumentStatus.ERROR
            document.error_message = str(exc)

        await session.commit()
