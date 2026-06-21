from dataclasses import dataclass

from app.models.plan import PlannedWorkout
from app.strava.models import ActivityDetail

DISTANCE_TOLERANCE = 0.30  # ±30%


@dataclass
class MatchResult:
    matched: bool
    workout: PlannedWorkout | None
    mismatch: bool


def match_activity_to_workout(
    activity: ActivityDetail,
    candidates: list[PlannedWorkout],
) -> MatchResult:
    """Match an activity to a planned workout by date + distance plausibility.

    candidates must already be filtered to the activity's calendar date by the caller.
    Returns unmatched when no candidates exist, matched+mismatch=True when distance
    is outside the ±DISTANCE_TOLERANCE band, matched+mismatch=False otherwise.
    """
    if not candidates:
        return MatchResult(matched=False, workout=None, mismatch=False)

    workout = candidates[0]

    if workout.distance_km == 0:
        return MatchResult(matched=True, workout=workout, mismatch=False)

    activity_km = activity.distance / 1000
    lower = workout.distance_km * (1 - DISTANCE_TOLERANCE)
    upper = workout.distance_km * (1 + DISTANCE_TOLERANCE)
    mismatch = not (lower <= activity_km <= upper)

    return MatchResult(matched=True, workout=workout, mismatch=mismatch)
