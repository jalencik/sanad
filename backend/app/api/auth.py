import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, UserPublic
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

ACCESS_TTL = timedelta(minutes=settings.access_token_expire_minutes)
REFRESH_TTL = timedelta(days=settings.refresh_token_expire_days)


def _set_auth_cookies(response: Response, user_id: uuid.UUID) -> None:
    access_token = create_token(user_id, "access", ACCESS_TTL)
    refresh_token = create_token(user_id, "refresh", REFRESH_TTL)

    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=int(ACCESS_TTL.total_seconds()),
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=int(REFRESH_TTL.total_seconds()),
        path="/api/auth",
    )


@router.post("/signup", response_model=UserPublic, status_code=201)
async def signup(payload: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    email = payload.email.lower()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(409, "An account with this email already exists")

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    _set_auth_cookies(response, user.id)
    return user


@router.post("/login", response_model=UserPublic)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    email = payload.email.lower()
    client_host = request.client.host if request.client else "unknown"
    check_rate_limit(f"{client_host}:{email}")

    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")

    _set_auth_cookies(response, user.id)
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/refresh", response_model=UserPublic)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Not authenticated")

    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Unexpected token type")
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(401, "Invalid or expired session") from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "User not found")

    _set_auth_cookies(response, user.id)
    return user
