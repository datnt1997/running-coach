"""Plan edits by chat: the coach proposes, Python checks, the Runner confirms, the edit is logged."""
from datetime import date, timedelta

import pytest
import pytest_asyncio
from psycopg.types.json import Jsonb

from app.ai.factory import get_chat_ai_client_dep
from app.db.connection import get_pool
from app.main import app
from tests.conftest import FakePlanChatAIClient

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Mon, Tue, Thu: one Easy run up to 5 km. Wed: up to 12 km, Quality allowed. Fri: rest.
# Sat: no cap, Quality allowed. Sun: up to 25 km, no Quality.
AVAILABILITY = [
    {"day": "Mon", "slots": 1, "maxKm": 5, "qualityAllowed": False},
    {"day": "Tue", "slots": 1, "maxKm": 5, "qualityAllowed": False},
    {"day": "Wed", "slots": 1, "maxKm": 12, "qualityAllowed": True},
    {"day": "Thu", "slots": 1, "maxKm": 5, "qualityAllowed": False},
    {"day": "Fri", "slots": 0, "maxKm": None, "qualityAllowed": False},
    {"day": "Sat", "slots": 1, "maxKm": None, "qualityAllowed": True},
    {"day": "Sun", "slots": 1, "maxKm": 25, "qualityAllowed": False},
]

# 45 km a week; the Long run limit is 30% of that, 13.5 km.
WEEK = [
    ("Mon", "easy", 5.0), ("Tue", "easy", 5.0), ("Wed", "tempo", 10.0),
    ("Thu", "easy", 5.0), ("Sat", "easy", 8.0), ("Sun", "long", 12.0),
]


def _week(**changes):
    """WEEK as a proposal's workouts, with `Day=(type, km)` replacements (None drops the day)."""
    out = []
    for day, kind, km in WEEK:
        if day in changes:
            if changes[day] is None:
                continue
            kind, km = changes[day]
        out.append({"day": day, "type": kind, "distance_km": km, "pace_zone": "Z2", "notes": ""})
    for day, value in changes.items():
        if value is not None and day not in {d for d, _, _ in WEEK}:
            out.append({"day": day, "type": value[0], "distance_km": value[1], "pace_zone": "Z2", "notes": ""})
    return out


@pytest_asyncio.fixture
async def chat_ai(client):
    fake = FakePlanChatAIClient()
    app.dependency_overrides[get_chat_ai_client_dep] = lambda: fake
    return fake


@pytest_asyncio.fixture
async def plan(client, runner_id):
    """A 4-week Plan: week 1 was last week, week 2 is this week, weeks 3 and 4 are ahead."""
    today = date.today()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=1)
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "INSERT INTO user_goals (distance, target_time, race_date, vdot, weekly_availability, runner_id)"
            " VALUES ('full_marathon', '4:00:00', %s, 40.0, %s, %s) RETURNING id",
            (start + timedelta(weeks=4, days=-1), Jsonb(AVAILABILITY), runner_id),
        )
        goal_id = (await cur.fetchone())[0]
        cur = await conn.execute(
            "INSERT INTO training_plans (goal_id, total_weeks, summary, start_date, runner_id)"
            " VALUES (%s, 4, 'Test plan', %s, %s) RETURNING id",
            (goal_id, start, runner_id),
        )
        plan_id = (await cur.fetchone())[0]
        for week in range(1, 5):
            for day, kind, km in WEEK:
                await conn.execute(
                    "INSERT INTO workout_sessions (plan_id, week_number, phase, day_of_week, workout_type, distance_km, pace_zone)"
                    " VALUES (%s, %s, 'taper', %s, %s, %s, 'Z2')",
                    (plan_id, week, day, kind, km),
                )
        await conn.commit()
    return {"goal_id": goal_id, "plan_id": plan_id, "start": start}


