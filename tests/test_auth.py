"""Google sign-in with an email allowlist, and the session it issues.

The Google token check is a faked boundary (see FakeGoogleVerifier in conftest);
everything else runs through the real ASGI app.
"""
import pytest

from app.auth import SESSION_COOKIE
from app.main import app
from tests.conftest import ALLOWED_EMAIL, sign_in


async def test_allowlisted_identity_signs_in_and_is_recognised(anon_client):
    resp = await anon_client.post("/auth/google", json={"credential": f"fake:{ALLOWED_EMAIL}"})
    assert resp.status_code == 200
    assert resp.json() == {"email": ALLOWED_EMAIL}

    me = await anon_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json() == {"email": ALLOWED_EMAIL}


async def test_allowlist_match_ignores_case_and_spaces(anon_client):
    # The test allowlist is "runner@example.com, Friend@Example.com"
    resp = await anon_client.post("/auth/google", json={"credential": "fake:friend@example.com"})
    assert resp.status_code == 200


async def test_non_allowlisted_identity_is_refused_and_gets_no_session(anon_client):
    resp = await anon_client.post("/auth/google", json={"credential": "fake:stranger@example.com"})
    assert resp.status_code == 403
    assert SESSION_COOKIE not in resp.cookies
    assert (await anon_client.get("/auth/me")).status_code == 401


async def test_invalid_google_token_is_refused(anon_client):
    resp = await anon_client.post("/auth/google", json={"credential": "garbage"})
    assert resp.status_code == 401
    assert (await anon_client.get("/auth/me")).status_code == 401


async def test_session_cookie_is_persistent_and_hardened(anon_client):
    resp = await sign_in(anon_client)
    cookie = resp.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE}=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    max_age = int(cookie.split("max-age=")[1].split(";")[0])
    assert max_age >= 30 * 24 * 3600


async def test_stays_signed_in_on_a_later_visit(anon_client):
    resp = await sign_in(anon_client)
    cookie_value = resp.cookies[SESSION_COOKIE]
    anon_client.cookies.clear()  # a new visit: only the browser's stored cookie comes back
    anon_client.cookies.set(SESSION_COOKIE, cookie_value)
    assert (await anon_client.get("/auth/me")).json() == {"email": ALLOWED_EMAIL}
    assert (await anon_client.get("/goals")).status_code == 200


async def test_tampered_session_cookie_is_rejected(anon_client):
    resp = await sign_in(anon_client)
    forged = resp.cookies[SESSION_COOKIE][:-2] + "xx"
    anon_client.cookies.clear()
    anon_client.cookies.set(SESSION_COOKIE, forged)
    assert (await anon_client.get("/auth/me")).status_code == 401


async def test_session_for_an_email_removed_from_the_allowlist_stops_working(anon_client, monkeypatch):
    await sign_in(anon_client)
    from app import config
    monkeypatch.setattr(config, "ALLOWED_EMAILS", "someone-else@example.com")
    assert (await anon_client.get("/auth/me")).status_code == 401


async def test_sign_out_ends_the_session(client):
    assert (await client.get("/auth/me")).status_code == 200
    resp = await client.post("/auth/logout")
    assert resp.status_code == 200
    assert (await client.get("/auth/me")).status_code == 401
    assert (await client.get("/goals")).status_code == 401


# Routes that are reachable without a session, and why.
OPEN_ROUTES = {
    ("GET", "/health"),
    ("GET", "/"),  # static landing page, holds no data
    ("GET", "/app"),  # the SPA shell (only when built); it holds no data and shows the sign-in screen
    ("GET", "/app/{full_path}"),
    ("POST", "/auth/google"),  # this is the sign-in itself
    ("POST", "/auth/logout"),
    ("GET", "/strava/webhook"),  # Strava's verification challenge
    ("POST", "/strava/webhook"),  # Strava's events
}


def _protected_routes():
    # The OpenAPI schema lists every route however the routers are nested.
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if (method.upper(), path) not in OPEN_ROUTES:
                yield method.upper(), path


@pytest.mark.parametrize("method,path", sorted(_protected_routes()))
async def test_every_other_endpoint_requires_a_session(anon_client, method, path):
    url = path.replace("{goal_id}", "1").replace("{plan_id}", "1")
    resp = await anon_client.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)
    assert resp.status_code == 401, f"{method} {path} answered {resp.status_code} without a session"


async def test_protected_route_list_covers_the_known_endpoints():
    found = {p for _, p in _protected_routes()}
    assert {"/goal", "/goals", "/goal/{goal_id}", "/goal/{goal_id}/plan", "/plan/{plan_id}",
            "/fitness-chat", "/activities", "/weekly-summary", "/strava/status",
            "/strava/disconnect", "/strava/connect", "/strava/callback", "/auth/me"} <= found


async def test_webhook_and_challenge_reachable_without_a_session(anon_webhook_client):
    challenge = await anon_webhook_client.get(
        "/strava/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "test_verify_token", "hub.challenge": "abc"},
    )
    assert challenge.status_code == 200
    assert challenge.json() == {"hub.challenge": "abc"}

    event = await anon_webhook_client.post(
        "/strava/webhook",
        json={"object_type": "athlete", "object_id": 1, "aspect_type": "update", "owner_id": 1},
    )
    assert event.status_code == 200


async def test_health_is_open(anon_client):
    assert (await anon_client.get("/health")).status_code == 200


async def test_session_cookie_is_secure_by_default(anon_client, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "COOKIE_SECURE", True)
    resp = await sign_in(anon_client)
    assert "secure" in resp.headers["set-cookie"].lower().split("; ")


