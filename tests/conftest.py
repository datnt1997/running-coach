import pathlib

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

MIGRATION_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "app"
    / "db"
    / "migrations"
    / "001_initial.sql"
)


def _build_fake_plan_arguments(
    total_weeks: int = 16,
    phase_breakdown: dict[str, int] | None = None,
    base_distance: float = 30.0,
) -> dict:
    """Construct a deterministic, well-formed plan for tests.

    Guarantees the plan-quality invariants the endpoint tests assert:
      - all four phases present
      - total_weeks == number of weeks
      - every workout has non-null day/type/distance_km/pace_zone
      - no week's total distance exceeds the previous week's by more than 10%
    """
    if phase_breakdown is None:
        phase_breakdown = {"base": 6, "build": 5, "peak": 3, "taper": 2}

    # Expand the phase breakdown into a per-week phase sequence.
    phase_sequence: list[str] = []
    for phase in ("base", "build", "peak", "taper"):
        phase_sequence.extend([phase] * phase_breakdown[phase])
    assert len(phase_sequence) == total_weeks

    days = ["Mon", "Tue", "Wed", "Thu"]  # 4 training days/week
    weeks = []
    weekly_total = base_distance
    for i, phase in enumerate(phase_sequence, start=1):
        # Build up to peak, then taper down — always within +10% week-over-week.
        if phase == "taper":
            weekly_total = round(weekly_total * 0.75, 2)
        else:
            weekly_total = round(weekly_total * 1.08, 2)

        # Distribute the weekly total across the 4 sessions (long run heavier).
        easy = round(weekly_total * 0.2, 2)
        workouts = [
            {
                "day": "Mon",
                "type": "easy",
                "distance_km": easy,
                "pace_zone": "Z2",
                "notes": "Conversational pace",
            },
            {
                "day": "Tue",
                "type": "tempo" if phase != "base" else "easy",
                "distance_km": easy,
                "pace_zone": "Z3" if phase != "base" else "Z2",
                "notes": "Quality session",
            },
            {
                "day": "Wed",
                "type": "easy",
                "distance_km": easy,
                "pace_zone": "Z2",
                "notes": "Recovery run",
            },
            {
                "day": "Thu",
                "type": "long",
                "distance_km": round(weekly_total - 3 * easy, 2),
                "pace_zone": "Z2",
                "notes": "Long run",
            },
        ]
        weeks.append(
            {"week_number": i, "phase": phase, "workouts": workouts}
        )

    return {
        "summary": (
            f"{total_weeks}-week plan with full periodization across "
            "base, build, peak, and taper phases."
        ),
        "total_weeks": total_weeks,
        "phase_breakdown": phase_breakdown,
        "weeks": weeks,
    }


class FakeAIClient:
    """Deterministic AI client for integration tests.

    Records call count to verify the endpoint calls generate() exactly once
    per request, and returns a valid generate_training_plan tool call.
    """

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


@pytest_asyncio.fixture
async def db_pool():
    """Open the connection pool and create the schema; drop it after the test."""
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not configured")

    schema_sql = MIGRATION_PATH.read_text()

    # Create tables (drop first so each test run starts clean).
    async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
        await conn.execute(
            "DROP TABLE IF EXISTS workout_sessions, training_plans, user_goals CASCADE"
        )
        await conn.execute(schema_sql)

    pool = await db_connection.init_pool()
    try:
        yield pool
    finally:
        await db_connection.close_pool()
        async with await AsyncConnection.connect(
            DATABASE_URL, autocommit=True
        ) as conn:
            await conn.execute(
                "DROP TABLE IF EXISTS workout_sessions, training_plans, "
                "user_goals CASCADE"
            )


@pytest_asyncio.fixture
async def fake_ai_client():
    return FakeAIClient()


@pytest_asyncio.fixture
async def client(db_pool, fake_ai_client):
    """httpx.AsyncClient bound to the FastAPI app via ASGI transport.

    The DB pool is real (db_pool fixture). The AI client is overridden with a
    deterministic fake so endpoint behavior is reproducible while still
    exercising the real persistence path.
    """
    app.dependency_overrides[get_ai_client_dep] = lambda: fake_ai_client
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
