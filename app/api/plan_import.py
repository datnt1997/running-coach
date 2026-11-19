"""One-off import of the runner's current Plan from pasted text or CSV."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel
from typing import Literal

from app.agent.plan_import import PlanImportError, parse_plan_csv
from app.agent.validation import GoalOutOfScopeError, _parse_target_time
from app.auth import require_runner
from app.db.connection import get_db
from app.db.repositories import GoalRepository, PlanRepository
from app.models.goal import WEEKDAYS
from app.vdot import vdot_from_race

router = APIRouter()

_RACE_METERS = {"half_marathon": 21097.5, "full_marathon": 42195}


class PlanImportRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    distance: Literal["half_marathon", "full_marathon"]
    target_time: str
    race_date: date
    start_date: date
    csv: str

    @field_validator("start_date")
    @classmethod
    def _starts_on_a_monday(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("startDate must be a Monday (the first day of plan week 1)")
        return value


@router.post("/plan/import", status_code=201)
async def import_plan(
    body: PlanImportRequest,
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
) -> dict:
    # Only the format of the target time is checked: the fastest-time and six-week
    # bounds apply to Plans generated from scratch, not to one the runner already follows.
    try:
        target = _parse_target_time(body.target_time)
    except GoalOutOfScopeError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "plan_import_invalid", "message": exc.message}
        )
    seconds = target.hour * 3600 + target.minute * 60 + target.second
    if seconds <= 0:
        raise HTTPException(
            status_code=422,
            detail={"error": "plan_import_invalid", "message": "targetTime must be above zero"},
        )

    try:
        workouts = parse_plan_csv(body.csv)
    except PlanImportError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "plan_import_invalid",
                "message": "Some rows could not be understood; nothing was imported.",
                "rows": [{"line": e.line, "message": e.message} for e in exc.errors],
            },
        )

    total_weeks = max(w.week_number for w in workouts)
    per_day = {d: 0 for d in WEEKDAYS}
    for w in workouts:
        per_day[w.day] += 1
    availability = [
        {"day": d, "slots": min(per_day[d], 2), "maxKm": None, "qualityAllowed": True}
        for d in WEEKDAYS
    ]

    # One transaction: any failure before commit leaves nothing behind.
    goal_id = await GoalRepository(db, runner_id).insert_imported(
        distance=body.distance,
        target_time=body.target_time,
        race_date=body.race_date,
        weekly_availability=availability,
        vdot=vdot_from_race(_RACE_METERS[body.distance], seconds),
    )
    plans = PlanRepository(db, runner_id)
    plan_id = await plans.insert_plan(
        goal_id=goal_id,
        total_weeks=total_weeks,
        summary="Imported plan",
        start_date=body.start_date,
    )
    for w in workouts:
        await plans.insert_workout(
            plan_id=plan_id,
            week_number=w.week_number,
            phase=w.phase,
            day=w.day,
            workout_type=w.workout_type,
            distance_km=w.distance_km,
            pace_zone=w.pace_zone,
            notes=w.notes,
        )
    await db.commit()
    return {
        "goalId": str(goal_id),
        "planId": str(plan_id),
        "totalWeeks": total_weeks,
        "workoutCount": len(workouts),
    }
