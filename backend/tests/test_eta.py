import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.eta import estimate_completion, typical_processing_seconds


async def _create_test_user() -> uuid.UUID:
    async with async_session_factory() as session:
        user = User(
            email=f"{uuid.uuid4()}@example.com",
            hashed_password=hash_password("correct-horse-battery"),
            full_name="ETA Test User",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def test_typical_processing_seconds_returns_none_when_no_history():
    async with async_session_factory() as session:
        result = await typical_processing_seconds(session)
    assert result is None


async def test_typical_processing_seconds_averages_recent_completed_durations():
    user_id = await _create_test_user()
    now = datetime.now(UTC)

    async with async_session_factory() as session:
        for duration_seconds in (10.0, 20.0, 30.0):
            started = now - timedelta(seconds=duration_seconds)
            document = Document(
                user_id=user_id,
                original_filename="d.png",
                stored_filename=f"{uuid.uuid4()}.png",
                mime_type="image/png",
                file_size=10,
                status=DocumentStatus.DONE,
                processing_started_at=started,
                updated_at=now,
            )
            session.add(document)
        await session.commit()

    async with async_session_factory() as session:
        result = await typical_processing_seconds(session)

    assert result == pytest.approx(20.0, abs=0.5)


async def test_typical_processing_seconds_ignores_documents_never_processed():
    user_id = await _create_test_user()

    async with async_session_factory() as session:
        document = Document(
            user_id=user_id,
            original_filename="d.png",
            stored_filename=f"{uuid.uuid4()}.png",
            mime_type="image/png",
            file_size=10,
            status=DocumentStatus.DONE,
            processing_started_at=None,
        )
        session.add(document)
        await session.commit()

    async with async_session_factory() as session:
        result = await typical_processing_seconds(session)

    assert result is None


def test_estimate_completion_returns_none_when_not_processing():
    document = Document(status=DocumentStatus.DONE, processing_started_at=datetime.now(UTC))
    assert estimate_completion(document, typical_seconds=10.0) is None


def test_estimate_completion_returns_none_when_no_history_yet():
    document = Document(status=DocumentStatus.PROCESSING, processing_started_at=datetime.now(UTC))
    assert estimate_completion(document, typical_seconds=None) is None


def test_estimate_completion_adds_typical_seconds_to_start_time():
    started = datetime.now(UTC)
    document = Document(status=DocumentStatus.PROCESSING, processing_started_at=started)

    result = estimate_completion(document, typical_seconds=42.0)

    assert result == started + timedelta(seconds=42.0)
