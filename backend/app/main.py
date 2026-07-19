import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(admin.router)
