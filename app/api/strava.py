import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from psycopg import AsyncConnection
from pydantic import BaseModel

from app.agent.analyzer import AnalysisGenerationError, analyze_activity, build_weekly_summary
from app.agent.matching import match_activity_to_workout
from app.ai.client import AIClient
from app.ai.factory import get_ai_client_dep
from app.config import STRAVA_CLIENT_ID, STRAVA_REDIRECT_URI, STRAVA_WEBHOOK_VERIFY_TOKEN
from app.db.connection import get_db
from app.db.repositories import (
    ActivityAnalysisRepository,
    PlanRepository,
    StravaConnectionRepository,
    WeeklySummaryRepository,
)
from app.strava.client import StravaClient, get_valid_access_token

logger = logging.getLogger(__name__)

router = APIRouter()

_CSRF_COOKIE = "strava_oauth_state"
_CSRF_MAX_AGE = 600  # seconds


def get_strava_client() -> StravaClient:
    return StravaClient()


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------


@router.get("/strava/connect")
async def strava_connect() -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "redirect_uri": STRAVA_REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "activity:read_all",
        "state": state,
    }
    url = f"https://www.strava.com/oauth/authorize?{urlencode(params)}"
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(_CSRF_COOKIE, state, httponly=True, max_age=_CSRF_MAX_AGE, samesite="lax")
    return response


@router.get("/strava/callback")
async def strava_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncConnection = Depends(get_db),
    strava_client: StravaClient = Depends(get_strava_client),
) -> RedirectResponse:
    expected = request.cookies.get(_CSRF_COOKIE)
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=403, detail="Invalid OAuth state")

    tokens = await strava_client.exchange_code(code)
    repo = StravaConnectionRepository(db)
    await repo.upsert(
        athlete_id=tokens.athlete_id,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_at=datetime.fromtimestamp(tokens.expires_at, tz=timezone.utc),
    )
    await db.commit()

    response = RedirectResponse(url="/?connected=1", status_code=302)
    response.delete_cookie(_CSRF_COOKIE)
    return response


@router.get("/strava/status")
async def strava_status(db: AsyncConnection = Depends(get_db)) -> dict:
    row = await StravaConnectionRepository(db).get()
    if row is None:
        return {"connected": False, "athlete_id": None}
    return {"connected": True, "athlete_id": row["strava_athlete_id"]}


@router.post("/strava/disconnect")
async def strava_disconnect(db: AsyncConnection = Depends(get_db)) -> dict:
    await StravaConnectionRepository(db).delete()
    await db.commit()
    return {"connected": False}


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


@router.get("/strava/webhook")
async def strava_webhook_validate(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> dict:
    if hub_verify_token != STRAVA_WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}


class _WebhookEvent(BaseModel):
    object_type: str
    object_id: int
    aspect_type: str
    owner_id: int
    subscription_id: int | None = None
    event_time: int | None = None
    updates: dict = {}


@router.post("/strava/webhook")
async def strava_webhook_event(
    event: _WebhookEvent,
    background_tasks: BackgroundTasks,
    strava_client: StravaClient = Depends(get_strava_client),
    ai_client: AIClient = Depends(get_ai_client_dep),
) -> Response:
    if event.aspect_type == "create" and event.object_type == "activity":
        background_tasks.add_task(_process_activity, event.object_id, strava_client, ai_client)
    return Response(status_code=200)


async def _process_activity(
    activity_id: int,
    strava_client: StravaClient,
    ai_client: AIClient,
) -> None:
    from app.db.connection import get_pool

    pool = get_pool()
    async with pool.connection() as conn:
        try:
            access_token = await get_valid_access_token(conn, strava_client)
            activity = await strava_client.get_activity(activity_id, access_token)
            activity_date = date.fromisoformat(activity.start_date_local[:10])

            plan_repo = PlanRepository(conn)
            plan_id = await plan_repo.get_latest_plan_id()
            if plan_id is None:
                logger.warning("No training plan found; skipping activity %s", activity_id)
                return

            candidates = await plan_repo.get_workouts_for_date(plan_id, activity_date)
            match = match_activity_to_workout(activity, candidates)

            avg_pace: timedelta | None = None
            if activity.distance > 0:
                avg_pace = timedelta(seconds=int(activity.moving_time / (activity.distance / 1000)))

            avg_hr_zone = _hr_zone(activity.average_heartrate)
            pace_adh = hr_adh = load_adh = None

            if match.matched and match.workout is not None:
                try:
                    result = await analyze_activity(match.workout, activity, ai_client)
                    pace_adh = result.get("pace_adherence")
                    hr_adh = result.get("hr_adherence")
                    load_adh = result.get("load_adherence")
                except AnalysisGenerationError as exc:
                    logger.error("Analysis failed for activity %s: %s", activity_id, exc)

            analysis_repo = ActivityAnalysisRepository(conn)
            await analysis_repo.insert(
                strava_activity_id=activity_id,
                matched_workout_id=match.workout.id if match.workout else None,
                activity_date=activity_date,
                distance_km=activity.distance / 1000,
                avg_pace_per_km=avg_pace,
                avg_hr_zone=avg_hr_zone,
                pace_adherence=pace_adh,
                hr_adherence=hr_adh,
                load_adherence=load_adh,
                mismatch=match.mismatch,
            )

            if match.matched and match.workout is not None:
                try:
                    summary = await build_weekly_summary(
                        plan_id, match.workout.week_number, conn, ai_client
                    )
                    await WeeklySummaryRepository(conn).upsert(
                        plan_id, match.workout.week_number, summary
                    )
                except Exception as exc:
                    logger.error("Weekly summary failed: %s", exc)

            await conn.commit()

        except Exception as exc:
            logger.error("Error processing activity %s: %s", activity_id, exc, exc_info=True)


def _hr_zone(bpm: float | None) -> str | None:
    if bpm is None:
        return None
    pct = bpm / 180  # default HRmax estimate
    if pct < 0.65:
        return "Z1"
    if pct < 0.75:
        return "Z2"
    if pct < 0.85:
        return "Z3"
    if pct < 0.92:
        return "Z4"
    return "Z5"
