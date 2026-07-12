import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_sanad.db")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("UPLOAD_DIR", "./test_uploads")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long-for-hs256")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import rate_limit  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _prepare_database():
    # The rate limiter's attempt counts live in a module-level dict, not the
    # DB, so they survive across tests unless cleared here too - otherwise
    # tests sharing a rate-limit key (e.g. the ASGI test client has no real
    # peer IP, so every signup call collides on "signup:unknown") trip each
    # other's limits depending on run order.
    rate_limit.reset()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def anon_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client(anon_client: AsyncClient):
    await anon_client.post(
        "/api/auth/signup",
        json={"email": "test.user@example.com", "password": "correct-horse-battery", "full_name": "Test User"},
    )
    yield anon_client
