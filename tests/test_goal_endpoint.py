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
    # All four phases present.
    phases = set(plan["phase_breakdown"].keys())
    assert {"base", "build", "peak", "taper"}.issubset(phases)

    # total_weeks == number of weeks returned.
    assert plan["total_weeks"] == len(plan["weeks"])

    # Every workout has non-null day, type, distance_km, pace_zone.
    week_totals = []
    for week in plan["weeks"]:
        total = 0.0
        for workout in week["workouts"]:
            assert workout["day"] is not None
            assert workout["type"] is not None
            assert workout["distance_km"] is not None
            assert workout["pace_zone"] is not None
            total += workout["distance_km"]
        week_totals.append(total)

    # No week exceeds 10% more total distance than the previous week.
    for prev, curr in zip(week_totals, week_totals[1:]):
        if prev > 0:
            assert curr <= prev * 1.10 + 1e-6, (
                f"week distance {curr} exceeds 10% over previous {prev}"
            )


# 1. Valid HM (sub 1:55, 16 weeks out) -> 200 + schema + valid UUID
async def test_valid_half_marathon(client):
    payload = {
        "distance": "half_marathon",
        "target_time": "1:55:00",
        "race_date": _race_date(16),
        "fitness_level": "intermediate",
        "days_per_week": 4,
        "injury_history": "left knee tendinopathy",
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert _valid_uuid(body["plan_id"])
    assert _valid_uuid(body["goal_id"])
    assert isinstance(body["summary"], str) and body["summary"]
    assert isinstance(body["total_weeks"], int)
    assert isinstance(body["weeks"], list)
    _assert_plan_quality(body)


# 2. Valid FM (sub 4:30, 20 weeks out) -> 200 + total_weeks >= 12
async def test_valid_full_marathon(client):
    payload = {
        "distance": "full_marathon",
        "target_time": "4:30:00",
        "race_date": _race_date(20),
        "fitness_level": "advanced",
        "days_per_week": 4,
        "injury_history": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total_weeks"] >= 12
    _assert_plan_quality(body)


# 3. HM target 1:38:00 -> 422 goal_out_of_scope
async def test_hm_too_fast_rejected(client):
    payload = {
        "distance": "half_marathon",
        "target_time": "1:38:00",
        "race_date": _race_date(16),
        "fitness_level": "advanced",
        "days_per_week": 5,
        "injury_history": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "goal_out_of_scope"


# 4. FM target 3:50:00 -> 422 goal_out_of_scope
async def test_fm_too_fast_rejected(client):
    payload = {
        "distance": "full_marathon",
        "target_time": "3:50:00",
        "race_date": _race_date(20),
        "fitness_level": "advanced",
        "days_per_week": 5,
        "injury_history": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "goal_out_of_scope"


# 5. Race date 6 weeks from today -> 422
async def test_race_date_too_soon_rejected(client):
    payload = {
        "distance": "half_marathon",
        "target_time": "1:55:00",
        "race_date": _race_date(6),
        "fitness_level": "intermediate",
        "days_per_week": 4,
        "injury_history": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "goal_out_of_scope"


# 6. GET /plan/{plan_id} after POST -> 200 same plan
async def test_get_plan_after_post(client):
    payload = {
        "distance": "half_marathon",
        "target_time": "1:55:00",
        "race_date": _race_date(16),
        "fitness_level": "intermediate",
        "days_per_week": 4,
        "injury_history": None,
    }
    post_resp = await client.post("/goal", json=payload)
    assert post_resp.status_code == 200, post_resp.text
    created = post_resp.json()
    plan_id = created["plan_id"]

    get_resp = await client.get(f"/plan/{plan_id}")
    assert get_resp.status_code == 200, get_resp.text
    fetched = get_resp.json()

    assert fetched["plan_id"] == plan_id
    assert fetched["goal_id"] == created["goal_id"]
    assert fetched["summary"] == created["summary"]
    assert fetched["total_weeks"] == created["total_weeks"]
    assert len(fetched["weeks"]) == len(created["weeks"])
    _assert_plan_quality(fetched)


# 7. GET /plan/{unknown_uuid} -> 404
async def test_get_unknown_plan_404(client):
    unknown = str(uuid.uuid4())
    resp = await client.get(f"/plan/{unknown}")
    assert resp.status_code == 404, resp.text


# Verify the AI client is invoked exactly once per POST /goal.
async def test_ai_client_called_once(client, fake_ai_client):
    payload = {
        "distance": "half_marathon",
        "target_time": "1:55:00",
        "race_date": _race_date(16),
        "fitness_level": "intermediate",
        "days_per_week": 4,
        "injury_history": None,
    }
    resp = await client.post("/goal", json=payload)
    assert resp.status_code == 200, resp.text
    assert fake_ai_client.call_count == 1
