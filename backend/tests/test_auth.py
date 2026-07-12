async def test_signup_creates_account_and_session(anon_client):
    response = await anon_client.post(
        "/api/auth/signup",
        json={"email": "New.User@Example.com", "password": "correct-horse-battery", "full_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"
    assert "access_token" in response.cookies

    me = await anon_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["full_name"] == "New User"


async def test_signup_rejects_duplicate_email(anon_client):
    payload = {"email": "dup@example.com", "password": "correct-horse-battery", "full_name": "Dup"}
    first = await anon_client.post("/api/auth/signup", json=payload)
    assert first.status_code == 201

    second = await anon_client.post("/api/auth/signup", json=payload)
    assert second.status_code == 409


async def test_signup_rejects_short_password(anon_client):
    response = await anon_client.post(
        "/api/auth/signup",
        json={"email": "short@example.com", "password": "short", "full_name": "Short"},
    )
    assert response.status_code == 422


async def test_login_with_correct_credentials(anon_client):
    await anon_client.post(
        "/api/auth/signup",
        json={"email": "login@example.com", "password": "correct-horse-battery", "full_name": "Login User"},
    )
    await anon_client.post("/api/auth/logout")

    response = await anon_client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "correct-horse-battery"}
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies


async def test_login_with_wrong_password_fails(anon_client):
    await anon_client.post(
        "/api/auth/signup",
        json={"email": "wrongpass@example.com", "password": "correct-horse-battery", "full_name": "User"},
    )
    response = await anon_client.post(
        "/api/auth/login", json={"email": "wrongpass@example.com", "password": "not-the-password"}
    )
    assert response.status_code == 401


async def test_signup_rate_limited_after_repeated_attempts(anon_client):
    for i in range(5):
        response = await anon_client.post(
            "/api/auth/signup",
            json={"email": f"limit{i}@example.com", "password": "correct-horse-battery", "full_name": "User"},
        )
        assert response.status_code == 201

    response = await anon_client.post(
        "/api/auth/signup",
        json={"email": "limit-extra@example.com", "password": "correct-horse-battery", "full_name": "User"},
    )
    assert response.status_code == 429


async def test_me_requires_authentication(anon_client):
    response = await anon_client.get("/api/auth/me")
    assert response.status_code == 401


async def test_logout_clears_session(client):
    await client.post("/api/auth/logout")
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_documents_require_authentication(anon_client):
    response = await anon_client.get("/api/documents")
    assert response.status_code == 401


async def test_documents_are_scoped_per_user(anon_client):
    from unittest.mock import AsyncMock, patch

    await anon_client.post(
        "/api/auth/signup",
        json={"email": "owner@example.com", "password": "correct-horse-battery", "full_name": "Owner"},
    )
    with patch("app.api.documents.process_document", new=AsyncMock()):
        upload = await anon_client.post(
            "/api/documents",
            files={"file": ("scan.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    await anon_client.post("/api/auth/logout")

    await anon_client.post(
        "/api/auth/signup",
        json={"email": "intruder@example.com", "password": "correct-horse-battery", "full_name": "Intruder"},
    )
    other_view = await anon_client.get(f"/api/documents/{document_id}")
    assert other_view.status_code == 404

    other_list = await anon_client.get("/api/documents")
    assert other_list.json() == []
