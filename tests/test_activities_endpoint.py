from datetime import date, timedelta, timezone
from datetime import datetime


async def test_activities_no_plan_returns_empty(client):
    resp = await client.get("/activities")
    assert resp.status_code == 200
    assert resp.json()["activities"] == []


async def test_activities_returns_seeded_row(webhook_client, seeded_plan, seeded_strava_connection):
    # Trigger a webhook event so activity_analyses gets a row
    await webhook_client.post(
        "/strava/webhook",
        json={
            "object_type": "activity",
            "object_id": 555,
            "aspect_type": "create",
            "owner_id": 12345,
        },
    )

    resp = await webhook_client.get("/activities")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["activities"]) == 1
    row = body["activities"][0]
    assert row["stravaActivityId"] == 555
    assert row["date"] == date.today().isoformat()
    assert row["distanceKm"] == pytest.approx(8.2, abs=0.01)


async def test_activities_week_filter(webhook_client, seeded_plan, seeded_strava_connection):
    await webhook_client.post(
        "/strava/webhook",
        json={"object_type": "activity", "object_id": 666, "aspect_type": "create", "owner_id": 12345},
    )

    resp_week1 = await webhook_client.get("/activities?week=1")
    assert resp_week1.status_code == 200
    assert len(resp_week1.json()["activities"]) == 1

    resp_week2 = await webhook_client.get("/activities?week=2")
    assert resp_week2.status_code == 200
    assert resp_week2.json()["activities"] == []


import pytest
