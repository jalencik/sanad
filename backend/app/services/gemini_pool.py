import logging
import threading
import time
from collections.abc import Callable
from typing import TypeVar

from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Free-tier rate limits (RPM) typically reset within well under a minute;
# 30s is generous enough to avoid hammering a limited key again while still
# bringing it back into rotation quickly. Non-429 failures (network blips,
# 5xx) get a shorter cooldown since they're less likely to still be bad.
_RATE_LIMIT_COOLDOWN_SECONDS = 30.0
_DEFAULT_COOLDOWN_SECONDS = 10.0
_CLIENT_TIMEOUT_MS = 30_000


def _build_client(key: str) -> genai.Client:
    return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=_CLIENT_TIMEOUT_MS))


def _cooldown_for(exc: Exception) -> float:
    if isinstance(exc, errors.APIError) and exc.code == 429:
        return _RATE_LIMIT_COOLDOWN_SECONDS
    return _DEFAULT_COOLDOWN_SECONDS


class GeminiKeyPool:
    """Spreads Gemini calls across several free-tier API keys.

    On any failure from a key (rate limit, transient network error, ...) that
    key is put on a short cooldown and the call is retried against the next
    key immediately - no waiting on a key we already know just failed.
    """

    def __init__(
        self,
        keys: list[str],
        *,
        client_factory: Callable[[str], genai.Client] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not keys:
            raise ValueError("GeminiKeyPool needs at least one API key")
        self._keys = keys
        self._client_factory = client_factory or _build_client
        self._clock = clock
        self._clients: dict[str, genai.Client] = {}
        self._cooldown_until: dict[str, float] = {}
        self._next_index = 0
        self._lock = threading.Lock()

    def _client_for(self, key: str) -> genai.Client:
        if key not in self._clients:
            self._clients[key] = self._client_factory(key)
        return self._clients[key]

    def _ordered_keys(self) -> list[str]:
        with self._lock:
            start = self._next_index
            self._next_index = (self._next_index + 1) % len(self._keys)
        rotated = self._keys[start:] + self._keys[:start]
        now = self._clock()
        ready = [key for key in rotated if self._cooldown_until.get(key, 0.0) <= now]
        cooling = [key for key in rotated if key not in ready]
        return ready + cooling

    def call(self, fn: Callable[[genai.Client], T]) -> T:
        last_exc: Exception | None = None
        for key in self._ordered_keys():
            try:
                return fn(self._client_for(key))
            except Exception as exc:  # noqa: BLE001 - any failure rotates to the next key
                masked = f"...{key[-4:]}" if len(key) > 4 else "***"
                logger.warning("Gemini key %s failed, rotating to next key: %s", masked, exc)
                self._cooldown_until[key] = self._clock() + _cooldown_for(exc)
                last_exc = exc
        assert last_exc is not None  # unreachable: _keys is always non-empty
        raise last_exc
