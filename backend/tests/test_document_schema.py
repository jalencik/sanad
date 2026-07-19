import uuid
from datetime import datetime

from app.models.document import DocumentStatus
from app.schemas.document import DocumentSummary


def _summary(**overrides) -> DocumentSummary:
    defaults = dict(
        id=uuid.uuid4(),
        original_filename="a.png",
        mime_type="image/png",
        file_size=10,
        status=DocumentStatus.PROCESSING,
        progress_percent=10,
        document_type=None,
        document_number=None,
        detected_language=None,
        created_at=datetime(2026, 7, 19, 8, 0, 0),
        processing_started_at=datetime(2026, 7, 19, 8, 0, 0),
        estimated_completion_at=datetime(2026, 7, 19, 8, 0, 25),
    )
    defaults.update(overrides)
    return DocumentSummary.model_validate(defaults)


def test_naive_datetimes_are_serialized_with_an_explicit_utc_offset():
    # A naive datetime coming back from SQLite genuinely represents UTC (see
    # app/services/eta.py), but a bare ISO string with no offset gets
    # misread as *local* time by JavaScript's Date parser - for a user in
    # Tashkent (UTC+5) that's a 5-hour error on every processing estimate.
    summary = _summary()
    dumped = summary.model_dump(mode="json")

    assert dumped["created_at"].endswith("+00:00") or dumped["created_at"].endswith("Z")
    assert dumped["processing_started_at"].endswith("+00:00") or dumped["processing_started_at"].endswith("Z")
    assert dumped["estimated_completion_at"].endswith("+00:00") or dumped["estimated_completion_at"].endswith("Z")


def test_null_estimated_completion_stays_null():
    summary = _summary(estimated_completion_at=None)
    dumped = summary.model_dump(mode="json")
    assert dumped["estimated_completion_at"] is None
