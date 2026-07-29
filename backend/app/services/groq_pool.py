import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Groq's free tier resets its per-minute limits quickly; 30s cooldown mirrors
# the same reasoning as GeminiKeyPool (see app/services/gemini_pool.py) -
# generous enough to dodge the same key's limit twice, short enough to keep
# every key back in rotation fast. Non-429 failures get a shorter cooldown
# since they're less likely to still be bad moments later.
_RATE_LIMIT_COOLDOWN_SECONDS = 30.0
_DEFAULT_COOLDOWN_SECONDS = 10.0
# Groq's whole pitch is LPU inference speed - a real response lands in a
# couple of seconds. 20s is a generous ceiling for a stalled connection, not
# a budget anyone should routinely need.
_REQUEST_TIMEOUT_SECONDS = 20.0


class GroqAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def chat_completion_json(api_key: str, *, model: str, prompt: str) -> dict[str, Any]:
    """Calls Groq's OpenAI-compatible chat completions endpoint and parses a
    JSON object out of the response. Raises GroqAPIError on any non-2xx
    response or malformed body - callers rotate to the next key on any
    exception, so this never needs to distinguish failure types itself."""
    try:
        response = httpx.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise GroqAPIError(f"Groq request failed: {exc}") from exc

    if response.status_code != 200:
        raise GroqAPIError(
            f"Groq returned {response.status_code}: {response.text[:200]}",
            status_code=response.status_code,
        )

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise GroqAPIError(f"Unexpected Groq response shape: {exc}") from exc

    try:
        return json.loads(content)
    except ValueError as exc:
        raise GroqAPIError(f"Groq did not return valid JSON: {exc}") from exc


def _cooldown_for(exc: Exception) -> float:
    if isinstance(exc, GroqAPIError) and exc.status_code == 429:
        return _RATE_LIMIT_COOLDOWN_SECONDS
    return _DEFAULT_COOLDOWN_SECONDS


class GroqKeyPool:
    """Spreads Groq calls across several free-tier API keys.

    Same rotate-on-any-failure design as GeminiKeyPool (see
    app/services/gemini_pool.py): a failing key gets a short cooldown and the
    call moves on to the next key immediately rather than backing off on the
    key that just failed.
    """

    def __init__(
        self,
        keys: list[str],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not keys:
            raise ValueError("GroqKeyPool needs at least one API key")
        self._keys = keys
        self._clock = clock
        self._cooldown_until: dict[str, float] = {}
        self._next_index = 0
        self._lock = threading.Lock()

    def _ordered_keys(self) -> list[str]:
        with self._lock:
            start = self._next_index
            self._next_index = (self._next_index + 1) % len(self._keys)
        rotated = self._keys[start:] + self._keys[:start]
        now = self._clock()
        ready = [key for key in rotated if self._cooldown_until.get(key, 0.0) <= now]
        cooling = [key for key in rotated if key not in ready]
        return ready + cooling

    def call(self, fn: Callable[[str], T]) -> T:
        last_exc: Exception | None = None
        for key in self._ordered_keys():
            try:
                return fn(key)
            except Exception as exc:  # noqa: BLE001 - any failure rotates to the next key
                masked = f"...{key[-4:]}" if len(key) > 4 else "***"
                logger.warning("Groq key %s failed, rotating to next key: %s", masked, exc)
                self._cooldown_until[key] = self._clock() + _cooldown_for(exc)
                last_exc = exc
        assert last_exc is not None  # unreachable: _keys is always non-empty
        raise last_exc
