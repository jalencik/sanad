from types import SimpleNamespace

import pytest

from app.services import ai


class _FakePool:
    """Stands in for GeminiKeyPool so tests never touch the real SDK/network."""

    def __init__(self, response):
        self._response = response
        self.calls = 0

    def call(self, fn):
        self.calls += 1
        fake_client = SimpleNamespace(
            models=SimpleNamespace(generate_content=lambda **kwargs: self._response)
        )
        return fn(fake_client)


def test_analyze_document_text_returns_the_parsed_response(monkeypatch):
    fake_analysis = ai.DocumentAnalysis(
        document_type="passport",
        detected_language="Uzbek",
        summary_original="orig",
        summary_english="eng",
    )
    fake_pool = _FakePool(SimpleNamespace(parsed=fake_analysis))
    monkeypatch.setattr(ai, "_get_pool", lambda: fake_pool)

    result = ai.analyze_document_text("some ocr text")

    assert result is fake_analysis
    assert fake_pool.calls == 1


def test_analyze_document_text_raises_when_gemini_returns_no_structured_data(monkeypatch):
    fake_pool = _FakePool(SimpleNamespace(parsed=None))
    monkeypatch.setattr(ai, "_get_pool", lambda: fake_pool)

    with pytest.raises(RuntimeError):
        ai.analyze_document_text("some ocr text")
