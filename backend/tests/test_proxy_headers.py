"""Regression coverage for the ProxyHeadersMiddleware trust boundary in
app/main.py. This exists because trusted_hosts="*" looks like the obvious
fix for rate limiting seeing one shared proxy IP, but it actually lets any
client bypass rate limiting outright by spoofing X-Forwarded-For - see the
comment above ProxyHeadersMiddleware in app/main.py for the full story.
"""

from httpx import ASGITransport, AsyncClient

from app.main import app

# ASGITransport's default simulated peer is ("127.0.0.1", 123), matching
# Settings.trusted_proxy_hosts' default - every other test file's fixtures
# are (implicitly) exercising the "trusted" path already.
UNTRUSTED_PEER = ("203.0.113.5", 12345)  # TEST-NET-3 (RFC 5737), not 127.0.0.1
TRUSTED_PEER = ("127.0.0.1", 123)


async def _signup(client: AsyncClient, email: str, forwarded_for: str) -> int:
    response = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "correct-horse-battery", "full_name": "User"},
        headers={"X-Forwarded-For": forwarded_for},
    )
    return response.status_code


async def test_untrusted_peer_cannot_bypass_rate_limit_by_spoofing_x_forwarded_for():
    transport = ASGITransport(app=app, client=UNTRUSTED_PEER)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A different claimed IP on every request - if the spoofed header
        # were honored, each would land in its own fresh rate-limit bucket
        # and this would never trip the limit.
        for i in range(5):
            assert await _signup(client, f"spoof{i}@example.com", f"203.0.113.{i}") == 201

        assert await _signup(client, "spoof-extra@example.com", "203.0.113.99") == 429


async def test_trusted_peer_x_forwarded_for_is_honored_per_real_client():
    transport = ASGITransport(app=app, client=TRUSTED_PEER)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Same shape as above, but from a trusted proxy address - each
        # distinct forwarded IP should get its own bucket, so none of these
        # six trip the signup rate limit (cap is 5 per bucket) the way the
        # untrusted-peer test above does.
        for i in range(6):
            assert await _signup(client, f"real{i}@example.com", f"198.51.100.{i}") == 201
