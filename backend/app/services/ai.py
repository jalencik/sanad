from typing import Any

from anthropic import Anthropic

from app.core.config import get_settings

settings = get_settings()

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


EXTRACTION_TOOL = {
    "name": "record_document_analysis",
    "description": "Record structured analysis of an official document's OCR text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "description": (
                    "Best guess at the document category, e.g. passport, birth_certificate, "
                    "contract, invoice, diploma, land_deed, court_order, other."
                ),
            },
            "document_number": {"type": ["string", "null"]},
            "issuing_authority": {"type": ["string", "null"]},
            "issue_date": {
                "type": ["string", "null"],
                "description": "ISO 8601 date if determinable, else the raw text found.",
            },
            "expiry_date": {"type": ["string", "null"]},
            "detected_language": {
                "type": "string",
                "description": "Primary language of the document, as an English word, e.g. Uzbek, Russian, English.",
            },
            "key_fields": {
                "type": "object",
                "description": "Other notable extracted fields as flat key-value string pairs (e.g. full_name).",
                "additionalProperties": {"type": "string"},
            },
            "summary_original": {
                "type": "string",
                "description": (
                    "A concise 2-4 sentence plain-language summary of the document's main point, "
                    "written in the document's own detected language."
                ),
            },
            "summary_english": {
                "type": "string",
                "description": (
                    "The same summary translated into English. If the document is already in "
                    "English, repeat it here."
                ),
            },
        },
        "required": [
            "document_type",
            "detected_language",
            "summary_original",
            "summary_english",
            "key_fields",
        ],
    },
}


class AiAnalysisResult:
    def __init__(self, data: dict[str, Any]):
        self.document_type: str | None = data.get("document_type")
        self.document_number: str | None = data.get("document_number")
        self.issuing_authority: str | None = data.get("issuing_authority")
        self.issue_date: str | None = data.get("issue_date")
        self.expiry_date: str | None = data.get("expiry_date")
        self.detected_language: str | None = data.get("detected_language")
        self.key_fields: dict[str, str] = data.get("key_fields") or {}
        self.summary_original: str | None = data.get("summary_original")
        self.summary_english: str | None = data.get("summary_english")


def analyze_document_text(ocr_text: str) -> AiAnalysisResult:
    client = _get_client()

    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1500,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_document_analysis"},
        messages=[
            {
                "role": "user",
                "content": (
                    "The following text was extracted via OCR from an official document and may "
                    "contain recognition errors. Analyze it and call the record_document_analysis "
                    "tool with your best-effort structured findings. If a field cannot be "
                    "determined, use null.\n\n"
                    f"--- OCR TEXT START ---\n{ocr_text}\n--- OCR TEXT END ---"
                ),
            }
        ],
    )

    for block in message.content:
        if block.type == "tool_use" and block.name == "record_document_analysis":
            return AiAnalysisResult(block.input)

    raise RuntimeError("Claude did not return a structured tool response")
