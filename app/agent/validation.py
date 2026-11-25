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

MIN_WEEKS_LEAD = 6


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


# ---------------------------------------------------------------------------
# Plan edits (Plan chat). The model proposes, these rules decide; see GLOSSARY.md
# (Weekly availability, Long run, Weekly volume, Missed workout).
# ---------------------------------------------------------------------------

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
QUALITY_TYPES = {
    "tempo", "threshold", "interval", "intervals", "repetition", "repetitions", "reps", "marathon_pace", "marathon",
}
LONG_RUN_SHARE_SMALL_WEEK = 0.30  # weeks under 64 km
LONG_RUN_SHARE = 0.25
SMALL_WEEK_KM = 64
LONG_RUN_MAX_MINUTES = 150
KM_TOLERANCE = 0.05  # rounding slack on km comparisons
AVAILABILITY_CODES = {"slots", "max_km", "quality_not_allowed"}


def _is_run(w: dict) -> bool:
    return w["type"].strip().lower() != "rest" and w["distanceKm"] > 0


def _is_quality(w: dict) -> bool:
    return w["type"].strip().lower() in QUALITY_TYPES


def day_signature(workouts: list[dict]) -> list[tuple[str, float]]:
    """What a day holds for comparison: its runs' types and distances (rest and notes ignored)."""
    return sorted((w["type"].strip().lower(), round(w["distanceKm"], 2)) for w in workouts if _is_run(w))


def _total(days: dict[str, list[dict]]) -> float:
    return sum(w["distanceKm"] for ws in days.values() for w in ws if _is_run(w))


def _longest(days: dict[str, list[dict]]) -> float:
    return max((w["distanceKm"] for ws in days.values() for w in ws if _is_run(w)), default=0.0)


def long_run_limit_km(week_km: float, easy_slow_sec_per_km: int | None) -> float:
    """The Long run limit: 30% of the week under 64 km, else 25%, or 150 minutes at easy pace."""
    share = LONG_RUN_SHARE_SMALL_WEEK if week_km < SMALL_WEEK_KM else LONG_RUN_SHARE
    limit = share * week_km
    if easy_slow_sec_per_km:
        limit = min(limit, LONG_RUN_MAX_MINUTES * 60 / easy_slow_sec_per_km)
    return round(limit, 1)


def _r(code: str, **params) -> dict:
    return {"code": code, "params": params}


def _goal_change_reason(goal: dict, change: dict | None) -> dict | None:
    if not change:
        return None
    differs = False
    if change.get("distance") and change["distance"] != goal["distance"]:
        differs = True
    if change.get("race_date") and str(change["race_date"]) != goal["race_date"].isoformat():
        differs = True
    if change.get("target_time"):
        try:
            wanted = _parse_target_time(str(change["target_time"]))
            seconds = wanted.hour * 3600 + wanted.minute * 60 + wanted.second
        except GoalOutOfScopeError:
            seconds = -1
        current = goal["target_time"]
        current = current.total_seconds() if isinstance(current, timedelta) else current
        differs = differs or seconds != current
    return _r("goal_change") if differs else None


