from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from app.agent.planner import PlanGenerationError, generate_plan
from app.agent.validation import GoalOutOfScopeError, validate_goal
from app.ai.client import AIClient
from app.ai.factory import get_ai_client_dep
from app.db.connection import get_db
from app.db.repositories import GoalRepository, PlanRepository
from app.models.goal import GoalRequest
from app.models.plan import PlanResponse

router = APIRouter()


@router.post("/goal", response_model=PlanResponse)
async def create_goal(
    goal: GoalRequest,
    db: AsyncConnection = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client_dep),
) -> PlanResponse:
    try:
        validate_goal(goal)
    except GoalOutOfScopeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "goal_out_of_scope", "message": exc.message},
        )

    try:
        plan = await generate_plan(goal, client=ai_client)
    except PlanGenerationError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "plan_generation_failed", "message": str(exc)},
        )

    # Persist the goal, plan, and all workout sessions through the repositories.
    goal_repo = GoalRepository(db)
    plan_repo = PlanRepository(db)

    goal_id = await goal_repo.insert(goal)
    plan_id = await plan_repo.insert_plan(
        goal_id=goal_id,
        total_weeks=plan.total_weeks,
        summary=plan.summary,
    )

    for week in plan.weeks:
        for workout in week.workouts:
            await plan_repo.insert_workout(
                plan_id=plan_id,
                week_number=week.week_number,
                phase=week.phase,
                day=workout.day,
                workout_type=workout.type,
                distance_km=workout.distance_km,
                pace_zone=workout.pace_zone,
                notes=workout.notes,
            )

    await db.commit()

    # Return the plan with the real persisted identifiers.
    return plan.model_copy(update={"plan_id": str(plan_id), "goal_id": str(goal_id)})
