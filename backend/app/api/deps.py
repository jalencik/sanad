import uuid

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(401, "Not authenticated")

    try:
        payload = decode_token(access_token)
        if payload.get("type") != "access":
            raise ValueError("Unexpected token type")
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(401, "Invalid or expired session") from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "User not found")

    return user
