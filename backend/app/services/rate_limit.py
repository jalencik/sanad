import time
from collections import defaultdict

from fastapi import HTTPException

_attempts: dict[str, list[float]] = defaultdict(list)

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300.0


def check_rate_limit(key: str) -> None:
    now = time.monotonic()
    window_start = now - WINDOW_SECONDS
    attempts = [t for t in _attempts[key] if t > window_start]

    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(429, "Too many login attempts. Try again in a few minutes.")

    attempts.append(now)
    _attempts[key] = attempts
