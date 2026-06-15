from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from app.db.connection import get_db
from app.db.repositories import PlanRepository
from app.models.plan import PlanResponse, PlanWeek, WorkoutSession

router = APIRouter()


def _build_plan_response(plan: dict) -> PlanResponse:
    """Assemble a PlanResponse from the joined plan/workout rows."""
    weeks_map: dict[int, PlanWeek] = {}
    phase_breakdown: dict[str, int] = {}

    for row in plan["workouts"]:
        week_number = row["week_number"]
        phase = row["phase"]
        week = weeks_map.get(week_number)
        if week is None:
            week = PlanWeek(week_number=week_number, phase=phase, workouts=[])
            weeks_map[week_number] = week
            phase_breakdown[phase] = phase_breakdown.get(phase, 0) + 1

        distance = row["distance_km"]
        week.workouts.append(
            WorkoutSession(
                day=row["day_of_week"],
                type=row["workout_type"],
                distance_km=float(distance) if distance is not None else 0.0,
                pace_zone=row["pace_zone"] or "",
                notes=row["notes"],
            )
        )

    weeks = [weeks_map[n] for n in sorted(weeks_map)]

    return PlanResponse(
        plan_id=str(plan["id"]),
        goal_id=str(plan["goal_id"]),
        summary=plan["summary"],
        total_weeks=plan["total_weeks"],
        phase_breakdown=phase_breakdown,
        weeks=weeks,
    )


@router.get("/plan/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: UUID, db: AsyncConnection = Depends(get_db)
) -> PlanResponse:
    repo = PlanRepository(db)
    plan = await repo.get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "plan_not_found", "message": "Plan not found"},
        )
    return _build_plan_response(plan)
