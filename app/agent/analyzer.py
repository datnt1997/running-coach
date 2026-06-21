from uuid import UUID

from psycopg import AsyncConnection

from app.agent.prompt import build_activity_analysis_messages, build_weekly_summary_messages
from app.ai.client import AIClient
from app.ai.factory import get_ai_client
from app.ai.tools import ANALYZE_ACTIVITY_TOOL
from app.models.plan import PlannedWorkout
from app.strava.models import ActivityDetail


class AnalysisGenerationError(Exception):
    pass


async def analyze_activity(
    planned: PlannedWorkout,
    actual: ActivityDetail,
    client: AIClient | None = None,
) -> dict:
    """Analyze an activity against its planned workout via Claude.

    Returns the analyze_activity tool arguments dict with pace_adherence,
    hr_adherence, load_adherence, and rationale keys.
    Raises AnalysisGenerationError on malformed output.
    """
    if client is None:
        client = get_ai_client()

    messages = build_activity_analysis_messages(planned, actual)
    response = await client.generate(messages, tools=[ANALYZE_ACTIVITY_TOOL])

    if not response.tool_calls:
        raise AnalysisGenerationError("AI did not return an analyze_activity tool call.")

    return response.tool_calls[0].arguments


async def build_weekly_summary(
    plan_id: UUID,
    week_number: int,
    conn: AsyncConnection,
    client: AIClient | None = None,
) -> str:
    """Generate a human-readable weekly summary by calling Claude once.

    Fetches all activity_analyses rows for the given week and rolls them up
    into a 2-3 sentence coaching summary.
    """
    from app.db.repositories import ActivityAnalysisRepository

    if client is None:
        client = get_ai_client()

    repo = ActivityAnalysisRepository(conn)
    analyses = await repo.list_for_week(plan_id, week_number)

    messages = build_weekly_summary_messages(week_number, analyses)
    response = await client.generate(messages)
    return response.content
