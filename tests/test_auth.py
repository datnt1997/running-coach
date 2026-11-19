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

    from app import config

    try:
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