async def _ask_for_edit(client, chat_ai, plan_edit_ai, proposal, text="Đổi lịch giúp mình"):
    chat_ai.scripted.append("Để mình xem.\n[[EDIT: " + text + "]]")
    plan_edit_ai.proposal = proposal
    resp = await client.post("/plan-chat/messages", json={"message": text})
    assert resp.status_code == 200, resp.text
    return resp.json()["messages"][1]


async def _workouts(client, plan, week):
    body = (await client.get(f"/plan/{plan['plan_id']}")).json()
    found = next(w for w in body["weeks"] if w["weekNumber"] == week)
    return [(w["day"], w["type"], w["distanceKm"]) for w in found["workouts"]]


SHORTER_THURSDAY = {"summary": "Thu 5 km to 3 km", "weeks": [{"week_number": 3, "workouts": _week(Thu=("easy", 3.0))}]}


async def test_an_edit_is_shown_as_a_difference_and_not_applied_until_confirmed(client, chat_ai, plan_edit_ai, plan):
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, SHORTER_THURSDAY)

    edit = reply["planEdit"]
    assert edit["status"] == "pending"
    assert edit["changes"] == [{
        "week": 3, "day": "Thu",
        "before": [{"type": "easy", "distanceKm": 5.0}],
        "after": [{"type": "easy", "distanceKm": 3.0}],
    }]
    assert "[[EDIT" not in reply["content"]
    assert ("Thu", "easy", 5.0) in await _workouts(client, plan, 3)
    assert (await client.get("/plan-edits")).json() == {"edits": []}


async def test_a_confirmed_edit_is_applied_and_appears_in_the_log(client, chat_ai, plan_edit_ai, plan):
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, SHORTER_THURSDAY)

    resp = await client.post(f"/plan-chat/messages/{reply['id']}/edit/confirm")
    assert resp.status_code == 200, resp.text
    assert resp.json()["edit"]["status"] == "applied"

    assert ("Thu", "easy", 3.0) in await _workouts(client, plan, 3)
    assert ("Thu", "easy", 5.0) in await _workouts(client, plan, 4)  # other weeks untouched
    log = (await client.get("/plan-edits")).json()["edits"]
    assert len(log) == 1
    assert log[0]["status"] == "applied" and log[0]["summary"] == "Thu 5 km to 3 km"
    assert log[0]["changes"][0]["after"] == [{"type": "easy", "distanceKm": 3.0}]
    assert log[0]["decidedAt"]
    # Confirming twice does not apply it again.
    assert (await client.post(f"/plan-chat/messages/{reply['id']}/edit/confirm")).status_code == 409


async def test_a_declined_edit_changes_nothing(client, chat_ai, plan_edit_ai, plan):
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, SHORTER_THURSDAY)

    resp = await client.post(f"/plan-chat/messages/{reply['id']}/edit/decline")
    assert resp.status_code == 200 and resp.json()["edit"]["status"] == "declined"
    assert ("Thu", "easy", 5.0) in await _workouts(client, plan, 3)
    assert (await client.get("/plan-edits")).json() == {"edits": []}
    assert (await client.post(f"/plan-chat/messages/{reply['id']}/edit/confirm")).status_code == 409
    stored = (await client.get("/plan-chat/messages")).json()["messages"]
    assert stored[1]["planEdit"]["status"] == "declined"


async def test_a_message_without_an_edit_cannot_be_confirmed(client, chat_ai, plan):
    resp = await client.post("/plan-chat/messages", json={"message": "chào"})
    reply = resp.json()["messages"][1]
    assert reply["planEdit"] is None
    assert (await client.post(f"/plan-chat/messages/{reply['id']}/edit/confirm")).status_code == 409


