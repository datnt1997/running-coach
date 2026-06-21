import os

# Provide test defaults for Strava env vars BEFORE any app module is imported,
# so validate_config() does not reject them during lifespan startup.
os.environ.setdefault("STRAVA_CLIENT_ID", "test_client_id")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("STRAVA_WEBHOOK_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("STRAVA_REDIRECT_URI", "http://localhost:8000/strava/callback")

import pathlib
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from psycopg import AsyncConnection

from app.ai.client import AIResponse, TokenUsage, ToolCall
from app.ai.factory import get_ai_client_dep
from app.config import DATABASE_URL
from app.db import connection as db_connection
from app.main import app
from app.strava.models import ActivityDetail, TokenSet

MIGRATION_001 = (
    pathlib.Path(__file__).resolve().parent.parent
    / "app" / "db" / "migrations" / "001_initial.sql"
)
MIGRATION_002 = (
    pathlib.Path(__file__).resolve().parent.parent
    / "app" / "db" / "migrations" / "002_strava.sql"
)
MIGRATION_003 = (
    pathlib.Path(__file__).resolve().parent.parent
    / "app" / "db" / "migrations" / "003_plan_status.sql"
)

_ALL_TABLES = (
    "weekly_summaries, activity_analyses, strava_connections, "
    "workout_sessions, training_plans, user_goals"
)


# ---------------------------------------------------------------------------
# Fake AI clients
# ---------------------------------------------------------------------------

def _build_fake_plan_arguments(
    total_weeks: int = 16,
    phase_breakdown: dict[str, int] | None = None,
    base_distance: float = 30.0,
) -> dict:
    if phase_breakdown is None:
        phase_breakdown = {"base": 6, "build": 5, "peak": 3, "taper": 2}

    phase_sequence: list[str] = []
    for phase in ("base", "build", "peak", "taper"):
        phase_sequence.extend([phase] * phase_breakdown[phase])
    assert len(phase_sequence) == total_weeks

    weeks = []
    weekly_total = base_distance
    for i, phase in enumerate(phase_sequence, start=1):
        if phase == "taper":
            weekly_total = round(weekly_total * 0.75, 2)
        else:
            weekly_total = round(weekly_total * 1.08, 2)

        easy = round(weekly_total * 0.2, 2)
        workouts = [
            {"day": "Mon", "type": "easy", "distance_km": easy, "pace_zone": "Z2", "notes": "Conversational pace"},
            {"day": "Tue", "type": "tempo" if phase != "base" else "easy", "distance_km": easy, "pace_zone": "Z3" if phase != "base" else "Z2", "notes": "Quality session"},
            {"day": "Wed", "type": "easy", "distance_km": easy, "pace_zone": "Z2", "notes": "Recovery run"},
            {"day": "Thu", "type": "long", "distance_km": round(weekly_total - 3 * easy, 2), "pace_zone": "Z2", "notes": "Long run"},
        ]
        weeks.append({"week_number": i, "phase": phase, "workouts": workouts})

    return {
        "summary": f"{total_weeks}-week plan with full periodization.",
        "total_weeks": total_weeks,
        "phase_breakdown": phase_breakdown,
        "weeks": weeks,
    }


class FakeAIClient:
    def __init__(self, total_weeks: int = 16, phase_breakdown=None):
        self.call_count = 0
        self._total_weeks = total_weeks
        self._phase_breakdown = phase_breakdown

    async def generate(self, messages, tools=None, response_format=None) -> AIResponse:
        self.call_count += 1
        arguments = _build_fake_plan_arguments(
            total_weeks=self._total_weeks,
            phase_breakdown=self._phase_breakdown,
        )
        return AIResponse(
            content="",
            tool_calls=[ToolCall(name="generate_training_plan", arguments=arguments)],
            usage=TokenUsage(input_tokens=100, output_tokens=200),
        )


class FakeAnalysisAIClient:
    """Handles both plan generation and activity analysis tool calls."""

    async def generate(self, messages, tools=None, response_format=None) -> AIResponse:
        if tools:
            tool_names = [t["name"] for t in tools]
            if "analyze_activity" in tool_names:
                return AIResponse(
                    content="",
                    tool_calls=[
                        ToolCall(
                            name="analyze_activity",
                            arguments={
                                "pace_adherence": "on_target",
                                "hr_adherence": "on_target",
                                "load_adherence": "on_target",
                                "rationale": "Good effort within prescribed zones.",
                            },
                        )
                    ],
                )
            if "generate_training_plan" in tool_names:
                return AIResponse(
                    content="",
                    tool_calls=[
                        ToolCall(
                            name="generate_training_plan",
                            arguments=_build_fake_plan_arguments(),
                        )
                    ],
                    usage=TokenUsage(input_tokens=100, output_tokens=200),
                )
        # Weekly summary (no tools)
        return AIResponse(content="Good week overall — pace and HR adherence were solid.")


# ---------------------------------------------------------------------------
# Fake Strava client
# ---------------------------------------------------------------------------

class FakeStravaClient:
    async def exchange_code(self, code: str) -> TokenSet:
        return TokenSet(
            access_token="fake_access",
            refresh_token="fake_refresh",
            expires_at=9999999999,
            athlete_id=12345,
        )

    async def refresh_token(self, refresh_token_value: str) -> TokenSet:
        return TokenSet(
            access_token="fake_access_new",
            refresh_token="fake_refresh_new",
            expires_at=9999999999,
        )

    async def get_activity(self, activity_id: int, access_token: str) -> ActivityDetail:
        today = date.today()
        return ActivityDetail(
            id=activity_id,
            start_date_local=today.isoformat() + "T07:30:00Z",
            distance=8200.0,
            moving_time=2460,
            average_heartrate=145.0,
            type="Run",
        )


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_pool():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not configured")

    async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
        await conn.execute(f"DROP TABLE IF EXISTS {_ALL_TABLES} CASCADE")
        await conn.execute(MIGRATION_001.read_text())
        await conn.execute(MIGRATION_002.read_text())
        await conn.execute(MIGRATION_003.read_text())

    pool = await db_connection.init_pool()
    try:
        yield pool
    finally:
        await db_connection.close_pool()
        async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {_ALL_TABLES} CASCADE")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def fake_ai_client():
    return FakeAIClient()


@pytest_asyncio.fixture
async def fake_analysis_ai_client():
    return FakeAnalysisAIClient()


@pytest_asyncio.fixture
async def fake_strava_client():
    return FakeStravaClient()


@pytest_asyncio.fixture
async def client(db_pool, fake_ai_client):
    app.dependency_overrides[get_ai_client_dep] = lambda: fake_ai_client
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def webhook_client(db_pool, fake_analysis_ai_client, fake_strava_client):
    from app.api.strava import get_strava_client
    app.dependency_overrides[get_ai_client_dep] = lambda: fake_analysis_ai_client
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_strava_connection(db_pool):
    """Insert a Strava connection that never expires."""
    from app.db.connection import get_pool
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO strava_connections
                    (strava_athlete_id, access_token, refresh_token, expires_at)
                VALUES (12345, 'test_access', 'test_refresh', %s)
                """,
                (datetime(2099, 1, 1, tzinfo=timezone.utc),),
            )
        await conn.commit()


@pytest_asyncio.fixture
async def seeded_plan(db_pool):
    """Insert a training plan with a workout scheduled for today."""
    from app.db.connection import get_pool
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday of this week
    day_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    today_abbrev = day_map[today.weekday()]

    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO user_goals (distance, target_time, race_date, fitness_level, days_per_week) "
                "VALUES ('half_marathon', '2:00:00', %s, 'intermediate', 4) RETURNING id",
                ((today + timedelta(weeks=16)),),
            )
            goal_id = (await cur.fetchone())[0]

            await cur.execute(
                "INSERT INTO training_plans (goal_id, total_weeks, summary, start_date) "
                "VALUES (%s, 4, 'Test plan', %s) RETURNING id",
                (goal_id, week_start),
            )
            plan_id = (await cur.fetchone())[0]

            await cur.execute(
                "INSERT INTO workout_sessions "
                "  (plan_id, week_number, phase, day_of_week, workout_type, distance_km, pace_zone) "
                "VALUES (%s, 1, 'base', %s, 'easy', 8.0, 'Z2') RETURNING id",
                (plan_id, today_abbrev),
            )
            workout_id = (await cur.fetchone())[0]
        await conn.commit()

    return {"plan_id": plan_id, "workout_id": workout_id, "date": today, "week_start": week_start}
