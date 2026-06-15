from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class GoalRequest(BaseModel):
    distance: Literal["half_marathon", "full_marathon"]
    target_time: str = Field(
        ...,
        description="Target finish time in HH:MM:SS format",
        examples=["1:55:00"],
    )
    race_date: date
    fitness_level: Literal["beginner", "intermediate", "advanced"]
    days_per_week: int = Field(..., ge=3, le=6)
    injury_history: str | None = None


class GoalValidationError(BaseModel):
    error: str
    message: str
