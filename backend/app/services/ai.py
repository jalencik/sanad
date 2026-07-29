import json
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.gemini_pool import GeminiKeyPool
from app.services.groq_pool import GroqKeyPool, chat_completion_json

logger = logging.getLogger(__name__)

settings = get_settings()

_gemini_pool: GeminiKeyPool | None = None
_groq_pool: GroqKeyPool | None = None


def _get_gemini_pool() -> GeminiKeyPool:
    global _gemini_pool
    if _gemini_pool is None:
        _gemini_pool = GeminiKeyPool(settings.gemini_keys)
    return _gemini_pool


def _get_groq_pool() -> GroqKeyPool:
    global _groq_pool
    if _groq_pool is None:
        _groq_pool = GroqKeyPool(settings.groq_keys)
    return _groq_pool


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


_PROMPT = (
    "The following text was extracted via OCR from an official document and may "
    "contain recognition errors. Analyze it and return your best-effort structured "
    "findings. If a field cannot be determined, use null.\n\n"
    "--- OCR TEXT START ---\n{ocr_text}\n--- OCR TEXT END ---"
)

# Groq's JSON mode guarantees syntactically valid JSON but not a specific
# shape, unlike Gemini's native response_schema - spelling the schema out in
# the prompt itself is what keeps its output aligned with DocumentAnalysis.
_GROQ_PROMPT = _PROMPT + (
    "\n\nRespond with ONLY a single JSON object matching exactly this JSON schema "
    "(use null for any field you can't determine):\n{schema}"
)


def _analyze_with_gemini(ocr_text: str) -> DocumentAnalysis:
    prompt = _PROMPT.format(ocr_text=ocr_text)

    def _call(client: genai.Client):
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DocumentAnalysis,
            ),
        )

    response = _get_gemini_pool().call(_call)

    if response.parsed is None:
        raise RuntimeError("Gemini did not return a structured response")

    return response.parsed


def _analyze_with_groq(ocr_text: str) -> DocumentAnalysis:
    schema = json.dumps(DocumentAnalysis.model_json_schema())
    prompt = _GROQ_PROMPT.format(ocr_text=ocr_text, schema=schema)

    def _call(api_key: str) -> DocumentAnalysis:
        data = chat_completion_json(api_key, model=settings.groq_model, prompt=prompt)
        return DocumentAnalysis.model_validate(data)

    return _get_groq_pool().call(_call)


def analyze_document_text(ocr_text: str) -> DocumentAnalysis:
    """Runs structured extraction over OCR'd text via whichever provider
    app.core.config.Settings.resolved_ai_provider selects.

    When Groq is the resolved provider and Gemini is *also* configured,
    a Groq failure (every key rate-limited, an outage, ...) falls back to
    Gemini instead of failing the document outright - the same "don't let
    one provider's bad day take the pipeline down" reasoning that motivated
    Gemini's own multi-key rotation in the first place.
    """
    if settings.resolved_ai_provider == "groq":
        try:
            return _analyze_with_groq(ocr_text)
        except Exception:
            if not settings.gemini_keys:
                raise
            logger.warning("Groq analysis failed on every key, falling back to Gemini", exc_info=True)
            return _analyze_with_gemini(ocr_text)

    return _analyze_with_gemini(ocr_text)
