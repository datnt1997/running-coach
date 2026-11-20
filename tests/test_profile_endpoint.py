"""Runner profile (heart rates), the zones computed from it, and where they show up."""
from datetime import date, timedelta

from app.ai.factory import get_ai_client_dep
from app.db.connection import get_pool
from app.main import app
from tests.availability import week_with_days

FULL = {"maxHr": 190, "restingHr": 50}
EVENT = {"object_type": "activity", "object_id": 1, "aspect_type": "create", "owner_id": 12345}


async def test_an_empty_profile_says_what_is_missing_and_invents_no_zones(client):
    body = (await client.get("/profile")).json()
    assert body["maxHr"] is None
    assert body["zones"] is None
    assert body["missing"] == ["maxHr", "restingHr"]


async def test_profile_values_are_saved_and_edited(client):
    resp = await client.put("/profile", json=FULL)
    assert resp.status_code == 200
    body = (await client.get("/profile")).json()
    assert {k: body[k] for k in FULL} == FULL
    assert body["missing"] == []
    assert [z["max"] for z in body["zones"]] == [137, 153, 167, 175, 190]

    await client.put("/profile", json={**FULL, "maxHr": 195})
    body = (await client.get("/profile")).json()
    assert body["maxHr"] == 195 and body["restingHr"] == 50
    assert body["zones"][-1]["max"] == 195


async def test_cadence_is_no_longer_part_of_the_profile(client):
    resp = await client.put("/profile", json={**FULL, "cadence": 176})
    assert resp.status_code == 200
    assert "cadence" not in resp.json()
    assert "cadence" not in (await client.get("/profile")).json()


async def test_a_partial_profile_gives_a_message_not_zones(client):
    await client.put("/profile", json={"maxHr": 190})
    body = (await client.get("/profile")).json()
    assert body["zones"] is None
    assert body["missing"] == ["restingHr"]


async def test_inconsistent_values_are_rejected(client):
    for bad in (
        {"maxHr": 150, "restingHr": 150},
        {"maxHr": 400},
        {"lactateThresholdHr": 10},
    ):
        assert (await client.put("/profile", json=bad)).status_code == 422, bad
    assert (await client.get("/profile")).json()["maxHr"] is None


async def test_lactate_threshold_is_saved_edited_and_cleared(client):
    await client.put("/profile", json={**FULL, "lactateThresholdHr": 170})
    assert (await client.get("/profile")).json()["lactateThresholdHr"] == 170
    await client.put("/profile", json={**FULL, "lactateThresholdHr": 172})
    assert (await client.get("/profile")).json()["lactateThresholdHr"] == 172
    await client.put("/profile", json=FULL)
    assert (await client.get("/profile")).json()["lactateThresholdHr"] is None


async def test_lactate_threshold_must_be_below_max_hr(client):
    for bad in ({"maxHr": 170, "lactateThresholdHr": 170}, {"lactateThresholdHr": 300}):
        assert (await client.put("/profile", json=bad)).status_code == 422, bad


async def test_zones_ignore_the_lactate_threshold(client):
    await client.put("/profile", json={"maxHr": 190, "restingHr": 50, "lactateThresholdHr": 170})
    with_lthr = (await client.get("/profile")).json()
    await client.put("/profile", json={"maxHr": 190, "restingHr": 50})
    without = (await client.get("/profile")).json()
    assert with_lthr["zones"] == without["zones"] and with_lthr["missing"] == []
    await client.put("/profile", json={"lactateThresholdHr": 170})
    only = (await client.get("/profile")).json()
    assert only["zones"] is None and only["missing"] == ["maxHr", "restingHr"]


async def test_profile_requires_sign_in(anon_client):
    assert (await anon_client.get("/profile")).status_code == 401
    assert (await anon_client.put("/profile", json=FULL)).status_code == 401


def _plan_workouts(plan_json):
    return [w for week in plan_json["weeks"] for w in week["workouts"]]


async def test_planned_workouts_show_a_target_zone_once_the_profile_has_one(client, seeded_plan):
    goal_id = seeded_plan["goal_id"]
    async with get_pool().connection() as conn:
        await conn.execute("UPDATE user_goals SET plan_status = 'ready' WHERE id = %s", (goal_id,))
        await conn.commit()
    before = _plan_workouts((await client.get(f"/goal/{goal_id}/plan")).json())
    assert before and all(w["targetZone"] is None for w in before)

    await client.put("/profile", json=FULL)
    after = _plan_workouts((await client.get(f"/goal/{goal_id}/plan")).json())
    easy = next(w for w in after if w["type"] == "easy")
    assert easy["targetZone"] == {"minZone": 2, "maxZone": 2, "min": 138, "max": 153}

    by_id = (await client.get(f"/plan/{seeded_plan['plan_id']}")).json()
    assert _plan_workouts(by_id)[0]["targetZone"]["minZone"] == 2


