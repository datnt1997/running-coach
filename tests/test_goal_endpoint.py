import uuid
from datetime import date, timedelta

import pytest


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _race_date(weeks: int) -> str:
    return (date.today() + timedelta(weeks=weeks)).isoformat()


def _assert_plan_quality(plan: dict) -> None:
    phases = set(plan["phaseBreakdown"].keys())
    assert {"base", "build", "peak", "taper"}.issubset(phases)
    assert plan["totalWeeks"] == len(plan["weeks"])
    assert date.fromisoformat(plan["startDate"])  # raises if not a valid ISO date

    week_totals = []
    for week in plan["weeks"]:
        total = 0.0
        for workout in week["workouts"]:
            assert workout["day"] is not None
            assert workout["type"] is not None
            assert workout["distanceKm"] is not None
            assert workout["paceZone"] is not None
            total += workout["distanceKm"]
        week_totals.append(total)

    for prev, curr in zip(week_totals, week_totals[1:]):
        if prev > 0:
            assert curr <= prev * 1.10 + 1e-6, (
                f"week distance {curr} exceeds 10% over previous {prev}"
            )


async def _submit_and_fetch_plan(client, payload: dict) -> tuple[str, dict]:
    """POST /goal (202) then GET /goal/{goalId}/plan (200 ready). Returns (goalId, plan)."""
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert _valid_uuid(body["goalId"])
    assert body["status"] == "generating"

    # Background task runs synchronously in test transport — plan is ready immediately
    plan_resp = await client.get(f"/goal/{body['goalId']}/plan")
    assert plan_resp.status_code == 200, plan_resp.text
    plan = plan_resp.json()
    assert plan["status"] == "ready"
    return body["goalId"], plan


# 1. Valid HM → 202 + poll → 200 ready plan
async def test_valid_half_marathon(client):
    payload = {
        "distance": "half_marathon",
        "targetTime": "1:55:00",
        "raceDate": _race_date(16),
        "fitnessLevel": "intermediate",
        "daysPerWeek": 4,
        "injuryHistory": "left knee tendinopathy",
    }
    goal_id, plan = await _submit_and_fetch_plan(client, payload)

    assert _valid_uuid(plan["planId"])
    assert _valid_uuid(plan["goalId"])
    assert isinstance(plan["summary"], str) and plan["summary"]
    assert isinstance(plan["totalWeeks"], int)
    assert isinstance(plan["weeks"], list)
    _assert_plan_quality(plan)


# 2. Valid FM → poll → totalWeeks >= 12
async def test_valid_full_marathon(client):
    payload = {
        "distance": "full_marathon",
        "targetTime": "4:30:00",
        "raceDate": _race_date(20),
        "fitnessLevel": "advanced",
        "daysPerWeek": 4,
        "injuryHistory": None,
    }
    _, plan = await _submit_and_fetch_plan(client, payload)
    assert plan["totalWeeks"] >= 12
    _assert_plan_quality(plan)


# 3. HM target 1:38:00 → 422 goal_out_of_scope (no background task queued)
async def test_hm_too_fast_rejected(client):
    payload = {
        "distance": "half_marathon",
        "targetTime": "1:38:00",
        "raceDate": _race_date(16),
        "fitnessLevel": "advanced",
        "daysPerWeek": 5,
        "injuryHistory": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "goal_out_of_scope"


# 4. FM target 3:50:00 → 422 goal_out_of_scope
async def test_fm_too_fast_rejected(client):
    payload = {
        "distance": "full_marathon",
        "targetTime": "3:50:00",
        "raceDate": _race_date(20),
        "fitnessLevel": "advanced",
        "daysPerWeek": 5,
        "injuryHistory": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "goal_out_of_scope"


# 5. Race date 6 weeks → 422
async def test_race_date_too_soon_rejected(client):
    payload = {
        "distance": "half_marathon",
        "targetTime": "1:55:00",
        "raceDate": _race_date(6),
        "fitnessLevel": "intermediate",
        "daysPerWeek": 4,
        "injuryHistory": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "goal_out_of_scope"


# 6. GET /goal/{unknown}/plan → 404
async def test_get_unknown_goal_plan_404(client):
    resp = await client.get(f"/goal/{uuid.uuid4()}/plan")
    assert resp.status_code == 404, resp.text


# 7. GET /goals lists submitted goals
async def test_list_goals(client):
    payload = {
        "distance": "half_marathon",
        "targetTime": "1:55:00",
        "raceDate": _race_date(16),
        "fitnessLevel": "intermediate",
        "daysPerWeek": 4,
        "injuryHistory": None,
    }
    post = await client.post("/goal", json=payload)
    assert post.status_code == 202
    goal_id = post.json()["goalId"]

    resp = await client.get("/goals")
    assert resp.status_code == 200
    goals = resp.json()["goals"]
    assert any(g["goalId"] == goal_id for g in goals)


# 8. DELETE /goal/{goalId} → 200; subsequent poll → 404
async def test_delete_goal(client):
    payload = {
        "distance": "half_marathon",
        "targetTime": "1:55:00",
        "raceDate": _race_date(16),
        "fitnessLevel": "intermediate",
        "daysPerWeek": 4,
        "injuryHistory": None,
    }
    post = await client.post("/goal", json=payload)
    assert post.status_code == 202
    goal_id = post.json()["goalId"]

    del_resp = await client.delete(f"/goal/{goal_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    plan_resp = await client.get(f"/goal/{goal_id}/plan")
    assert plan_resp.status_code == 404


# 9. AI client called exactly once per POST /goal
async def test_ai_client_called_once(client, fake_ai_client):
    payload = {
        "distance": "half_marathon",
        "targetTime": "1:55:00",
        "raceDate": _race_date(16),
        "fitnessLevel": "intermediate",
        "daysPerWeek": 4,
        "injuryHistory": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 202, resp.text
    assert fake_ai_client.call_count == 1
