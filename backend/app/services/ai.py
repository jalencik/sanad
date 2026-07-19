from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.gemini_pool import GeminiKeyPool

settings = get_settings()

_pool: GeminiKeyPool | None = None


def _get_pool() -> GeminiKeyPool:
    global _pool
    if _pool is None:
        _pool = GeminiKeyPool(settings.gemini_keys)
    return _pool


class KeyField(BaseModel):
    key: str
    value: str


class DocumentAnalysis(BaseModel):
    document_type: str = Field(
        description=(
            "Best guess at the document category, e.g. passport, birth_certificate, "
            "contract, invoice, diploma, land_deed, court_order, other."
        )
    )
    document_number: str | None = None
    issuing_authority: str | None = None
    issue_date: str | None = Field(
        default=None, description="ISO 8601 date if determinable, else the raw text found."
    )
    expiry_date: str | None = None
    detected_language: str = Field(
        description="Primary language of the document, as an English word, e.g. Uzbek, Russian, English."
    )
    key_fields: list[KeyField] = Field(
        default_factory=list,
        description="Other notable extracted fields as flat key-value string pairs (e.g. full_name).",
    )
    summary_original: str = Field(
        description=(
            "A concise 2-4 sentence plain-language summary of the document's main point, "
            "written in the document's own detected language."
        )
    )
    summary_english: str = Field(
        description=(
            "The same summary translated into English. If the document is already in "
            "English, repeat it here."
        )
    )


def analyze_document_text(ocr_text: str) -> DocumentAnalysis:
    prompt = (
        "The following text was extracted via OCR from an official document and may "
        "contain recognition errors. Analyze it and return your best-effort structured "
        "findings. If a field cannot be determined, use null.\n\n"
        f"--- OCR TEXT START ---\n{ocr_text}\n--- OCR TEXT END ---"
    )

    def _call(client: genai.Client):
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DocumentAnalysis,
            ),
        )

    response = _get_pool().call(_call)

    if response.parsed is None:
        raise RuntimeError("Gemini did not return a structured response")

    return response.parsed
