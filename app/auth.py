"""Google sign-in, the email allowlist, and the signed session cookie.

The session is stateless: the cookie holds the email and an expiry, signed with
SESSION_SECRET. Nothing is stored server side, so it needs no table.
"""
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, Request

from app import config

SESSION_COOKIE = "rc_session"
SESSION_MAX_AGE = 365 * 24 * 3600  # a year: sign in once per device

_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class InvalidGoogleToken(Exception):
    pass


@dataclass(frozen=True)
class GoogleIdentity:
    email: str
    email_verified: bool


class GoogleVerifier:
    """Verifies a Google ID token through Google's tokeninfo endpoint.

    Tests replace this through get_google_verifier; they never call Google.
    """

    async def verify(self, id_token: str) -> GoogleIdentity:
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                resp = await http.get(_TOKENINFO_URL, params={"id_token": id_token})
        except httpx.HTTPError as exc:
            raise InvalidGoogleToken("Google could not be reached") from exc
        if resp.status_code != 200:
            raise InvalidGoogleToken("Google rejected the token")
        info = resp.json()
        if info.get("aud") != config.GOOGLE_CLIENT_ID or info.get("iss") not in _GOOGLE_ISSUERS:
            raise InvalidGoogleToken("Token was not issued for this app")
        if not info.get("email"):
            raise InvalidGoogleToken("Token has no email")
        return GoogleIdentity(
            email=info["email"], email_verified=str(info.get("email_verified")).lower() == "true"
        )


def get_google_verifier() -> GoogleVerifier:
    """FastAPI dependency; tests override it via app.dependency_overrides."""
    return GoogleVerifier()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def allowed_emails() -> set[str]:
    return {normalize_email(e) for e in (config.ALLOWED_EMAILS or "").split(",") if e.strip()}


def is_allowed(email: str) -> bool:
    return normalize_email(email) in allowed_emails()


# --- session cookie -------------------------------------------------------


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: bytes) -> str:
    if not config.SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET is not set; refusing to sign a session")
    key = config.SESSION_SECRET.encode()
    return _b64encode(hmac.new(key, payload, hashlib.sha256).digest())


def make_session_token(email: str, now: float | None = None) -> str:
    body = json.dumps({"email": email, "exp": int((time.time() if now is None else now) + SESSION_MAX_AGE)}).encode()
    return _b64encode(body) + "." + _sign(body)


def read_session_token(token: str | None, now: float | None = None) -> str | None:
    """The email in a valid, unexpired token, else None."""
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    try:
        body = _b64decode(encoded)
        if not hmac.compare_digest(signature, _sign(body)):
            return None
        data = json.loads(body)
        exp, email = data["exp"], data["email"]
    except (ValueError, TypeError, KeyError):
        return None
    if not isinstance(exp, (int, float)) or isinstance(exp, bool) or not isinstance(email, str):
        return None
    if exp < (time.time() if now is None else now):
        return None
    return email


def require_session(request: Request) -> str:
    """Dependency: the signed-in runner's email, or 401.

    The allowlist is re-checked on every request, so removing an email from
    ALLOWED_EMAILS signs that person out.
    """
    email = read_session_token(request.cookies.get(SESSION_COOKIE))
    if email is None or not is_allowed(email):
        raise HTTPException(status_code=401, detail="Not signed in")
    return email
