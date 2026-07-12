from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

settings = get_settings()

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthError(Exception):
    pass


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_userinfo(code: str) -> dict:
    """Exchange an authorization code for tokens, then fetch the profile.

    Raises GoogleOAuthError on any failure - callers should turn this into a
    generic auth error rather than exposing Google's raw response to users.
    """
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        token_response = await http_client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code != 200:
            raise GoogleOAuthError(f"Token exchange failed: {token_response.status_code}")

        access_token = token_response.json().get("access_token")
        if not access_token:
            raise GoogleOAuthError("No access_token in Google's response")

        userinfo_response = await http_client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_response.status_code != 200:
            raise GoogleOAuthError(f"Fetching userinfo failed: {userinfo_response.status_code}")

        userinfo = userinfo_response.json()

    if not userinfo.get("email"):
        raise GoogleOAuthError("Google account has no email")

    return userinfo
