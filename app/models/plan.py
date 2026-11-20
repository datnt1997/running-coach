from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class WorkoutSession(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    day: str
    type: str
    distance_km: float
    pace_zone: str
    notes: str | None = None
    # Heart-rate target {minZone, maxZone, min, max}; None when the runner's profile
    # has no zones or the workout type has no heart-rate target.
    target_zone: dict | None = None


class PlanWeek(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    week_number: int
    phase: str
    workouts: list[WorkoutSession]


class PlanResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    plan_id: str
    goal_id: str
    summary: str
    start_date: date
    language: str
    total_weeks: int
    phase_breakdown: dict[str, int]
    weeks: list[PlanWeek]
    # False when the runner's profile lacks the values the heart-rate zones need.
    zones_available: bool = False


class PlannedWorkout(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: UUID
    date: date
    workout_type: str
    distance_km: float
    pace_zone: str
    week_number: int
    phase: str