async def test_cookie_secure_can_be_turned_off_for_http_dev(anon_client, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "COOKIE_SECURE", False)
    resp = await sign_in(anon_client)
    assert "secure" not in resp.headers["set-cookie"].lower().split("; ")


def test_cookie_secure_config_defaults_to_true(monkeypatch):
    import importlib

    import dotenv

    from app import config

    try:
        # config calls load_dotenv() on reload; keep a developer's real .env out of this test
        monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
        monkeypatch.delenv("COOKIE_SECURE", raising=False)
        importlib.reload(config)
        assert config.COOKIE_SECURE is True
        monkeypatch.setenv("COOKIE_SECURE", "false")
        importlib.reload(config)
        assert config.COOKIE_SECURE is False
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_empty_session_secret_is_refused(monkeypatch):
    from app import auth, config

    monkeypatch.setattr(config, "SESSION_SECRET", "")
    with pytest.raises(RuntimeError):
        auth.make_session_token("runner@example.com")
    monkeypatch.setattr(config, "SESSION_SECRET", None)
    with pytest.raises(RuntimeError):
        auth.make_session_token("runner@example.com")


def _signed(payload) -> str:
    import base64
    import json

    from app import auth

    body = json.dumps(payload).encode()
    return base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + auth._sign(body)


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "runner@example.com", "exp": "soon"},
        {"email": "runner@example.com", "exp": None},
        {"email": "runner@example.com"},
        {"email": 5, "exp": 9999999999},
        ["not", "a", "dict"],
    ],
)
def test_malformed_signed_payload_is_invalid_not_an_error(payload):
    from app.auth import read_session_token

    assert read_session_token(_signed(payload)) is None


def test_now_of_zero_is_not_treated_as_unset():
    from app.auth import SESSION_MAX_AGE, make_session_token, read_session_token

    token = make_session_token("runner@example.com", now=0)
    assert read_session_token(token, now=0) == "runner@example.com"
    assert read_session_token(token, now=SESSION_MAX_AGE + 1) is None


@pytest.fixture
def valid_config(monkeypatch):
    """Every required setting present, so a test varies only SESSION_SECRET."""
    from app import config

    for name, value in {
        "ANTHROPIC_API_KEY": "k",
        "AI_PROVIDER": "anthropic",
        "CHAT_AI_PROVIDER": None,
        "DATABASE_URL": "postgresql://u:p@localhost/db_test",
        "GOOGLE_CLIENT_ID": "client-id",
        "ALLOWED_EMAILS": "runner@example.com",
        "STRAVA_CLIENT_ID": "id",
        "STRAVA_CLIENT_SECRET": "secret",
        "STRAVA_WEBHOOK_VERIFY_TOKEN": "token",
        "STRAVA_REDIRECT_URI": "http://localhost:8000/strava/callback",
        "SESSION_SECRET": "x" * 32,
    }.items():
        monkeypatch.setattr(config, name, value)
    return config


def test_strong_session_secret_passes_validation(valid_config):
    valid_config.validate_config()


@pytest.mark.parametrize("secret", ["change_me", "x" * 31])
def test_weak_session_secret_is_rejected_with_how_to_generate(valid_config, monkeypatch, secret):
    monkeypatch.setattr(valid_config, "SESSION_SECRET", secret)
    with pytest.raises(RuntimeError, match=r"secrets\.token_urlsafe\(48\)"):
        valid_config.validate_config()


# --- the real GoogleVerifier, with only the HTTP boundary faked -------------

import httpx  # noqa: E402

from app import auth  # noqa: E402


def _verifier_with(monkeypatch, handler):
    from app import config

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "client-id")
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        auth.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    return auth.GoogleVerifier()


def _claims(**over):
    claims = {
        "aud": "client-id",
        "iss": "https://accounts.google.com",
        "email": "runner@example.com",
        "email_verified": "true",
    }
    claims.update(over)
    return claims


async def test_real_verifier_accepts_a_valid_token(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_claims())

    identity = await _verifier_with(monkeypatch, handler).verify("tok")
    assert identity == auth.GoogleIdentity(email="runner@example.com", email_verified=True)
    assert seen["url"].startswith("https://oauth2.googleapis.com/tokeninfo")
    assert "id_token=tok" in seen["url"]


async def test_real_verifier_accepts_bare_google_issuer(monkeypatch):
    v = _verifier_with(monkeypatch, lambda r: httpx.Response(200, json=_claims(iss="accounts.google.com")))
    assert (await v.verify("tok")).email == "runner@example.com"


async def test_real_verifier_reports_unverified_email(monkeypatch):
    v = _verifier_with(monkeypatch, lambda r: httpx.Response(200, json=_claims(email_verified="false")))
    assert (await v.verify("tok")).email_verified is False


@pytest.mark.parametrize(
    "over", [{"aud": "someone-elses-client"}, {"iss": "https://evil.example.com"}, {"email": ""}]
)
async def test_real_verifier_rejects_wrong_audience_issuer_or_missing_email(monkeypatch, over):
    v = _verifier_with(monkeypatch, lambda r: httpx.Response(200, json=_claims(**over)))
    with pytest.raises(auth.InvalidGoogleToken):
        await v.verify("tok")


async def test_real_verifier_rejects_non_200(monkeypatch):
    v = _verifier_with(monkeypatch, lambda r: httpx.Response(400, json={"error": "invalid_token"}))
    with pytest.raises(auth.InvalidGoogleToken):
        await v.verify("tok")


async def test_real_verifier_turns_network_error_into_invalid_token(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(auth.InvalidGoogleToken):
        await _verifier_with(monkeypatch, handler).verify("tok")
