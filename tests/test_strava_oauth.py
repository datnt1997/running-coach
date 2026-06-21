from app.api.strava import _CSRF_COOKIE, get_strava_client
from app.main import app


async def test_connect_redirects_to_strava(client):
    resp = await client.get("/strava/connect", follow_redirects=False)
    assert resp.status_code == 302
    loc = resp.headers["location"]
    assert "strava.com/oauth/authorize" in loc
    assert "client_id=" in loc
    assert "scope=activity" in loc
    assert "state=" in loc
    assert _CSRF_COOKIE in resp.cookies


async def test_connect_sets_csrf_cookie(client):
    resp = await client.get("/strava/connect", follow_redirects=False)
    cookie = resp.cookies.get(_CSRF_COOKIE)
    assert cookie is not None and len(cookie) > 0


async def test_callback_valid_state_persists_and_redirects(client, fake_strava_client):
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client

    connect_resp = await client.get("/strava/connect", follow_redirects=False)
    state = connect_resp.cookies[_CSRF_COOKIE]

    resp = await client.get(
        f"/strava/callback?code=fake_code&state={state}&scope=activity:read_all",
        follow_redirects=False,
        cookies={_CSRF_COOKIE: state},
    )
    assert resp.status_code == 302
    assert "connected=1" in resp.headers["location"]

    status = await client.get("/strava/status")
    body = status.json()
    assert body["connected"] is True
    assert body["athlete_id"] == 12345


async def test_callback_invalid_state_returns_403(client, fake_strava_client):
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client

    resp = await client.get(
        "/strava/callback?code=fake_code&state=wrong&scope=activity:read_all",
        follow_redirects=False,
        cookies={_CSRF_COOKIE: "correct"},
    )
    assert resp.status_code == 403

    status = await client.get("/strava/status")
    assert status.json()["connected"] is False
