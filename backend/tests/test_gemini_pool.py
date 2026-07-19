import pytest
from google.genai import errors


def _rate_limit_error() -> errors.ClientError:
    return errors.ClientError(429, {"error": {"message": "rate limited"}})


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _pool(keys, clock=None):
    from app.services.gemini_pool import GeminiKeyPool

    kwargs = {"client_factory": lambda key: key}
    if clock is not None:
        kwargs["clock"] = clock
    return GeminiKeyPool(keys, **kwargs)


def test_call_returns_the_function_result():
    pool = _pool(["key-a"])
    assert pool.call(lambda client: "ok") == "ok"


def test_rotates_to_next_key_when_one_fails():
    pool = _pool(["key-a", "key-b"])

    def fn(client):
        if client == "key-a":
            raise _rate_limit_error()
        return client

    assert pool.call(fn) == "key-b"


def test_raises_last_error_when_every_key_fails():
    pool = _pool(["key-a", "key-b"])

    def always_fails(client):
        raise _rate_limit_error()

    with pytest.raises(errors.ClientError):
        pool.call(always_fails)


def test_a_failed_key_is_skipped_until_its_cooldown_elapses():
    clock = FakeClock()
    pool = _pool(["key-a", "key-b"], clock=clock)

    def fail_on_a(client):
        if client == "key-a":
            raise _rate_limit_error()
        return client

    pool.call(fail_on_a)  # puts key-a on cooldown

    assert pool.call(lambda client: client) == "key-b"

    clock.advance(60)
    assert pool.call(lambda client: client) == "key-a"


def test_empty_key_list_is_rejected():
    from app.services.gemini_pool import GeminiKeyPool

    with pytest.raises(ValueError):
        GeminiKeyPool([])
