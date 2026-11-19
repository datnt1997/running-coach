from datetime import date, timedelta

from tests.conftest import ALLOWED_EMAIL, make_runner, sign_in

HEADER = "week,phase,day,type,distance_km,pace_zone,notes"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _monday(offset_weeks: int = 0) -> date:
    today = date.today()
    return today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)


def _body(csv_text: str, race_in_weeks: int = 3, start: date | None = None) -> dict:
    return {
        "distance": "full_marathon",
        "targetTime": "3:59:00",
        "raceDate": (date.today() + timedelta(weeks=race_in_weeks)).isoformat(),
        "startDate": (start or _monday()).isoformat(),
        "csv": csv_text,
    }


def _plan_csv(weeks: int = 3) -> str:
    rows = [HEADER]
    for w in range(1, weeks + 1):
        rows += [
            f"{w},IV,Mon,easy,8,E,",
            f"{w},IV,Wed,tempo,10,T,Steady",
            f"{w},IV,Sat,long,20,E,",
        ]
    return "\n".join(rows)


async def _count(table: str) -> int:
    from app.db.connection import get_pool
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"SELECT count(*) FROM {table}")
            return (await cur.fetchone())[0]


async def test_valid_import_becomes_active_goal_with_plan_and_workouts(client):
    resp = await client.post("/plan/import", json=_body(_plan_csv()))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["totalWeeks"] == 3 and body["workoutCount"] == 9

    goals = (await client.get("/goals")).json()["goals"]
    assert [g["goalId"] for g in goals] == [body["goalId"]]
    assert goals[0]["planStatus"] == "ready"
    assert goals[0]["distance"] == "full_marathon"

    plan = (await client.get(f"/goal/{body['goalId']}/plan")).json()
    assert plan["status"] == "ready"
    assert plan["totalWeeks"] == 3
    assert plan["startDate"] == _monday().isoformat()
    assert [w["day"] for w in plan["weeks"][0]["workouts"]] == ["Mon", "Wed", "Sat"]
    assert plan["weeks"][0]["workouts"][1]["notes"] == "Steady"


async def test_unparseable_rows_are_reported_and_nothing_is_written(client):
    csv_text = _plan_csv() + "\n2,IV,Funday,easy,5,E,\n3,IV,Tue,easy,lots,E,"
    resp = await client.post("/plan/import", json=_body(csv_text))
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "plan_import_invalid"
    assert [r["line"] for r in detail["rows"]] == [11, 12]
    assert await _count("user_goals") == 0
    assert await _count("training_plans") == 0
    assert await _count("workout_sessions") == 0


async def test_start_date_must_be_a_monday(client):
    body = _body(_plan_csv(), start=_monday() + timedelta(days=2))
    resp = await client.post("/plan/import", json=body)
    assert resp.status_code == 422
    assert await _count("user_goals") == 0


async def test_race_inside_six_weeks_imports_but_scratch_generation_is_refused(client):
    resp = await client.post("/plan/import", json=_body(_plan_csv(), race_in_weeks=2))
    assert resp.status_code == 201, resp.text

    scratch = await client.post("/goal", json={
        "distance": "full_marathon", "targetTime": "4:30:00",
        "raceDate": (date.today() + timedelta(weeks=2)).isoformat(),
        "weeklyAvailability": [
            {"day": d, "slots": 1 if d in ("Mon", "Wed", "Sat") else 0,
             "maxKm": None, "qualityAllowed": True} for d in DAYS
        ],
        "vdot": 40, "weeklyKm": 40, "longestRunKm": 18,
    })
    assert scratch.status_code == 422
    assert scratch.json()["detail"]["error"] == "goal_out_of_scope"


async def test_import_replaces_the_previous_active_goal(client):
    first = (await client.post("/plan/import", json=_body(_plan_csv()))).json()
    second = (await client.post("/plan/import", json=_body(_plan_csv(2)))).json()
    goals = (await client.get("/goals")).json()["goals"]
    assert goals[0]["goalId"] == second["goalId"]  # newest first = Active Goal
    assert {g["goalId"] for g in goals} == {first["goalId"], second["goalId"]}


async def test_imported_plan_takes_a_strava_match(webhook_client, seeded_strava_connection):
    today = date.today()
    csv_text = f"{HEADER}\n1,IV,{DAYS[today.weekday()]},easy,8,E,"
    resp = await webhook_client.post("/plan/import", json=_body(csv_text, race_in_weeks=2))
    assert resp.status_code == 201, resp.text

    hook = await webhook_client.post("/strava/webhook", json={
        "object_type": "activity", "object_id": 987, "aspect_type": "create", "owner_id": 12345,
    })
    assert hook.status_code == 200
    row = (await webhook_client.get("/activities")).json()["activities"][0]
    assert row["analysisStatus"] == "complete"
    assert row["matchedWorkoutId"] is not None


async def test_import_belongs_to_the_signed_in_runner(client, anon_client):
    await client.post("/plan/import", json=_body(_plan_csv()))
    await make_runner("friend@example.com")
    await sign_in(anon_client, "friend@example.com")
    assert (await anon_client.get("/goals")).json()["goals"] == []
