from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.models.user import User


async def _make_admin(email: str) -> None:
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        user.is_admin = True
        await session.commit()


async def test_admin_users_requires_admin(client):
    response = await client.get("/api/admin/users")
    assert response.status_code == 403


async def test_admin_users_requires_authentication(anon_client):
    response = await anon_client.get("/api/admin/users")
    assert response.status_code == 401


async def test_admin_users_returns_all_users_with_document_counts(anon_client):
    await anon_client.post(
        "/api/auth/signup",
        json={"email": "admin@example.com", "password": "correct-horse-battery", "full_name": "Admin User"},
    )
    await _make_admin("admin@example.com")

    async with async_session_factory() as session:
        admin_user = await session.scalar(select(User).where(User.email == "admin@example.com"))
        session.add_all(
            [
                Document(
                    user_id=admin_user.id,
                    original_filename="a.png",
                    stored_filename="stored-a.png",
                    mime_type="image/png",
                    file_size=10,
                    status=DocumentStatus.DONE,
                ),
                Document(
                    user_id=admin_user.id,
                    original_filename="b.png",
                    stored_filename="stored-b.png",
                    mime_type="image/png",
                    file_size=10,
                    status=DocumentStatus.ERROR,
                ),
            ]
        )
        await session.commit()

    response = await anon_client.get("/api/admin/users")
    assert response.status_code == 200

    body = response.json()
    admin_row = next(u for u in body if u["email"] == "admin@example.com")
    assert admin_row["is_admin"] is True
    assert admin_row["document_count"] == 2
    assert admin_row["done_count"] == 1
    assert admin_row["error_count"] == 1
