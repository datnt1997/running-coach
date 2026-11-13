from datetime import date, timedelta

import pytest

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _day(day, slots=1, max_km=None, quality=True):
    return {"day": day, "slots": slots, "maxKm": max_km, "qualityAllowed": quality}


def runner_week():
    """Seven training days: a double on Wednesday, 3 km cap on weekdays,
    Quality workouts only at the weekend."""
    week = [_day(d, slots=1, max_km=3, quality=False) for d in DAYS[:5]]
    week[2] = _day("Wed", slots=2, max_km=3, quality=False)
    week += [_day("Sat"), _day("Sun")]
    return week


def goal_payload(**extra):
    return {
        "distance": "half_marathon",
        "targetTime": "1:55:00",
        "raceDate": (date.today() + timedelta(weeks=16)).isoformat(),
        "fitnessLevel": "intermediate",
        "weeklyAvailability": runner_week(),
        **extra,
    }


async def _listed_goal(client, goal_id):
    resp = await client.get("/goals")
    assert resp.status_code == 200
    return next(g for g in resp.json()["goals"] if g["goalId"] == goal_id)


@pytest.mark.asyncio
async def test_availability_round_trips_through_goals_list(client):
    resp = await client.post("/goal", json=goal_payload())
    assert resp.status_code == 202, resp.text

    goal = await _listed_goal(client, resp.json()["goalId"])

    assert goal["weeklyAvailability"] == runner_week()
    assert goal["daysPerWeek"] == 7


def _week(**overrides):
    """A valid 7-day week with entries replaced by day name."""
    week = {d["day"]: d for d in runner_week()}
    week.update(overrides)
    return [week[d] for d in DAYS]


def _without(day):
    return [d for d in runner_week() if d["day"] != day]


def _only_two_training_days():
    return [_day(d, slots=1 if d in ("Sat", "Sun") else 0) for d in DAYS]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "availability",
    [
        pytest.param(_without("Thu"), id="missing-day"),
        pytest.param(runner_week() + [_day("Mon")], id="duplicate-day"),
        pytest.param(_week(Tue=_day("Tue", slots=3)), id="three-slots"),
        pytest.param(_week(Tue=_day("Tue", max_km=0)), id="zero-cap"),
        pytest.param(_week(Tue=_day("Tue", max_km=-2)), id="negative-cap"),
        pytest.param(_week(Tue=_day("Tue", max_km=61)), id="absurd-cap"),
        pytest.param(_only_two_training_days(), id="fewer-than-three-training-days"),
    ],
)
async def test_malformed_availability_is_rejected(client, availability):
    resp = await client.post("/goal", json=goal_payload(weeklyAvailability=availability))

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_rest_day_ignores_its_cap_and_quality_flag(client):
    week = _week(Thu=_day("Thu", slots=0, max_km=-5, quality=True))

    resp = await client.post("/goal", json=goal_payload(weeklyAvailability=week))

    assert resp.status_code == 202, resp.text


def _user_prompt(fake_ai_client) -> str:
    return next(m["content"] for m in fake_ai_client.last_messages if m["role"] == "user")


def _line_for(prompt: str, day: str) -> str:
    return next(line for line in prompt.splitlines() if line.startswith(f"- {day}:"))


@pytest.mark.asyncio
async def test_plan_request_lists_each_weekdays_limits(client, fake_ai_client):
    week = _week(Thu=_day("Thu", slots=0))
    resp = await client.post("/goal", json=goal_payload(weeklyAvailability=week))
    assert resp.status_code == 202, resp.text

    prompt = _user_prompt(fake_ai_client)

    wed = _line_for(prompt, "Wed")
    assert "2 workouts" in wed and "3 km" in wed and "no Quality" in wed
    assert "rest" in _line_for(prompt, "Thu")
    sat = _line_for(prompt, "Sat")
    assert "1 workout" in sat and "Quality workouts allowed" in sat and "km" not in sat


@pytest.mark.asyncio
async def test_plan_request_no_longer_states_days_per_week(client, fake_ai_client):
    await client.post("/goal", json=goal_payload())

    assert "training days per week" not in _user_prompt(fake_ai_client).lower()


@pytest.mark.asyncio
async def test_migration_turns_days_per_week_into_one_slot_days():
    from psycopg import AsyncConnection

    from app.config import DATABASE_URL
    from tests import conftest as c

    if not DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not configured")

    before = [c.MIGRATION_001, c.MIGRATION_002, c.MIGRATION_003, c.MIGRATION_004, c.MIGRATION_005]
    async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
        await conn.execute(f"DROP TABLE IF EXISTS {c._ALL_TABLES} CASCADE")
        for migration in before:
            await conn.execute(migration.read_text())
        for n in (3, 4, 7):
            await conn.execute(
                "INSERT INTO user_goals (distance, target_time, race_date, fitness_level, days_per_week)"
                " VALUES ('half_marathon', '2:00:00', '2027-06-01', 'intermediate', %s)",
                (n,),
            )

        await conn.execute(c.MIGRATION_006.read_text())

        cur = await conn.execute("SELECT weekly_availability FROM user_goals")
        weeks = [row[0] for row in await cur.fetchall()]

    # Mon, Wed, Fri, Sat, Tue, Thu, Sun is the order days are picked in.
    expected_training_days = {
        3: {"Mon", "Wed", "Fri"},
        4: {"Mon", "Wed", "Fri", "Sat"},
        7: set(DAYS),
    }
    by_count = {sum(d["slots"] for d in week): week for week in weeks}
    assert set(by_count) == {3, 4, 7}
    for n, week in by_count.items():
        assert [d["day"] for d in week] == DAYS
        assert {d["day"] for d in week if d["slots"] > 0} == expected_training_days[n]
        assert all(d["slots"] in (0, 1) for d in week)
        assert all(d["maxKm"] is None and d["qualityAllowed"] is True for d in week)


def _system_prompt(fake_ai_client) -> str:
    return next(m["content"] for m in fake_ai_client.last_messages if m["role"] == "system")


@pytest.mark.asyncio
async def test_system_prompt_allows_two_workouts_on_one_day(client, fake_ai_client):
    await client.post("/goal", json=goal_payload())

    system = _system_prompt(fake_ai_client)

    assert "one workout entry per day" not in system
    assert "two workouts" in system