async def _create_goal(client):
    resp = await client.post("/goal", json={
        "distance": "half_marathon", "targetTime": "1:55:00",
        "raceDate": (date.today() + timedelta(weeks=16)).isoformat(), "vdot": 40.0,
        "weeklyKm": 40, "longestRunKm": 18, "weeklyAvailability": week_with_days(4),
    })
    assert resp.status_code == 202


async def test_plan_prompt_carries_the_computed_zones(client, fake_ai_client):
    await client.put("/profile", json=FULL)
    await _create_goal(client)
    user = fake_ai_client.last_messages[1]["content"]
    assert "Z2 138-153 bpm" in user and "Z5 176-190 bpm" in user


async def test_plan_prompt_says_zones_are_unavailable_when_the_profile_is_empty(client, fake_ai_client):
    await _create_goal(client)
    user = fake_ai_client.last_messages[1]["content"]
    assert "Heart-rate zones: unavailable" in user
    assert "max_hr" in user and "resting_hr" in user
    assert "bpm" not in user


def _spy_on_ai():
    seen = []
    inner = app.dependency_overrides[get_ai_client_dep]()

    class Spy:
        async def generate(self, messages, tools=None, response_format=None):
            seen.append(messages)
            return await inner.generate(messages, tools=tools, response_format=response_format)

    app.dependency_overrides[get_ai_client_dep] = lambda: Spy()
    return seen


def _analysis_prompt(seen):
    return next(m for m in seen if "Planned workout" in m[1]["content"])[1]["content"]


async def test_adherence_prompt_names_the_target_zone_and_the_runners_average_hr(
    webhook_client, seeded_plan, seeded_strava_connection
):
    seen = _spy_on_ai()
    await webhook_client.put("/profile", json=FULL)
    assert (await webhook_client.post("/strava/webhook", json=EVENT)).status_code == 200

    text = _analysis_prompt(seen)
    assert "Target heart-rate zone: Z2 (138-153 bpm)" in text
    assert "Avg heart rate: 145.0 bpm" in text


async def test_adherence_prompt_without_a_profile_does_not_invent_zones(
    webhook_client, seeded_plan, seeded_strava_connection
):
    seen = _spy_on_ai()
    await webhook_client.post("/strava/webhook", json=EVENT)

    text = _analysis_prompt(seen)
    assert "Target heart-rate zone: unavailable" in text
    assert "139" not in text


async def test_resting_hr_must_be_below_max_hr(client):
    resp = await client.put("/profile", json={"maxHr": 150, "restingHr": 150})
    assert resp.status_code == 422
    assert "resting" in str(resp.json()).lower()



async def test_plan_says_whether_zones_are_available(client, seeded_plan):
    goal_id = seeded_plan["goal_id"]
    async with get_pool().connection() as conn:
        await conn.execute("UPDATE user_goals SET plan_status = 'ready' WHERE id = %s", (goal_id,))
        await conn.commit()
    assert (await client.get(f"/goal/{goal_id}/plan")).json()["zonesAvailable"] is False
    await client.put("/profile", json=FULL)
    assert (await client.get(f"/goal/{goal_id}/plan")).json()["zonesAvailable"] is True
    assert (await client.get(f"/plan/{seeded_plan['plan_id']}")).json()["zonesAvailable"] is True


async def test_hr_adherence_is_not_stored_when_zones_are_unavailable(
    webhook_client, seeded_plan, seeded_strava_connection
):
    await webhook_client.post("/strava/webhook", json=EVENT)
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT hr_adherence, pace_adherence FROM activity_analyses")
        hr, pace = await cur.fetchone()
    assert hr is None and pace == "on_target"


async def test_hr_adherence_is_stored_when_zones_are_available(
    webhook_client, seeded_plan, seeded_strava_connection
):
    await webhook_client.put("/profile", json=FULL)
    await webhook_client.post("/strava/webhook", json=EVENT)
    async with get_pool().connection() as conn:
        cur = await conn.execute("SELECT hr_adherence FROM activity_analyses")
        assert (await cur.fetchone())[0] == "on_target"


async def test_avg_hr_zone_follows_the_profile_filled_in_after_the_run(
    webhook_client, seeded_plan, seeded_strava_connection
):
    await webhook_client.post("/strava/webhook", json=EVENT)
    before = (await webhook_client.get("/weekly-summary?week_number=1")).json()
    assert before["sessions"][0]["actual"]["avgHrZone"] is None
    await webhook_client.put("/profile", json=FULL)
    after = (await webhook_client.get("/weekly-summary?week_number=1")).json()
    assert after["sessions"][0]["actual"]["avgHrZone"] == "Z2"
