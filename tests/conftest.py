import asyncio
import json
import os

# Provide test defaults for Strava env vars BEFORE any app module is imported,
# so validate_config() does not reject them during lifespan startup.
os.environ.setdefault("STRAVA_CLIENT_ID", "test_client_id")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("STRAVA_WEBHOOK_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("STRAVA_REDIRECT_URI", "http://localhost:8000/strava/callback")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-not-for-production")
os.environ["COOKIE_SECURE"] = "false"  # TestClient talks plain http, so a Secure cookie would not come back
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ["ALLOWED_EMAILS"] = "runner@example.com, Friend@Example.com"

# Tests DROP all tables, so they must never see the dev DATABASE_URL from .env.
# Point the app at TEST_DATABASE_URL (which must name a *_test database), or at
# an empty value so DB tests skip. load_dotenv() does not override existing vars.
from dotenv import load_dotenv

load_dotenv()  # so TEST_DATABASE_URL can live in .env
_TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if _TEST_DATABASE_URL:
    _db_name = _TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
    if not _db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests: TEST_DATABASE_URL database '{_db_name}' "
            "must end with '_test' (tests drop all tables)."
        )
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

import pathlib
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from app.agent.plan_chat import SUMMARY_SYSTEM_PROMPT
from app.ai.client import AIResponse, TokenUsage, ToolCall
from app.ai.factory import get_ai_client_dep
from app.auth import GoogleIdentity, InvalidGoogleToken, get_google_verifier
from app.config import DATABASE_URL
from app.db import connection as db_connection
from app.main import app
from app.strava.models import ActivityDetail, AthleteProfile, RecentActivity, TokenSet

# Every migration, applied in filename order. Adding a file here is automatic.
MIGRATIONS = sorted(
    (pathlib.Path(__file__).resolve().parent.parent / "app" / "db" / "migrations").glob("*.sql")
)

_FOUR_DAY_AVAILABILITY = [
    {"day": d, "slots": 1 if d in ("Mon", "Wed", "Fri", "Sat") else 0,
     "maxKm": None, "qualityAllowed": True}
    for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
]

