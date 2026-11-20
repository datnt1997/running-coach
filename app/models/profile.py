from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class ProfileRequest(BaseModel):
    """The runner's personal numbers. A value left out or null is cleared.

    Zones use maximum and resting heart rate. The lactate-threshold heart rate is
    optional and stored only; zones do not use it."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    max_hr: int | None = Field(default=None, ge=100, le=230)
    lactate_threshold_hr: int | None = Field(default=None, ge=80, le=220)
    resting_hr: int | None = Field(default=None, ge=25, le=120)
    cadence: int | None = Field(default=None, ge=120, le=230)

    @model_validator(mode="after")
    def _heart_rates_are_ordered(self):
        if (
            self.max_hr is not None
            and self.lactate_threshold_hr is not None
            and self.lactate_threshold_hr >= self.max_hr
        ):
            raise ValueError("Lactate-threshold heart rate must be below maximum heart rate")
        if (
            self.max_hr is not None
            and self.resting_hr is not None
            and self.resting_hr >= self.max_hr
        ):
            raise ValueError("Resting heart rate must be below maximum heart rate")
        return self
