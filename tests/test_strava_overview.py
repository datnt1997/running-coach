from app.api.strava import get_strava_client
from app.main import app


async def test_overview_not_connected(client):
    resp = await client.get("/strava/overview")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "athlete": None, "activities": []}


async def test_overview_shows_athlete_and_runs_only(client, fake_strava_client, seeded_strava_connection):
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    body = (await client.get("/strava/overview")).json()
    assert body["connected"] is True
    assert body["athlete"] == {"id": 12345, "name": "An Nguyen", "profile_url": "https://example.com/a.jpg"}
    assert [a["id"] for a in body["activities"]] == [777, 779]  # the ride is left out
    first = body["activities"][0]
    assert first["distance_km"] == 10.0
    assert first["pace_sec_per_km"] == 300
    assert first["avg_hr_bpm"] == 150.0
    assert first["match"] is None
    assert body["activities"][1]["avg_hr_bpm"] is None


async def test_overview_joins_the_analysis(client, fake_strava_client, seeded_strava_connection, seeded_plan, runner_id):
    from app.db.connection import get_pool
    from app.db.repositories import ActivityAnalysisRepository
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT id FROM workout_sessions LIMIT 1")
        workout_id = (await cur.fetchone())[0]
        await conn.execute(
            "INSERT INTO activity_analyses (strava_activity_id, matched_workout_id, activity_date, distance_km, "
            "pace_adherence, hr_adherence, load_adherence, mismatch, runner_id) "
            "VALUES (777, %s, '2026-11-20', 10, 'on_target', 'on_target', 'on_target', false, %s)",
            (workout_id, runner_id),
        )
        await conn.commit()
    body = (await client.get("/strava/overview")).json()
    run = next(a for a in body["activities"] if a["id"] == 777)
    assert run["match"]["workout_type"]
    assert run["match"]["load_adherence"] == "on_target"


async def test_overview_survives_a_profile_failure(client, fake_strava_client, seeded_strava_connection):
    async def boom(access_token):
        raise RuntimeError("no profile scope")
    fake_strava_client.get_athlete = boom
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    body = (await client.get("/strava/overview")).json()
    assert body["athlete"] == {"id": 12345, "name": None, "profile_url": None}
    assert len(body["activities"]) == 2


async def test_overview_502_when_strava_is_down(client, fake_strava_client, seeded_strava_connection):
    async def boom(access_token, limit=10):
        raise RuntimeError("down")
    fake_strava_client.list_activities = boom
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    assert (await client.get("/strava/overview")).status_code == 502


async def test_sync_requires_a_connection_and_a_plan(client, fake_strava_client):
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    assert (await client.post("/strava/sync")).status_code == 409


async def test_sync_stores_runs_once_and_the_page_then_shows_them(
    webhook_client, fake_strava_client, seeded_strava_connection, seeded_plan
):
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    first = (await webhook_client.post("/strava/sync")).json()
    assert first == {"synced": 2, "matched": 0, "remaining": 0}  # the two runs; the ride is skipped
    again = (await webhook_client.post("/strava/sync")).json()
    assert again["synced"] == 0
    from app.db.connection import get_pool
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT strava_activity_id FROM activity_analyses ORDER BY 1")
        assert [r[0] for r in await cur.fetchall()] == [777, 779]


async def test_sync_matches_a_run_on_a_planned_day(
    webhook_client, fake_strava_client, seeded_strava_connection, seeded_plan
):
    from app.strava.models import RecentActivity

    async def todays_run(access_token, limit=10):
        return [RecentActivity(id=900, name="Run", start_date_local=seeded_plan["date"].isoformat() + "T06:00:00Z",
                               distance=8000.0, moving_time=2700, average_heartrate=145.0, type="Run")]
    fake_strava_client.list_activities = todays_run
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    assert (await webhook_client.post("/strava/sync")).json() == {"synced": 1, "matched": 1, "remaining": 0}
    body = (await webhook_client.get("/strava/overview")).json()
    assert body["activities"][0]["match"]["workout_type"]