_ALL_TABLES = (
    "chat_summaries, profile_facts, chat_messages, weekly_summaries, activity_analyses, strava_connections, "
    "workout_sessions, training_plans, user_goals, runner_profiles, runners"
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
    weekly_volume = base_distance
    for i, phase in enumerate(phase_sequence, start=1):
        if phase == "taper":
            weekly_volume = round(weekly_volume * 0.75, 2)
        else:
            weekly_volume = round(weekly_volume * 1.08, 2)

        easy = round(weekly_volume * 0.2, 2)
        workouts = [
            {"day": "Mon", "type": "easy", "distance_km": easy, "pace_zone": "Z2", "notes": "Conversational pace"},
            {"day": "Tue", "type": "tempo" if phase != "base" else "easy", "distance_km": easy, "pace_zone": "Z3" if phase != "base" else "Z2", "notes": "Quality session"},
            {"day": "Wed", "type": "easy", "distance_km": easy, "pace_zone": "Z2", "notes": "Recovery run"},
            {"day": "Thu", "type": "long", "distance_km": round(weekly_volume - 3 * easy, 2), "pace_zone": "Z2", "notes": "Long run"},
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
        self.last_messages = None
        self._total_weeks = total_weeks
        self._phase_breakdown = phase_breakdown

    async def generate(self, messages, tools=None, response_format=None) -> AIResponse:
        self.call_count += 1
        self.last_messages = messages
        arguments = _build_fake_plan_arguments(
            total_weeks=self._total_weeks,
            phase_breakdown=self._phase_breakdown,
        )
        return AIResponse(
            content="",
            tool_calls=[ToolCall(name="generate_training_plan", arguments=arguments)],
            usage=TokenUsage(input_tokens=100, output_tokens=200),
        )


class FakeFitnessChatAIClient:
    """Returns a plain follow-up question by default, or a signals JSON block.

    `signals` overrides or (with None values dropped via `drop`) removes keys.
    """

    def __init__(self, classify: bool = False, signals: dict | None = None, drop: tuple = ()):
        self.classify = classify
        self.signals = {
            "race_distance": "10k", "race_time": "52:00",
            "weekly_km": 40, "longest_run_km": 18, **(signals or {}),
        }
        for key in drop:
            self.signals.pop(key, None)
        self.calls: list[list[dict]] = []

    async def generate(self, messages, tools=None, response_format=None) -> AIResponse:
        self.calls.append(messages)
        if self.classify:
            content = (
                "Based on everything you've shared, you're in great shape for this plan!\n\n"
                "```json\n" + json.dumps(self.signals) + "\n```"
            )
        else:
            content = "What's your most recent race time, and what distance was it?"
        return AIResponse(content=content, usage=TokenUsage(input_tokens=50, output_tokens=30))


class FakePlanChatAIClient:
    """Records every prompt it receives; replies "reply N". `fail` makes calls raise."""

    def __init__(self):
        self.calls: list[list[dict]] = []
        self.fail = False
        self.fail_summary = False
        self.delay = 0.0
        self.scripted: list[str] = []  # replies to give next, before "reply N"

    @staticmethod
    def is_summary_call(messages) -> bool:
        return messages[0]["content"] == SUMMARY_SYSTEM_PROMPT

    @property
    def chat_calls(self) -> list[list[dict]]:
        return [c for c in self.calls if not self.is_summary_call(c)]

    async def generate(self, messages, tools=None, response_format=None) -> AIResponse:
        self.calls.append(messages)
        if self.is_summary_call(messages):
            # A deterministic stand-in for a model: keeps the start of what it was given
            # (the previous summary comes first), capped like a real summary would be.
            if self.fail_summary:
                raise RuntimeError("summary unavailable")
            return AIResponse(content="SUMMARY: " + messages[1]["content"][:1500])
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("model unavailable")
        if self.scripted:
            return AIResponse(content=self.scripted.pop(0))
        return AIResponse(content=f"reply {len(self.chat_calls)}")


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

    async def get_athlete(self, access_token: str) -> AthleteProfile:
        return AthleteProfile(name="An Nguyen", profile_url="https://example.com/a.jpg")

    async def list_activities(self, access_token: str, limit: int = 10) -> list[RecentActivity]:
        return [
            RecentActivity(id=777, name="Morning Run", start_date_local="2026-11-20T06:00:00Z",
                           distance=10000.0, moving_time=3000, average_heartrate=150.0, type="Run"),
            RecentActivity(id=778, name="Lunch Ride", start_date_local="2026-11-19T12:00:00Z",
                           distance=20000.0, moving_time=3600, average_heartrate=None, type="Ride"),
            RecentActivity(id=779, name="Easy jog", start_date_local="2026-11-18T06:00:00Z",
                           distance=5000.0, moving_time=1800, average_heartrate=None, type="Run"),
        ][:limit]

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
# Fake Google token verifier
# ---------------------------------------------------------------------------

ALLOWED_EMAIL = "runner@example.com"


class FakeGoogleVerifier:
    """Accepts tokens shaped "fake:<email>"; anything else is an invalid token."""

    async def verify(self, id_token: str) -> GoogleIdentity:
        if not id_token.startswith("fake:"):
            raise InvalidGoogleToken("not a valid token")
        return GoogleIdentity(email=id_token[len("fake:"):], email_verified=True)


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_pool():
    if not DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not configured")

    async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
        await conn.execute(f"DROP TABLE IF EXISTS {_ALL_TABLES} CASCADE")
        for migration in MIGRATIONS:
            await conn.execute(migration.read_text())

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


async def sign_in(ac: httpx.AsyncClient, email: str = ALLOWED_EMAIL) -> httpx.Response:
    resp = await ac.post("/auth/google", json={"credential": f"fake:{email}"})
    assert resp.status_code == 200, resp.text
    return resp


@pytest_asyncio.fixture
async def anon_client(db_pool, fake_ai_client):
    """A client with no session. Google verification is faked."""
    app.dependency_overrides[get_ai_client_dep] = lambda: fake_ai_client
    app.dependency_overrides[get_google_verifier] = lambda: FakeGoogleVerifier()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(anon_client):
    """A client signed in as the allowlisted fake runner."""
    await sign_in(anon_client)
    return anon_client


@pytest_asyncio.fixture
async def anon_webhook_client(db_pool, fake_analysis_ai_client, fake_strava_client):
    from app.api.strava import get_strava_client
    app.dependency_overrides[get_ai_client_dep] = lambda: fake_analysis_ai_client
    app.dependency_overrides[get_strava_client] = lambda: fake_strava_client
    app.dependency_overrides[get_google_verifier] = lambda: FakeGoogleVerifier()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def webhook_client(anon_webhook_client):
    """Webhook-wiring client that is also signed in, for reading results back."""
    await sign_in(anon_webhook_client)
    return anon_webhook_client


async def make_runner(email: str):
    """Insert (or find) the Runner with this email and return their id."""
    from app.db.connection import get_pool
    from app.db.repositories import RunnerRepository
    async with get_pool().connection() as conn:
        return await RunnerRepository(conn).get_or_create(email)


@pytest_asyncio.fixture
async def runner_id(db_pool):
    """The id of the signed-in fake runner (ALLOWED_EMAIL)."""
    return await make_runner(ALLOWED_EMAIL)


@pytest_asyncio.fixture
async def seeded_strava_connection(db_pool, runner_id):
    """Insert a Strava connection that never expires, owned by the fake runner."""
    from app.db.connection import get_pool
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO strava_connections
                    (strava_athlete_id, access_token, refresh_token, expires_at, runner_id)
                VALUES (12345, 'test_access', 'test_refresh', %s, %s)
                """,
                (datetime(2099, 1, 1, tzinfo=timezone.utc), runner_id),
            )
        await conn.commit()


@pytest_asyncio.fixture
async def seeded_plan(db_pool, runner_id):
    """Insert a training plan with a workout scheduled for today, owned by the fake runner."""
    return await _seed_plan(runner_id)


async def _seed_plan(runner_id):
    from app.db.connection import get_pool
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday of this week
    day_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    today_abbrev = day_map[today.weekday()]

    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO user_goals (distance, target_time, race_date, vdot, weekly_availability, runner_id) "
                "VALUES ('half_marathon', '2:00:00', %s, 40.0, %s, %s) RETURNING id",
                ((today + timedelta(weeks=16)), Jsonb(_FOUR_DAY_AVAILABILITY), runner_id),
            )
            goal_id = (await cur.fetchone())[0]

            await cur.execute(
                "INSERT INTO training_plans (goal_id, total_weeks, summary, start_date, runner_id) "
                "VALUES (%s, 4, 'Test plan', %s, %s) RETURNING id",
                (goal_id, week_start, runner_id),
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

    return {"goal_id": goal_id, "plan_id": plan_id, "workout_id": workout_id, "date": today, "week_start": week_start}
