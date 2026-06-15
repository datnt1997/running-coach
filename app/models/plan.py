from pydantic import BaseModel


class WorkoutSession(BaseModel):
    day: str
    type: str
    distance_km: float
    pace_zone: str
    notes: str | None = None


class PlanWeek(BaseModel):
    week_number: int
    phase: str
    workouts: list[WorkoutSession]


class PlanResponse(BaseModel):
    plan_id: str
    goal_id: str
    summary: str
    total_weeks: int
    phase_breakdown: dict[str, int]
    weeks: list[PlanWeek]
