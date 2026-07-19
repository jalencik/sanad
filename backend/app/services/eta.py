from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus

# How many recent completions to average. Recent-only (not all-time) so the
# estimate tracks the host's current real performance rather than a stale
# blend from whenever the app was slower or faster.
_HISTORY_SAMPLE_SIZE = 20


def _strip_tz(value: datetime) -> datetime:
    # SQLite (tests/local dev) and Postgres (production) don't round-trip
    # timezone-awareness the same way - normalize before subtracting so this
    # never raises "can't subtract offset-naive and offset-aware datetimes".
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


async def typical_processing_seconds(session: AsyncSession) -> float | None:
    """Average real duration of the last N completed documents, this
    server's own actual track record. None until at least one document has
    ever finished - there is nothing genuine to show before that, so the UI
    just doesn't display an estimate yet rather than inventing one."""
    result = await session.execute(
        select(Document.processing_started_at, Document.updated_at)
        .where(Document.status == DocumentStatus.DONE, Document.processing_started_at.isnot(None))
        .order_by(Document.updated_at.desc())
        .limit(_HISTORY_SAMPLE_SIZE)
    )
    rows = result.all()

    durations = [
        (_strip_tz(updated_at) - _strip_tz(started_at)).total_seconds()
        for started_at, updated_at in rows
        if started_at is not None and updated_at > started_at
    ]
    if not durations:
        return None
    return sum(durations) / len(durations)


def estimate_completion(document: Document, typical_seconds: float | None) -> datetime | None:
    """Projected completion time for a document currently being processed.
    None while not actively processing, or while there's no real history to
    base a number on yet."""
    if document.status != DocumentStatus.PROCESSING or document.processing_started_at is None:
        return None
    if typical_seconds is None:
        return None
    return document.processing_started_at + timedelta(seconds=typical_seconds)
