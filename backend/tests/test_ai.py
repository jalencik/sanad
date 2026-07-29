from types import SimpleNamespace

import pytest

from app.services import ai


class _FakeGeminiPool:
    """Stands in for GeminiKeyPool so tests never touch the real SDK/network."""

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = 0

    def call(self, fn):
        self.calls += 1
        if self._error is not None:
            raise self._error
        fake_client = SimpleNamespace(
            models=SimpleNamespace(generate_content=lambda **kwargs: self._response)
        )
        return fn(fake_client)


class _FakeGroqPool:
    """Stands in for GroqKeyPool - fn receives a bare API key string."""

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = 0

    def call(self, fn):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return fn("fake-groq-key")


def _fake_analysis(**overrides) -> ai.DocumentAnalysis:
    defaults = dict(document_type="passport", detected_language="Uzbek", summary_original="orig", summary_english="eng")
    return ai.DocumentAnalysis(**{**defaults, **overrides})


def test_analyze_document_text_returns_the_parsed_gemini_response(monkeypatch):
    fake_analysis = _fake_analysis()
    fake_pool = _FakeGeminiPool(response=SimpleNamespace(parsed=fake_analysis))
    monkeypatch.setattr(ai, "_get_gemini_pool", lambda: fake_pool)
    monkeypatch.setattr(ai.settings, "ai_provider", "gemini")

    result = ai.analyze_document_text("some ocr text")

    assert result is fake_analysis
    assert fake_pool.calls == 1


def test_analyze_document_text_raises_when_gemini_returns_no_structured_data(monkeypatch):
    fake_pool = _FakeGeminiPool(response=SimpleNamespace(parsed=None))
    monkeypatch.setattr(ai, "_get_gemini_pool", lambda: fake_pool)
    monkeypatch.setattr(ai.settings, "ai_provider", "gemini")

    with pytest.raises(RuntimeError):
        ai.analyze_document_text("some ocr text")


def test_analyze_document_text_uses_groq_when_it_is_the_resolved_provider(monkeypatch):
    fake_analysis = _fake_analysis()
    fake_pool = _FakeGroqPool(result=fake_analysis)
    monkeypatch.setattr(ai, "_get_groq_pool", lambda: fake_pool)
    monkeypatch.setattr(
        ai,
        "chat_completion_json",
        lambda api_key, *, model, prompt: fake_analysis.model_dump(mode="json"),
    )
    monkeypatch.setattr(ai.settings, "ai_provider", "groq")

    result = ai.analyze_document_text("some ocr text")

    assert result == fake_analysis
    assert fake_pool.calls == 1


def test_groq_failure_falls_back_to_gemini_when_gemini_is_also_configured(monkeypatch):
    fake_analysis = _fake_analysis()
    fake_groq_pool = _FakeGroqPool(error=RuntimeError("every groq key rate-limited"))
    fake_gemini_pool = _FakeGeminiPool(response=SimpleNamespace(parsed=fake_analysis))
    monkeypatch.setattr(ai, "_get_groq_pool", lambda: fake_groq_pool)
    monkeypatch.setattr(ai, "_get_gemini_pool", lambda: fake_gemini_pool)
    monkeypatch.setattr(ai.settings, "ai_provider", "groq")
    monkeypatch.setattr(ai.settings, "gemini_api_keys", "gemini-fallback-key")

    result = ai.analyze_document_text("some ocr text")

    assert result is fake_analysis
    assert fake_groq_pool.calls == 1
    assert fake_gemini_pool.calls == 1


def test_groq_failure_raises_when_no_gemini_fallback_is_configured(monkeypatch):
    fake_groq_pool = _FakeGroqPool(error=RuntimeError("every groq key rate-limited"))
    monkeypatch.setattr(ai, "_get_groq_pool", lambda: fake_groq_pool)
    monkeypatch.setattr(ai.settings, "ai_provider", "groq")
    monkeypatch.setattr(ai.settings, "gemini_api_keys", "")
    monkeypatch.setattr(ai.settings, "gemini_api_key", "")

    with pytest.raises(RuntimeError, match="every groq key"):
        ai.analyze_document_text("some ocr text")
