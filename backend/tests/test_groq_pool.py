import pytest

from app.services.groq_pool import GroqAPIError, GroqKeyPool


def _rate_limit_error() -> GroqAPIError:
    return GroqAPIError("rate limited", status_code=429)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _pool(keys, clock=None):
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    return GroqKeyPool(keys, **kwargs)


def test_call_returns_the_function_result():
    pool = _pool(["key-a"])
    assert pool.call(lambda key: "ok") == "ok"


def test_rotates_to_next_key_when_one_fails():
    pool = _pool(["key-a", "key-b"])

    def fn(key):
        if key == "key-a":
            raise _rate_limit_error()
        return key

    assert pool.call(fn) == "key-b"


def test_raises_last_error_when_every_key_fails():
    pool = _pool(["key-a", "key-b"])

    def always_fails(key):
        raise _rate_limit_error()

    with pytest.raises(GroqAPIError):
        pool.call(always_fails)


def test_a_failed_key_is_skipped_until_its_cooldown_elapses():
    clock = FakeClock()
    pool = _pool(["key-a", "key-b"], clock=clock)

    def fail_on_a(key):
        if key == "key-a":
            raise _rate_limit_error()
        return key

    pool.call(fail_on_a)  # puts key-a on cooldown

    assert pool.call(lambda key: key) == "key-b"

    clock.advance(60)
    assert pool.call(lambda key: key) == "key-a"


def test_consecutive_calls_use_consecutive_keys_even_without_failures():
    pool = _pool(["key-a", "key-b", "key-c"])

    used = [pool.call(lambda key: key) for _ in range(4)]

    assert used == ["key-a", "key-b", "key-c", "key-a"]


def test_empty_key_list_is_rejected():
    with pytest.raises(ValueError):
        GroqKeyPool([])
