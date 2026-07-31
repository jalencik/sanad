import io
from collections.abc import Iterator
from dataclasses import dataclass

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
_PAGE_TIMEOUT_SECONDS = 90


@dataclass
class OcrResult:
    text: str
    confidence: float


class PasswordProtectedError(Exception):
    """Raised when a PDF needs a password fitz was never given one for.

    Distinct from a generic OCR failure because it's not actually broken -
    without this check, PyMuPDF just raises a bare
    ValueError('document closed or encrypted') the moment a page is
    rendered, indistinguishable from any other corruption. Checking
    needs_pass upfront turns a guess ("may be password-protected... or who
    knows") into a definite answer.
    """


class OcrTimeoutError(Exception):
    """Raised when Tesseract itself reports it hit _PAGE_TIMEOUT_SECONDS.

    pytesseract signals this as a bare RuntimeError('Tesseract process
    timeout'), which without this translation would land in the same
    generic bucket as a corrupted file - a page that's still working, just
    slowly, deserves an honest "too big" message instead of "broken."
    """


def _iter_pdf_pages(data: bytes) -> Iterator[Image.Image]:
    # Yields one rendered page at a time rather than building a list of all
    # of them up front - an 8-page PDF at 300 DPI is easily 150-200MB of raw
    # RGB buffers, which on a 512MB host is real OOM risk. Each page becomes
    # eligible for garbage collection as soon as the loop below moves past
    # it instead of all of them living until the whole document finishes.
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise PasswordProtectedError("This PDF is password-protected")

        page_count = min(len(doc), settings.max_pdf_pages)
        for page_index in range(page_count):
            page = doc[page_index]
            pixmap = page.get_pixmap(dpi=300)
            yield Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def _iter_images(data: bytes, mime_type: str) -> Iterator[Image.Image]:
    if mime_type == "application/pdf":
        yield from _iter_pdf_pages(data)
    else:
        yield Image.open(io.BytesIO(data)).convert("RGB")


def _text_from_data(data: dict) -> str:
    # image_to_data's per-word output already contains everything
    # image_to_string would give us - grouping it back into lines by
    # (block, paragraph, line) reconstructs the same reading-order text
    # without a second full Tesseract pass over the same image.
    lines: dict[tuple[int, int, int], list[str]] = {}
    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
    return "\n".join(" ".join(words) for words in lines.values())


def run_ocr(data: bytes, mime_type: str) -> OcrResult:
    texts: list[str] = []
    page_confidences: list[float] = []

    for image in _iter_images(data, mime_type):
        # A single image_to_data call replaces what used to be a separate
        # image_to_string + image_to_data pair - each ran Tesseract as its
        # own subprocess with its own _PAGE_TIMEOUT_SECONDS ceiling, so two
        # calls meant a page could legitimately take up to twice as long as
        # this function's name suggests. On an 8-page PDF that pushed the
        # worst case (8 * 2 * 90s = 1440s) well past PROCESS_TIMEOUT_SECONDS
        # in pipeline.py, which could abort an honestly-still-working job
        # as "took too long." One call halves both the CPU spent per page
        # (real money on a fractional-CPU host) and that worst case.
        try:
            data = pytesseract.image_to_data(
                image,
                lang=settings.tesseract_languages,
                output_type=pytesseract.Output.DICT,
                timeout=_PAGE_TIMEOUT_SECONDS,
            )
        except RuntimeError as exc:
            # pytesseract only raises a bare RuntimeError for the
            # subprocess-timeout path (see its timeout_manager) - every
            # other engine failure comes back as a TesseractError instead.
            # Checking the message anyway keeps this honest rather than
            # assuming every RuntimeError here means "timeout."
            if "timeout" in str(exc).lower():
                raise OcrTimeoutError(str(exc)) from exc
            raise
        texts.append(_text_from_data(data))

        word_confidences = [float(c) for c in data["conf"] if float(c) >= 0]
        if word_confidences:
            page_confidences.append(sum(word_confidences) / len(word_confidences))

    combined_text = "\n\n".join(t for t in texts if t)
    average_confidence = (sum(page_confidences) / len(page_confidences) / 100) if page_confidences else 0.0

    return OcrResult(text=combined_text, confidence=round(average_confidence, 3))