def check_plan_edit(
    *,
    start_date: date,
    total_weeks: int,
    current: dict[int, dict[str, list[dict]]],
    proposed: dict[int, dict[str, list[dict]]],
    goal: dict,
    today: date,
    locked_days: set[tuple[int, str]] = frozenset(),
    weekly_volumes: dict[int, float] | None = None,
    override: dict | None = None,
    override_weeks_used: set[int] = frozenset(),
    goal_change: dict | None = None,
    easy_slow_sec_per_km: int | None = None,
) -> dict:
    """Check a proposed Plan edit against the rules. Python, not the model, decides.

    `current` and `proposed` map week -> day -> workouts ({type, distanceKm, ...}); a
    proposed week replaces the whole week. Returns {changes, reasons, override}: the
    changed days with before and after, why the edit is refused (empty when it may be
    proposed), and the availability limits the one-off override breaks, if any.
    """
    goal_reason = _goal_change_reason(goal, goal_change)
    if goal_reason:
        return {"changes": [], "reasons": [goal_reason], "override": None}

    weekly_volumes = weekly_volumes or {}
    availability = {d["day"]: d for d in goal["weekly_availability"]}
    changes, reasons, availability_breaks = [], [], {}
    for week in sorted(proposed):
        if not 1 <= week <= total_weeks:
            reasons.append(_r("unknown_week", week=week))
            continue
        before_days, after_days = current.get(week, {}), proposed[week]
        changed_days = [
            d for d in WEEKDAYS
            if day_signature(before_days.get(d, [])) != day_signature(after_days.get(d, []))
        ]
        if not changed_days:
            continue
        for day in changed_days:
            changes.append({"week": week, "day": day, "before": before_days.get(day, []), "after": after_days.get(day, [])})
            when = start_date + timedelta(days=(week - 1) * 7 + WEEKDAYS.index(day))
            if when < today:
                reasons.append(_r("past_day", week=week, day=day))
                continue
            if (week, day) in locked_days:
                reasons.append(_r("matched_day", week=week, day=day))
                continue
            limits = availability.get(day, {"slots": 0, "maxKm": None, "qualityAllowed": False})
            runs = [w for w in after_days.get(day, []) if _is_run(w)]
            broken = []
            if len(runs) > limits["slots"]:
                broken.append(_r("slots", week=week, day=day, count=len(runs), slots=limits["slots"]))
            cap = limits.get("maxKm")
            for w in runs:
                if cap is not None and w["distanceKm"] > cap + KM_TOLERANCE:
                    broken.append(_r("max_km", week=week, day=day, km=w["distanceKm"], max=cap))
                if _is_quality(w) and not limits.get("qualityAllowed", True):
                    broken.append(_r("quality_not_allowed", week=week, day=day, type=w["type"]))
            if broken:
                availability_breaks[(week, day)] = broken

        quality_before = sum(_is_quality(w) for ws in before_days.values() for w in ws if _is_run(w))
        quality_after = sum(_is_quality(w) for ws in after_days.values() for w in ws if _is_run(w))
        if quality_after > quality_before:
            reasons.append(_r("quality_added", week=week))
        total_after = round(_total(after_days), 2)
        volume = weekly_volumes.get(week, round(_total(before_days), 2))
        if total_after > volume + KM_TOLERANCE:
            reasons.append(_r("load_cap", week=week, km=total_after, volume=volume))
        long_after, long_before = _longest(after_days), _longest(before_days)
        limit = long_run_limit_km(total_after, easy_slow_sec_per_km)
        if long_after > limit + KM_TOLERANCE and long_after > long_before + KM_TOLERANCE:
            reasons.append(_r("long_run", week=week, km=long_after, limit=limit))

    used_override = None
    if override:
        key = (override.get("week_number"), override.get("day"))
        if key in availability_breaks:
            if key[0] in override_weeks_used:
                reasons.append(_r("override_used", week=key[0]))
            else:
                used_override = {"week": key[0], "day": key[1], "limits": availability_breaks.pop(key)}
    for broken in availability_breaks.values():
        reasons.extend(broken)
    if not changes and not reasons:
        reasons.append(_r("no_change"))
    return {"changes": changes, "reasons": reasons, "override": used_override}


_REASON_TEXT = {
    "goal_change": "the race, target time and race date cannot change in the Plan; that starts a new Goal",
    "unknown_week": "week {week} is not in the Plan",
    "past_day": "week {week} {day} is in the past, and past days are never changed",
    "matched_day": "week {week} {day} already has a run matched to it",
    "slots": "week {week} {day} would hold {count} runs; Weekly availability allows {slots}",
    "max_km": "week {week} {day} would be {km} km; Weekly availability allows at most {max} km that day",
    "quality_not_allowed": "week {week} {day} does not allow Quality workouts ({type})",
    "quality_added": "week {week} would gain a Quality workout; a missed Quality workout is never made up",
    "load_cap": "week {week} would total {km} km, above its Weekly volume of {volume} km",
    "long_run": "the longest run in week {week} would be {km} km, above the Long run limit of {limit} km",
    "override_used": "week {week} has already used its one-off availability override",
    "no_change": "the proposal changes nothing",
    "no_proposal": "the edit model did not produce a usable proposal",
    "stale": "the Plan changed since this was proposed",
}


def reason_text(reason: dict) -> str:
    """English text of a rejection reason, for prompts and logs (the UI translates the code)."""
    return _REASON_TEXT[reason["code"]].format(**reason["params"])
