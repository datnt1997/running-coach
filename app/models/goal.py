from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
Weekday = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

MAX_WORKOUT_KM = 60  # Longest distance cap a runner may set for one workout.
MIN_TRAINING_DAYS = 3


class DayAvailability(BaseModel):
    """What the runner can do on one weekday (see GLOSSARY.md, Weekly availability)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    day: Weekday
    slots: int = Field(..., ge=0, le=2)
    max_km: float | None = None
    quality_allowed: bool = True

    @model_validator(mode="after")
    def _cap_is_sensible_on_training_days(self):
        # A rest day (0 slots) ignores its cap and Quality flag.
        if self.slots > 0 and self.max_km is not None:
            if not 0 < self.max_km <= MAX_WORKOUT_KM:
                raise ValueError(f"maxKm must be above 0 and at most {MAX_WORKOUT_KM}")
        return self


def count_training_days(week: list[DayAvailability]) -> int:
    """Number of Training days: weekdays with at least one workout slot."""
    return sum(1 for d in week if d.slots > 0)


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
    weekly_availability: list[DayAvailability]
    injury_history: str | None = None
    vdot: float | None = Field(None, ge=15, le=90)

    @model_validator(mode="after")
    def _availability_covers_the_week(self):
        days = [d.day for d in self.weekly_availability]
        if sorted(days, key=WEEKDAYS.index) != list(WEEKDAYS):
            raise ValueError("weeklyAvailability needs exactly one entry for each weekday")
        if self.training_days < MIN_TRAINING_DAYS:
            raise ValueError(f"at least {MIN_TRAINING_DAYS} training days are needed")
        return self

    @property
    def training_days(self) -> int:
        return count_training_days(self.weekly_availability)


class GoalValidationError(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    error: str
    message: str
