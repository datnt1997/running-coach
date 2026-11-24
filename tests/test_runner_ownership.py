"""Every table is owned by one Runner; another Runner never sees or touches it."""
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest_asyncio
from httpx import ASGITransport

from app.db.connection import get_pool
from app.main import app
from tests.availability import week_with_days
from tests.conftest import _seed_plan, make_runner, sign_in

FRIEND = "friend@example.com"


@pytest_asyncio.fixture
async def friend_client(webhook_client):
    """A second signed-in Runner (own cookie jar) on the same app and database."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        await sign_in(ac, FRIEND)
        yield ac


async def _insert_connection(runner_id, athlete_id):
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO strava_connections (strava_athlete_id, access_token, refresh_token, expires_at, runner_id)"
            " VALUES (%s, 'a', 'r', %s, %s)",
            (athlete_id, datetime(2099, 1, 1, tzinfo=timezone.utc), runner_id),
        )
        await conn.commit()


async def _count(table, runner_id):
    async with get_pool().connection() as conn:
        cur = await conn.execute(f"SELECT count(*) FROM {table} WHERE runner_id = %s", (runner_id,))
        return (await cur.fetchone())[0]


def _activity_event(athlete_id, activity_id=555):
    return {"object_type": "activity", "object_id": activity_id,
            "aspect_type": "create", "owner_id": athlete_id}


async def test_goals_and_plans_are_invisible_to_another_runner(client, friend_client, seeded_plan):
    goal_id, plan_id = str(seeded_plan["goal_id"]), str(seeded_plan["plan_id"])

    assert [g["goalId"] for g in (await client.get("/goals")).json()["goals"]] == [goal_id]
    assert (await friend_client.get("/goals")).json() == {"goals": []}

    assert (await client.get(f"/plan/{plan_id}")).status_code == 200
    assert (await friend_client.get(f"/plan/{plan_id}")).status_code == 404
    assert (await friend_client.get(f"/goal/{goal_id}/plan")).status_code == 404


async def test_another_runner_cannot_delete_a_goal(client, friend_client, seeded_plan):
    goal_id = str(seeded_plan["goal_id"])
    assert (await friend_client.delete(f"/goal/{goal_id}")).status_code == 404
    assert len((await client.get("/goals")).json()["goals"]) == 1
    assert (await client.delete(f"/goal/{goal_id}")).status_code == 200


async def test_a_new_goal_belongs_to_its_creator_only(client, friend_client):
    resp = await friend_client.post("/goal", json={
        "distance": "half_marathon", "targetTime": "1:55:00",
        "raceDate": (date.today() + timedelta(weeks=16)).isoformat(), "vdot": 40.0,
        "weeklyKm": 40, "longestRunKm": 18, "weeklyAvailability": week_with_days(4),
    })
    assert resp.status_code == 202
    goal_id = resp.json()["goalId"]

    assert len((await friend_client.get("/goals")).json()["goals"]) == 1
    assert (await client.get("/goals")).json() == {"goals": []}
    assert (await client.get(f"/goal/{goal_id}/plan")).status_code == 404
    assert (await friend_client.get(f"/goal/{goal_id}/plan")).json()["status"] == "ready"


async def test_activities_and_summaries_are_invisible_to_another_runner(
    webhook_client, friend_client, seeded_plan, seeded_strava_connection
):
    resp = await webhook_client.post("/strava/webhook", json=_activity_event(12345))
    assert resp.status_code == 200

    assert len((await webhook_client.get("/activities")).json()["activities"]) == 1
    assert (await webhook_client.get("/weekly-summary")).status_code == 200

    assert (await friend_client.get("/activities")).json() == {"activities": []}
    assert (await friend_client.get("/weekly-summary")).status_code == 404


async def test_strava_connection_is_per_runner(client, friend_client, seeded_strava_connection):
    assert (await client.get("/strava/status")).json()["connected"] is True
    assert (await friend_client.get("/strava/status")).json()["connected"] is False

    await friend_client.post("/strava/disconnect")
    assert (await client.get("/strava/status")).json()["connected"] is True

    await client.post("/strava/disconnect")
    assert (await client.get("/strava/status")).json()["connected"] is False


async def test_connecting_an_athlete_already_held_by_another_runner_is_refused(
    client, friend_client, seeded_strava_connection, fake_strava_client
):
    from app.api.strava import _CSRF_COOKIE, get_strava_client

    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client  # athlete 12345
    connect = await friend_client.get("/strava/connect", follow_redirects=False)
    state = connect.cookies[_CSRF_COOKIE]
    resp = await friend_client.get(
        f"/strava/callback?code=c&state={state}", follow_redirects=False, cookies={_CSRF_COOKIE: state}
    )
    assert resp.status_code == 409
    assert (await friend_client.get("/strava/status")).json()["connected"] is False
    assert (await client.get("/strava/status")).json()["athlete_id"] == 12345


async def test_webhook_updates_only_the_athletes_runner(
    webhook_client, friend_client, seeded_plan, seeded_strava_connection, runner_id
):
    friend_id = await make_runner(FRIEND)
    await _seed_plan(friend_id)
    await _insert_connection(friend_id, 999)

    resp = await webhook_client.post("/strava/webhook", json=_activity_event(999))
    assert resp.status_code == 200

    assert await _count("activity_analyses", friend_id) == 1
    assert await _count("weekly_summaries", friend_id) == 1
    assert await _count("activity_analyses", runner_id) == 0
    assert await _count("weekly_summaries", runner_id) == 0
    assert len((await friend_client.get("/activities")).json()["activities"]) == 1
    assert (await webhook_client.get("/activities")).json() == {"activities": []}


async def test_webhook_for_an_unknown_athlete_is_acknowledged_and_changes_nothing(
    webhook_client, seeded_plan, seeded_strava_connection, runner_id
):
    resp = await webhook_client.post("/strava/webhook", json=_activity_event(424242))
    assert resp.status_code == 200

    async with get_pool().connection() as conn:
        for table in ("activity_analyses", "weekly_summaries"):
            cur = await conn.execute(f"SELECT count(*) FROM {table}")
            assert (await cur.fetchone())[0] == 0, table
        cur = await conn.execute("SELECT access_token FROM strava_connections")
        assert [r[0] for r in await cur.fetchall()] == ["test_access"]


async def test_a_foreign_plan_id_leaks_nothing_through_any_repository(
    webhook_client, friend_client, seeded_plan, seeded_strava_connection
):
    from app.db.repositories import (
        ActivityAnalysisRepository, PlanRepository, WeeklySummaryRepository,
    )
    import pytest

    assert (await webhook_client.post("/strava/webhook", json=_activity_event(12345))).status_code == 200
    plan_id = seeded_plan["plan_id"]
    friend = await make_runner(FRIEND)
    activity_date = date.today()

    assert (await friend_client.get(f"/plan/{plan_id}")).status_code == 404
    async with get_pool().connection() as conn:
        plans = PlanRepository(conn, friend)
        assert await plans.get_plan(plan_id) is None
        assert await plans.get_workouts_for_date(plan_id, activity_date) == []
        assert await ActivityAnalysisRepository(conn, friend).list_for_week(plan_id, 1) == []
        summaries = WeeklySummaryRepository(conn, friend)
        assert await summaries.get_by_week(plan_id, 1) is None
        with pytest.raises(LookupError):
            await summaries.upsert(plan_id, 1, "intruder")


async def test_plan_chat_is_private_to_its_runner(client, friend_client):
    from app.ai.factory import get_chat_ai_client_dep
    from tests.conftest import FakePlanChatAIClient

    fake = FakePlanChatAIClient()
    app.dependency_overrides[get_chat_ai_client_dep] = lambda: fake
    await client.post("/plan-chat/messages", json={"message": "bí mật của tôi"})

    assert (await friend_client.get("/plan-chat/messages")).json() == {"messages": []}
    await friend_client.post("/plan-chat/messages", json={"message": "tin của bạn"})
    assert "bí mật của tôi" not in "".join(m["content"] for m in fake.calls[-1])
    mine = (await client.get("/plan-chat/messages")).json()["messages"]
    assert [m["content"] for m in mine] == ["bí mật của tôi", "reply 1"]


async def test_profiles_are_private_to_their_runner(client, friend_client):
    await client.put("/profile", json={"maxHr": 190, "restingHr": 50})

    assert (await friend_client.get("/profile")).json()["maxHr"] is None
    await friend_client.put("/profile", json={"maxHr": 180})
    assert (await client.get("/profile")).json()["maxHr"] == 190
    assert (await friend_client.get("/profile")).json()["maxHr"] == 180


async def test_profile_facts_are_private_to_their_runner(client, friend_client):
    from app.ai.factory import get_chat_ai_client_dep
    from tests.conftest import FakePlanChatAIClient

    fake = FakePlanChatAIClient()
    app.dependency_overrides[get_chat_ai_client_dep] = lambda: fake
    fake.scripted.append("Ghi nhớ nhé?\n[[REMEMBER: gối trái đau]]")
    reply = (await client.post("/plan-chat/messages", json={"message": "gối đau"})).json()["messages"][1]
    url = f"/plan-chat/messages/{reply['id']}/proposal"

    # Another Runner cannot confirm or decline a proposal that is not theirs.
    assert (await friend_client.post(f"{url}/confirm")).status_code == 404
    assert (await friend_client.post(f"{url}/decline")).status_code == 404
    assert (await client.post(f"{url}/confirm")).status_code == 200
    fact_id = (await client.get("/profile-facts")).json()["facts"][0]["id"]

    assert (await friend_client.get("/profile-facts")).json() == {"facts": []}
    assert (await friend_client.put(f"/profile-facts/{fact_id}", json={"text": "hack"})).status_code == 404
    assert (await friend_client.delete(f"/profile-facts/{fact_id}")).status_code == 404
    assert [f["text"] for f in (await client.get("/profile-facts")).json()["facts"]] == ["gối trái đau"]

    await friend_client.post("/plan-chat/messages", json={"message": "chào"})
    assert "gối trái đau" not in "".join(m["content"] for m in fake.calls[-1])


async def test_the_rolling_summary_is_private_to_its_runner(client, friend_client):
    from app.ai.factory import get_chat_ai_client_dep
    from tests.conftest import FakePlanChatAIClient

    fake = FakePlanChatAIClient()
    app.dependency_overrides[get_chat_ai_client_dep] = lambda: fake
    await client.post("/plan-chat/messages", json={"message": "bí mật cũ của tôi"})
    for i in range(35):
        await client.post("/plan-chat/messages", json={"message": f"tin {i}"})
    assert "bí mật cũ của tôi" in "".join(m["content"] for m in fake.chat_calls[-1])

    await friend_client.post("/plan-chat/messages", json={"message": "chào"})
    assert "bí mật cũ của tôi" not in "".join(m["content"] for m in fake.chat_calls[-1])
    assert "SUMMARY" not in "".join(m["content"] for m in fake.chat_calls[-1])
