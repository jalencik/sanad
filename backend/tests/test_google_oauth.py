from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.user import User


def _configure_google(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "google_redirect_uri", "http://test/api/auth/google/callback")


async def test_google_login_disabled_when_not_configured(anon_client):
    response = await anon_client.get("/api/auth/google/login")
    assert response.status_code == 503


async def test_google_login_redirects_and_sets_state_cookie(anon_client, monkeypatch):
    _configure_google(monkeypatch)

    response = await anon_client.get("/api/auth/google/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]
    assert "oauth_state" in response.cookies


async def test_google_callback_rejects_missing_state(anon_client, monkeypatch):
    _configure_google(monkeypatch)

    response = await anon_client.get("/api/auth/google/callback?code=abc&state=mismatch")
    assert response.status_code == 400


async def test_google_callback_creates_new_user_and_logs_in(anon_client, monkeypatch):
    _configure_google(monkeypatch)

    login_response = await anon_client.get("/api/auth/google/login", follow_redirects=False)
    state = login_response.cookies["oauth_state"]

    with patch(
        "app.api.auth.google_oauth.exchange_code_for_userinfo",
        new=AsyncMock(return_value={"email": "New.Google.User@example.com", "name": "Google User"}),
    ):
        callback_response = await anon_client.get(
            f"/api/auth/google/callback?code=fake-code&state={state}", follow_redirects=False
        )

    assert callback_response.status_code in (302, 307)
    assert "access_token" in callback_response.cookies

    me = await anon_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "new.google.user@example.com"
    assert me.json()["full_name"] == "Google User"

    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "new.google.user@example.com"))
        assert user is not None


async def test_google_callback_logs_in_existing_user_without_duplicate(anon_client, monkeypatch):
    _configure_google(monkeypatch)

    await anon_client.post(
        "/api/auth/signup",
        json={"email": "existing@example.com", "password": "correct-horse-battery", "full_name": "Existing User"},
    )
    await anon_client.post("/api/auth/logout")

    login_response = await anon_client.get("/api/auth/google/login", follow_redirects=False)
    state = login_response.cookies["oauth_state"]

    with patch(
        "app.api.auth.google_oauth.exchange_code_for_userinfo",
        new=AsyncMock(return_value={"email": "existing@example.com", "name": "Existing User"}),
    ):
        await anon_client.get(f"/api/auth/google/callback?code=fake-code&state={state}", follow_redirects=False)

    async with async_session_factory() as session:
        result = await session.scalars(select(User).where(User.email == "existing@example.com"))
        assert len(result.all()) == 1
