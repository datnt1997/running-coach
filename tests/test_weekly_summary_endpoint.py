async def test_weekly_summary_no_plan_returns_404(client):
    resp = await client.get("/weekly-summary?week_number=1")
    assert resp.status_code == 404


async def test_weekly_summary_no_summary_yet_returns_404(webhook_client, seeded_plan):
    resp = await webhook_client.get("/weekly-summary?week_number=1")
    assert resp.status_code == 404


async def test_weekly_summary_after_webhook(
    webhook_client, seeded_plan, seeded_strava_connection
):
    await webhook_client.post(
        "/strava/webhook",
        json={
            "object_type": "activity",
            "object_id": 777,
            "aspect_type": "create",
            "owner_id": 12345,
        },
    )

    resp = await webhook_client.get("/weekly-summary?week_number=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["weekNumber"] == 1
    assert isinstance(body["summary"], str) and body["summary"]
    assert isinstance(body["sessions"], list)
    assert len(body["sessions"]) == 1

    session = body["sessions"][0]
    assert session["planned"]["type"] == "easy"
    assert session["actual"]["distanceKm"] == pytest.approx(8.2, abs=0.01)
    assert session["mismatch"] is False


import pytest
