import io
from unittest.mock import patch

import fitz
import pytest
from PIL import Image

from app.services.ocr import (
    OcrTimeoutError,
    PasswordProtectedError,
    _iter_pdf_pages,
    _text_from_data,
    run_ocr,
)


def test_text_from_data_preserves_line_breaks_and_reading_order():
    # Mirrors the real shape of pytesseract.image_to_data(output_type=DICT):
    # a row per detected element at every level (page/block/paragraph/line/
    # word), not just words - non-word rows carry an empty "text" and a -1
    # "conf", which the confidence averaging elsewhere already relies on.
    data = {
        "block_num": [0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3],
        "par_num": [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1],
        "line_num": [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1],
        "text": ["", "", "", "", "Hello", "world", "", "Second", "line", "here.", "", "", "", "Third", "para"],
        "conf": [-1, -1, -1, -1, 96.0, 94.5, -1, 91.0, 88.0, 90.2, -1, -1, -1, 93.0, 95.0],
    }

    assert _text_from_data(data) == "Hello world\nSecond line here.\nThird para"


def test_text_from_data_on_a_blank_page():
    data = {"block_num": [0], "par_num": [0], "line_num": [0], "text": [""], "conf": [-1]}

    assert _text_from_data(data) == ""


def _make_password_protected_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "Secret content")
    buffer = io.BytesIO()
    doc.save(buffer, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret123", owner_pw="ownersecret")
    doc.close()
    return buffer.getvalue()


def test_iter_pdf_pages_raises_a_specific_error_for_password_protected_pdfs():
    # Without this check, PyMuPDF only fails once a page is actually
    # rendered, with a bare ValueError("document closed or encrypted") -
    # indistinguishable from any other corruption. Catching needs_pass
    # upfront turns "may be password-protected... or who knows" into a
    # definite, actionable answer.
    protected_pdf = _make_password_protected_pdf()

    with pytest.raises(PasswordProtectedError):
        list(_iter_pdf_pages(protected_pdf))


def _make_blank_image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_run_ocr_raises_a_specific_error_when_tesseract_times_out():
    # pytesseract signals a subprocess timeout as a bare
    # RuntimeError('Tesseract process timeout') - without translating it,
    # this lands in the same bucket as a corrupted file. A page that's
    # still working, just slowly, deserves an honest "too big" message.
    with patch(
        "app.services.ocr.pytesseract.image_to_data",
        side_effect=RuntimeError("Tesseract process timeout"),
    ), pytest.raises(OcrTimeoutError):
        run_ocr(_make_blank_image_bytes(), "image/png")


def test_run_ocr_does_not_mistake_other_runtime_errors_for_a_timeout():
    # Guards the "timeout" in str(exc).lower() check itself: some other,
    # unrelated RuntimeError from pytesseract must not be silently
    # relabeled as a timeout it never was.
    with patch(
        "app.services.ocr.pytesseract.image_to_data",
        side_effect=RuntimeError("something else entirely"),
    ), pytest.raises(RuntimeError, match="something else entirely"):
        run_ocr(_make_blank_image_bytes(), "image/png")
