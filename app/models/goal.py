from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class GoalRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    distance: Literal["half_marathon", "full_marathon"]
    target_time: str = Field(
        ...,
        description="Target finish time in HH:MM:SS format",
        examples=["1:55:00"],
    )
    race_date: date
    fitness_level: Literal["beginner", "intermediate", "advanced"]
    days_per_week: int = Field(..., ge=3, le=7)
    injury_history: str | None = None


class GoalValidationError(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    error: str
    message: str
