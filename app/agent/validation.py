from datetime import date, time, timedelta

from app.models.goal import GoalRequest


class GoalOutOfScopeError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# Fastest target time we will plan for. A target FASTER than the bound is
# rejected as out of scope.
BOUNDS = {
    "half_marathon": time(1, 44, 0),
    "full_marathon": time(3, 59, 0),
}

MIN_WEEKS_LEAD = 10


def _parse_target_time(target_time: str) -> time:
    """Parse an HH:MM:SS (or H:MM:SS / MM:SS) string into a time."""
    parts = target_time.split(":")
    try:
        ints = [int(p) for p in parts]
    except ValueError as exc:
        raise GoalOutOfScopeError(
            f"Invalid target_time format: {target_time!r}"
        ) from exc

    if len(ints) == 3:
        hours, minutes, seconds = ints
    elif len(ints) == 2:
        hours, minutes, seconds = 0, ints[0], ints[1]
    else:
        raise GoalOutOfScopeError(f"Invalid target_time format: {target_time!r}")

    if not (0 <= minutes < 60 and 0 <= seconds < 60):
        raise GoalOutOfScopeError(f"Invalid target_time value: {target_time!r}")

    return time(hour=hours, minute=minutes, second=seconds)


def validate_goal(goal: GoalRequest, today: date | None = None) -> None:
    """Validate a goal is within coaching scope.

    Raises GoalOutOfScopeError when:
      - the target time is FASTER than the distance bound, or
      - the race date is less than MIN_WEEKS_LEAD weeks away.
    """
    if today is None:
        today = date.today()

    target = _parse_target_time(goal.target_time)
    bound = BOUNDS[goal.distance]

    # Reject if the requested target is faster than the supported bound.
    if target < bound:
        raise GoalOutOfScopeError(
            f"A target time of {goal.target_time} for {goal.distance.replace('_', ' ')} "
            f"is faster than this coach supports (minimum supported time is "
            f"{bound.strftime('%-H:%M:%S')})."
        )

    earliest_race_date = today + timedelta(weeks=MIN_WEEKS_LEAD)
    if goal.race_date < earliest_race_date:
        raise GoalOutOfScopeError(
            f"Race date {goal.race_date.isoformat()} is too soon. A minimum of "
            f"{MIN_WEEKS_LEAD} weeks of lead time is required "
            f"(earliest acceptable race date is {earliest_race_date.isoformat()})."
        )
