import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from psycopg import AsyncConnection

from app.agent.planner import PlanGenerationError, generate_plan
from app.agent.validation import GoalOutOfScopeError, validate_goal
from app.ai.client import AIClient
from app.ai.factory import get_ai_client_dep
from app.db.connection import get_db
from app.db.repositories import GoalRepository, PlanRepository
from app.models.goal import GoalRequest
from app.models.plan import PlanResponse, PlanWeek, WorkoutSession

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_plan_response(plan: dict) -> PlanResponse:
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

    return PlanResponse(
        plan_id=str(plan["id"]),
        goal_id=str(plan["goal_id"]),
        summary=plan["summary"],
        total_weeks=plan["total_weeks"],
        phase_breakdown=phase_breakdown,
        weeks=[weeks_map[n] for n in sorted(weeks_map)],
    )


@router.post("/goal", status_code=202)
async def create_goal(
    goal: GoalRequest,
    background_tasks: BackgroundTasks,
    db: AsyncConnection = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client_dep),
) -> dict:
    try:
        validate_goal(goal)
    except GoalOutOfScopeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "goal_out_of_scope", "message": exc.message},
        )

    goal_id = await GoalRepository(db).insert(goal)
    await db.commit()

    background_tasks.add_task(_generate_plan_background, goal_id, goal, ai_client)
    return {"goalId": str(goal_id), "status": "generating"}


async def _generate_plan_background(
    goal_id: UUID, goal: GoalRequest, ai_client: AIClient
) -> None:
    from app.db.connection import get_pool

    pool = get_pool()
    async with pool.connection() as conn:
        try:
            plan = await generate_plan(goal, client=ai_client)
            plan_repo = PlanRepository(conn)
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
            await GoalRepository(conn).update_status(goal_id, "ready")
            await conn.commit()
        except PlanGenerationError as exc:
            logger.error("Plan generation failed for goal %s: %s", goal_id, exc)
            try:
                await GoalRepository(conn).update_status(goal_id, "failed")
                await conn.commit()
            except Exception:
                pass
        except Exception as exc:
            logger.error("Unexpected error for goal %s: %s", goal_id, exc, exc_info=True)
            try:
                await GoalRepository(conn).update_status(goal_id, "failed")
                await conn.commit()
            except Exception:
                pass


@router.get("/goals")
async def list_goals(db: AsyncConnection = Depends(get_db)) -> dict:
    rows = await GoalRepository(db).list_all()
    goals = []
    for row in rows:
        tt = row["target_time"]
        total_secs = int(tt.total_seconds())
        h, remainder = divmod(total_secs, 3600)
        m, s = divmod(remainder, 60)
        goals.append({
            "goalId": str(row["id"]),
            "distance": row["distance"],
            "targetTime": f"{h}:{m:02d}:{s:02d}",
            "raceDate": row["race_date"].isoformat(),
            "fitnessLevel": row["fitness_level"],
            "daysPerWeek": row["days_per_week"],
            "planStatus": row["plan_status"],
            "createdAt": row["created_at"].isoformat(),
        })
    return {"goals": goals}


@router.get("/goal/{goal_id}/plan")
async def get_goal_plan(
    goal_id: UUID, db: AsyncConnection = Depends(get_db)
) -> JSONResponse:
    goal_row = await GoalRepository(db).get(goal_id)
    if goal_row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "goal_not_found", "message": "Goal not found"},
        )

    status = goal_row["plan_status"]

    if status == "generating":
        return JSONResponse(
            status_code=202,
            content={"goalId": str(goal_id), "status": "generating"},
        )

    if status == "failed":
        return JSONResponse(
            status_code=200,
            content={
                "goalId": str(goal_id),
                "status": "failed",
                "error": "plan_generation_failed",
            },
        )

    # status == "ready"
    plan = await PlanRepository(db).get_plan_by_goal_id(goal_id)
    if plan is None:
        raise HTTPException(status_code=500, detail="Plan marked ready but not found in DB")

    response_data = _build_plan_response(plan).model_dump(by_alias=True)
    response_data["status"] = "ready"
    return JSONResponse(status_code=200, content=response_data)


@router.delete("/goal/{goal_id}")
async def delete_goal(
    goal_id: UUID, db: AsyncConnection = Depends(get_db)
) -> dict:
    deleted = await GoalRepository(db).delete(goal_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "goal_not_found", "message": "Goal not found"},
        )
    await db.commit()
    return {"deleted": True}
