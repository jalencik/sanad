import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, UserPublic
from app.services import google_oauth
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

ACCESS_TTL = timedelta(minutes=settings.access_token_expire_minutes)
REFRESH_TTL = timedelta(days=settings.refresh_token_expire_days)

GOOGLE_STATE_COOKIE = "oauth_state"
GOOGLE_STATE_TTL_SECONDS = 600


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


def _is_admin_email(email: str) -> bool:
    return email in {e.lower() for e in settings.admin_emails}


@router.post("/signup", response_model=UserPublic, status_code=201)
async def signup(
    payload: SignupRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    client_host = request.client.host if request.client else "unknown"
    check_rate_limit(f"signup:{client_host}", message="Too many signup attempts. Try again in a few minutes.")

    email = payload.email.lower()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(409, "An account with this email already exists")

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_admin=_is_admin_email(email),
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

    # Re-sync admin status on every login so editing ADMIN_EMAILS takes
    # effect without needing to touch the database directly.
    should_be_admin = _is_admin_email(email)
    if user.is_admin != should_be_admin:
        user.is_admin = should_be_admin
        await db.commit()

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


@router.get("/google/login")
async def google_login(response: Response) -> RedirectResponse:
    if not settings.google_oauth_configured:
        raise HTTPException(503, "Google sign-in is not configured on this server")

    state = secrets.token_urlsafe(32)
    redirect = RedirectResponse(google_oauth.build_authorize_url(state))
    redirect.set_cookie(
        GOOGLE_STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=GOOGLE_STATE_TTL_SECONDS,
        path="/api/auth/google",
    )
    return redirect


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    if not settings.google_oauth_configured:
        raise HTTPException(503, "Google sign-in is not configured on this server")

    expected_state = request.cookies.get(GOOGLE_STATE_COOKIE)
    if not code or not state or not expected_state or state != expected_state:
        raise HTTPException(400, "Invalid or expired Google sign-in attempt. Please try again.")

    try:
        userinfo = await google_oauth.exchange_code_for_userinfo(code)
    except google_oauth.GoogleOAuthError as exc:
        raise HTTPException(401, "Google sign-in failed. Please try again.") from exc

    email = userinfo["email"].lower()
    user = await db.scalar(select(User).where(User.email == email))

    if user is None:
        user = User(
            email=email,
            # Google-authenticated accounts never use password login - this
            # hash is unreachable (verify_password requires the plaintext,
            # which nothing ever sends), it only satisfies the NOT NULL column.
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            full_name=userinfo.get("name") or email.split("@")[0],
            is_admin=_is_admin_email(email),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        should_be_admin = _is_admin_email(email)
        if user.is_admin != should_be_admin:
            user.is_admin = should_be_admin
            await db.commit()

    redirect = RedirectResponse("/app")
    redirect.delete_cookie(GOOGLE_STATE_COOKIE, path="/api/auth/google")
    _set_auth_cookies(redirect, user.id)
    return redirect
