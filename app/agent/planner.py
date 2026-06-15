from app.agent.prompt import build_messages
from app.ai.client import AIClient
from app.ai.factory import get_ai_client
from app.ai.tools import TOOLS
from app.models.goal import GoalRequest
from app.models.plan import PlanResponse, PlanWeek, WorkoutSession


class PlanGenerationError(Exception):
    """Raised when the AI client returns malformed or unusable plan output."""


def _parse_plan_arguments(arguments: dict, goal: GoalRequest) -> PlanResponse:
    try:
        weeks_raw = arguments["weeks"]
        weeks: list[PlanWeek] = []
        for week in weeks_raw:
            workouts = [
                WorkoutSession(
                    day=w["day"],
                    type=w["type"],
                    distance_km=float(w["distance_km"]),
                    pace_zone=w["pace_zone"],
                    notes=w.get("notes"),
                )
                for w in week["workouts"]
            ]
            weeks.append(
                PlanWeek(
                    week_number=int(week["week_number"]),
                    phase=week["phase"],
                    workouts=workouts,
                )
            )

        phase_breakdown = {k: int(v) for k, v in arguments["phase_breakdown"].items()}

        return PlanResponse(
            # plan_id / goal_id are assigned after persistence; placeholders here.
            plan_id="",
            goal_id="",
            summary=arguments["summary"],
            total_weeks=int(arguments["total_weeks"]),
            phase_breakdown=phase_breakdown,
            weeks=weeks,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanGenerationError(
            f"AI returned malformed training plan: {exc}"
        ) from exc


async def generate_plan(
    goal: GoalRequest, client: AIClient | None = None
) -> PlanResponse:
    """Generate a training plan for a validated goal via the configured AI client.

    Calls the AI client exactly once and parses the structured tool output into
    a PlanResponse. Raises PlanGenerationError on malformed output. An explicit
    ``client`` may be supplied (e.g. by the API layer / tests); otherwise the
    configured provider client is created via the factory.
    """
    if client is None:
        client = get_ai_client()
    messages = build_messages(goal)

    response = await client.generate(messages, tools=TOOLS)

    if not response.tool_calls:
        raise PlanGenerationError(
            "AI did not return a generate_training_plan tool call."
        )

    return _parse_plan_arguments(response.tool_calls[0].arguments, goal)