async def test_the_edit_step_gets_the_request_and_the_edit_tool(client, chat_ai, plan_edit_ai, plan):
    await _ask_for_edit(client, chat_ai, plan_edit_ai, SHORTER_THURSDAY, text="Tuần 3 thứ Năm chạy 3 km thôi")
    messages, tools = plan_edit_ai.calls[-1]
    assert [t["name"] for t in tools] == ["propose_plan_edit"]
    prompt = "\n".join(m["content"] for m in messages)
    assert "Tuần 3 thứ Năm chạy 3 km thôi" in prompt
    assert "Mon: up to 1 run(s), at most 5 km each, no Quality workouts" in prompt
    # The chat model is told how to ask for an edit.
    assert "[[EDIT:" in chat_ai.chat_calls[-1][0]["content"]


def _edit(week, **changes):
    return {"summary": "change", "weeks": [{"week_number": week, "workouts": _week(**changes)}]}


@pytest.mark.parametrize("proposal,code", [
    (_edit(3, Tue=("easy", 8.0), Sat=("easy", 5.0)), "max_km"),             # Tue allows 5 km
    (_edit(3, Fri=("easy", 3.0), Sat=("easy", 5.0)), "slots"),              # Fri is a rest day
    (_edit(3, Thu=("tempo", 5.0), Wed=("easy", 10.0)), "quality_not_allowed"),
    (_edit(3, Sun=("long", 16.0), Sat=("easy", 4.0)), "long_run"),          # limit 13.5 km
    (_edit(3, Sat=("easy", 12.0)), "load_cap"),                             # 49 km > 45 km
    (_edit(3, Sat=("tempo", 8.0)), "quality_added"),                        # a missed Q is never made up
    (_edit(1, Thu=("easy", 3.0)), "past_day"),                              # last week
    (_edit(9, Thu=("easy", 3.0)), "unknown_week"),
    ({**SHORTER_THURSDAY, "goal_change": {"race_date": "2027-01-01"}}, "goal_change"),
    (_edit(3), "no_change"),
])
async def test_an_edit_that_breaks_a_rule_is_rejected_with_a_reason(client, chat_ai, plan_edit_ai, plan, proposal, code):
    before = [await _workouts(client, plan, w) for w in (1, 3)]
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, proposal)

    edit = reply["planEdit"]
    assert edit["status"] == "rejected"
    assert code in [r["code"] for r in edit["reasons"]]
    assert all(r["text"] for r in edit["reasons"])
    assert (await client.post(f"/plan-chat/messages/{reply['id']}/edit/confirm")).status_code == 409
    assert [await _workouts(client, plan, w) for w in (1, 3)] == before
    assert (await client.get("/plan-edits")).json() == {"edits": []}


async def test_the_coach_sees_why_an_edit_was_refused_on_the_next_turn(client, chat_ai, plan_edit_ai, plan):
    await _ask_for_edit(client, chat_ai, plan_edit_ai, _edit(3, Sat=("easy", 12.0)))
    await client.post("/plan-chat/messages", json={"message": "Sao vậy?"})
    system = chat_ai.chat_calls[-1][0]["content"]
    assert "RECENT PLAN EDITS" in system and "above its Weekly volume of 45" in system


async def test_no_usable_proposal_is_a_rejection_and_the_turn_still_answers(client, chat_ai, plan_edit_ai, plan):
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, None)
    assert reply["content"] == "Để mình xem."
    assert reply["planEdit"]["status"] == "rejected"
    assert reply["planEdit"]["reasons"][0]["code"] == "no_proposal"


async def test_past_weeks_are_never_altered_even_inside_a_wider_edit(client, chat_ai, plan_edit_ai, plan):
    proposal = {"summary": "two weeks", "weeks": [
        {"week_number": 1, "workouts": _week(Mon=("easy", 3.0))},
        {"week_number": 3, "workouts": _week(Thu=("easy", 3.0))},
    ]}
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, proposal)
    assert reply["planEdit"]["status"] == "rejected"
    assert ("Mon", "easy", 5.0) in await _workouts(client, plan, 1)
    assert ("Thu", "easy", 5.0) in await _workouts(client, plan, 3)


