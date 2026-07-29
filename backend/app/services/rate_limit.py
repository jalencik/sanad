import time
from collections import defaultdict

from fastapi import HTTPException

_attempts: dict[str, list[float]] = defaultdict(list)

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300.0


def check_rate_limit(
    key: str,
    max_attempts: int = MAX_ATTEMPTS,
    window_seconds: float = WINDOW_SECONDS,
    message: str = "Too many login attempts. Try again in a few minutes.",
) -> None:
    now = time.monotonic()
    window_start = now - window_seconds
    attempts = [t for t in _attempts[key] if t > window_start]

    if len(attempts) >= max_attempts:
        _attempts[key] = attempts
        raise HTTPException(429, message)

    attempts.append(now)
    _attempts[key] = attempts

    # _attempts has no TTL of its own - every distinct key (IP, IP:email,
    # user id, ...) this process has ever seen would otherwise sit in memory
    # forever. Sweeping expired keys on the way through bounds it to
    # whatever's been active in the last window, at negligible extra cost.
    if len(_attempts) > 1000:
        for stale_key in [k for k, v in _attempts.items() if not v or v[-1] <= window_start]:
            del _attempts[stale_key]


def reset() -> None:
    """Clear all tracked attempts. Test isolation only - never called in app code."""
    _attempts.clear()
