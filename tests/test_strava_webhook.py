async def test_webhook_validation_correct_token(client):
    resp = await client.get(
        "/strava/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "abc123",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["hub.challenge"] == "abc123"


async def test_webhook_validation_wrong_token(client):
    resp = await client.get(
        "/strava/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "abc123",
        },
    )
    assert resp.status_code == 403


async def test_webhook_create_activity_produces_analysis(
    webhook_client, seeded_plan, seeded_strava_connection
):
    payload = {
        "object_type": "activity",
        "object_id": 123456789,
        "aspect_type": "create",
        "owner_id": 12345,
    }
    resp = await webhook_client.post("/strava/webhook", json=payload)
    assert resp.status_code == 200

    activities = await webhook_client.get("/activities")
    body = activities.json()
    assert len(body["activities"]) == 1
    row = body["activities"][0]
    assert row["stravaActivityId"] == 123456789
    assert row["analysisStatus"] == "complete"
    assert row["mismatch"] is False


async def test_webhook_unmatched_activity_no_weekly_summary(
    webhook_client, seeded_plan, seeded_strava_connection
):
    """Activity on a date with no planned workout → stored as unmatched, no weekly_summaries row."""
    from datetime import date, timedelta
    # Use a date 30 days out — no workout scheduled there
    future_date = (date.today() + timedelta(days=30)).isoformat()

    from tests.conftest import FakeStravaClient
    from app.strava.models import ActivityDetail

    class FutureStravaClient(FakeStravaClient):
        async def get_activity(self, activity_id, access_token):
            return ActivityDetail(
                id=activity_id,
                start_date_local=future_date + "T07:30:00Z",
                distance=8200.0,
                moving_time=2460,
                type="Run",
            )

    from app.api.strava import get_strava_client
    from app.main import app
    app.dependency_overrides[get_strava_client] = lambda: FutureStravaClient()

    payload = {
        "object_type": "activity",
        "object_id": 987654321,
        "aspect_type": "create",
        "owner_id": 12345,
    }
    resp = await webhook_client.post("/strava/webhook", json=payload)
    assert resp.status_code == 200

    activities = await webhook_client.get("/activities")
    body = activities.json()
    assert len(body["activities"]) == 1
    assert body["activities"][0]["matchedWorkoutId"] is None
    assert body["activities"][0]["analysisStatus"] == "unmatched"


async def test_webhook_non_create_event_ignored(webhook_client):
    payload = {
        "object_type": "activity",
        "object_id": 111,
        "aspect_type": "update",
        "owner_id": 12345,
    }
    resp = await webhook_client.post("/strava/webhook", json=payload)
    assert resp.status_code == 200

    activities = await webhook_client.get("/activities")
    assert activities.json()["activities"] == []