async def test_a_day_with_a_matched_run_is_never_altered(client, chat_ai, plan_edit_ai, plan, runner_id):
    today = DAYS[date.today().weekday()]
    async with get_pool().connection() as conn:
        cur = await conn.execute(
            "SELECT id FROM workout_sessions WHERE plan_id = %s AND week_number = 2 AND day_of_week = %s",
            (plan["plan_id"], today),
        )
        row = await cur.fetchone()
        if row is None:  # Friday is a rest day in this Plan
            pytest.skip("no Planned workout today")
        await conn.execute(
            "INSERT INTO activity_analyses (strava_activity_id, matched_workout_id, activity_date, distance_km, runner_id)"
            " VALUES (4242, %s, %s, 5.0, %s)",
            (row[0], date.today(), runner_id),
        )
        await conn.commit()
    kind, km = next((k, d) for d_, k, d in WEEK if d_ == today)
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, _edit(2, **{today: (kind, km - 1)}))
    assert "matched_day" in [r["code"] for r in reply["planEdit"]["reasons"]]


async def test_an_edit_is_checked_again_when_confirmed(client, chat_ai, plan_edit_ai, plan):
    first = await _ask_for_edit(client, chat_ai, plan_edit_ai, SHORTER_THURSDAY)
    second = await _ask_for_edit(client, chat_ai, plan_edit_ai, _edit(3, Thu=("easy", 4.0)))
    assert (await client.post(f"/plan-chat/messages/{first['id']}/edit/confirm")).status_code == 200

    resp = await client.post(f"/plan-chat/messages/{second['id']}/edit/confirm")
    assert resp.status_code == 409
    assert resp.json()["detail"]["edit"]["reasons"][0]["code"] == "stale"
    assert ("Thu", "easy", 3.0) in await _workouts(client, plan, 3)


async def test_a_one_off_override_works_once_and_is_logged(client, chat_ai, plan_edit_ai, plan):
    over = {**_edit(3, Tue=("easy", 8.0), Sat=("easy", 5.0)), "override": {"week_number": 3, "day": "Tue"}}
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, over, text="Tuần 3 thứ Ba mình muốn chạy 8 km, chỉ lần này")

    edit = reply["planEdit"]
    assert edit["status"] == "pending"
    assert edit["override"]["week"] == 3 and edit["override"]["day"] == "Tue"
    assert [r["code"] for r in edit["override"]["limits"]] == ["max_km"]
    assert (await client.post(f"/plan-chat/messages/{reply['id']}/edit/confirm")).status_code == 200
    assert ("Tue", "easy", 8.0) in await _workouts(client, plan, 3)
    log = (await client.get("/plan-edits")).json()["edits"]
    assert log[0]["override"]["day"] == "Tue"

    # The week's override is spent: a second one in week 3 is refused.
    again = {**_edit(3, Tue=("easy", 8.0), Mon=("easy", 7.0), Sat=("easy", 3.0)), "override": {"week_number": 3, "day": "Mon"}}
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, again)
    assert "override_used" in [r["code"] for r in reply["planEdit"]["reasons"]]
    # Weekly availability itself did not change: week 4 still allows 5 km on Tuesday.
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, _edit(4, Tue=("easy", 8.0), Sat=("easy", 5.0)))
    assert "max_km" in [r["code"] for r in reply["planEdit"]["reasons"]]


async def test_an_override_never_excuses_the_long_run_or_load_rules(client, chat_ai, plan_edit_ai, plan):
    over = {**_edit(3, Sat=("easy", 12.0)), "override": {"week_number": 3, "day": "Sat"}}
    reply = await _ask_for_edit(client, chat_ai, plan_edit_ai, over)
    assert reply["planEdit"]["status"] == "rejected"
    assert "load_cap" in [r["code"] for r in reply["planEdit"]["reasons"]]
