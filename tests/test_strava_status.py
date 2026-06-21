from app.api.strava import get_strava_client
from app.main import app


async def test_status_no_connection(client):
    resp = await client.get("/strava/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is False
    assert body["athlete_id"] is None


async def test_status_after_connect(client, fake_strava_client):
    from app.api.strava import _CSRF_COOKIE

    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client

    connect = await client.get("/strava/connect", follow_redirects=False)
    state = connect.cookies[_CSRF_COOKIE]
    await client.get(
        f"/strava/callback?code=c&state={state}&scope=activity:read_all",
        follow_redirects=False,
        cookies={_CSRF_COOKIE: state},
    )

    resp = await client.get("/strava/status")
    assert resp.status_code == 200
    assert resp.json()["connected"] is True


async def test_disconnect_clears_connection(client, fake_strava_client):
    from app.api.strava import _CSRF_COOKIE

    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client

    connect = await client.get("/strava/connect", follow_redirects=False)
    state = connect.cookies[_CSRF_COOKIE]
    await client.get(
        f"/strava/callback?code=c&state={state}&scope=activity:read_all",
        follow_redirects=False,
        cookies={_CSRF_COOKIE: state},
    )

    disc = await client.post("/strava/disconnect")
    assert disc.status_code == 200
    assert disc.json()["connected"] is False

    status = await client.get("/strava/status")
    assert status.json()["connected"] is False
