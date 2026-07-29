from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.core.config import get_settings

settings = get_settings()

# Tesseract has no internal timeout of its own - a pathological image (huge
# dimensions, adversarial noise) can make it hang far past what any real
# document needs. The outer pipeline still bounds total processing time at
# PROCESS_TIMEOUT_SECONDS regardless, but this releases the OS thread (and
# frees up an _ocr_slots permit) as soon as a single page is actually stuck,
# rather than only when the whole document times out.
_PAGE_TIMEOUT_SECONDS = 60


@dataclass
class OcrResult:
    text: str
    confidence: float


def _render_pdf_pages(path: Path) -> list[Image.Image]:
    images: list[Image.Image] = []
    with fitz.open(path) as doc:
        page_count = min(len(doc), settings.max_pdf_pages)
        for page_index in range(page_count):
            page = doc[page_index]
            pixmap = page.get_pixmap(dpi=300)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            images.append(image)
    return images


def _load_images(path: Path, mime_type: str) -> list[Image.Image]:
    if mime_type == "application/pdf":
        return _render_pdf_pages(path)
    return [Image.open(path).convert("RGB")]


def run_ocr(path: Path, mime_type: str) -> OcrResult:
    images = _load_images(path, mime_type)
    texts: list[str] = []
    page_confidences: list[float] = []

    for image in images:
        text = pytesseract.image_to_string(
            image, lang=settings.tesseract_languages, timeout=_PAGE_TIMEOUT_SECONDS
        )
        texts.append(text.strip())

        data = pytesseract.image_to_data(
            image,
            lang=settings.tesseract_languages,
            output_type=pytesseract.Output.DICT,
            timeout=_PAGE_TIMEOUT_SECONDS,
        )
        word_confidences = [float(c) for c in data["conf"] if float(c) >= 0]
        if word_confidences:
            page_confidences.append(sum(word_confidences) / len(word_confidences))

    combined_text = "\n\n".join(t for t in texts if t)
    average_confidence = (sum(page_confidences) / len(page_confidences) / 100) if page_confidences else 0.0

    return OcrResult(text=combined_text, confidence=round(average_confidence, 3))
