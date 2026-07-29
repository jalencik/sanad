import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api import admin, auth, documents, health
from app.core.config import get_settings
from app.services.pipeline import recover_stuck_documents

logging.basicConfig(level=logging.INFO)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Picks back up any document a previous process (redeploy, crash, free-tier
    # recycle) abandoned mid-flight - see docs/decisions/2026-07-19-pipeline-durability-and-key-rotation.md
    await recover_stuck_documents()
    yield


app = FastAPI(title="Sanad API", version="0.1.0", lifespan=lifespan)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """A handful of response headers that cost nothing and close off whole
    classes of browser-side attacks: nosniff stops a mislabeled upload from
    being MIME-sniffed into something executable, DENY stops this app being
    framed for clickjacking, and HSTS (once cookies are actually flowing
    over HTTPS) stops a downgrade to plain HTTP from ever being offered."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# request.client.host is what rate limiting keys off of (see
# app/services/rate_limit.py) - without any trusted-proxy config, it's
# always our own reverse proxy's address, meaning every real visitor shares
# one rate-limit bucket. trusted_hosts="*" would "fix" that but is actually
# worse: uvicorn then believes the FIRST (leftmost) X-Forwarded-For entry
# unconditionally, and nginx's $proxy_add_x_forwarded_for *appends* to
# whatever X-Forwarded-For a client already sent rather than replacing it -
# so a client can simply pre-set the header themselves and be believed,
# defeating login/signup throttling entirely. Only trust specific,
# known-proxy addresses (see TRUSTED_PROXY_HOSTS in .env.example) - the
# default below trusts nothing, which is the same safe-but-imprecise
# shared-bucket behavior as having no middleware at all.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.trusted_proxy_hosts)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(admin.router)
