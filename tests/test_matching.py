from datetime import date
from uuid import uuid4

import pytest

from app.agent.matching import DISTANCE_TOLERANCE, MatchResult, match_activity_to_workout
from app.models.plan import PlannedWorkout
from app.strava.models import ActivityDetail


def _workout(distance_km: float = 8.0) -> PlannedWorkout:
    return PlannedWorkout(
        id=uuid4(),
        date=date.today(),
        workout_type="easy",
        distance_km=distance_km,
        pace_zone="Z2",
        week_number=1,
        phase="base",
    )


def _activity(distance_m: float) -> ActivityDetail:
    return ActivityDetail(
        id=1,
        start_date_local=date.today().isoformat() + "T07:00:00Z",
        distance=distance_m,
        moving_time=3600,
        type="Run",
    )


def test_unmatched_when_no_candidates():
    result = match_activity_to_workout(_activity(8000), [])
    assert result.matched is False
    assert result.workout is None
    assert result.mismatch is False


def test_clean_match_within_tolerance():
    workout = _workout(8.0)
    result = match_activity_to_workout(_activity(8000), [workout])
    assert result.matched is True
    assert result.mismatch is False
    assert result.workout == workout


def test_mismatch_when_far_outside_tolerance():
    # 5 km actual vs 20 km planned → well outside ±30%
    workout = _workout(20.0)
    result = match_activity_to_workout(_activity(5000), [workout])
    assert result.matched is True
    assert result.mismatch is True


def test_match_at_lower_tolerance_boundary():
    planned_km = 10.0
    lower_bound_m = planned_km * (1 - DISTANCE_TOLERANCE) * 1000  # exactly at boundary
    result = match_activity_to_workout(_activity(lower_bound_m), [_workout(planned_km)])
    assert result.matched is True
    assert result.mismatch is False


def test_match_at_upper_tolerance_boundary():
    planned_km = 10.0
    upper_bound_m = planned_km * (1 + DISTANCE_TOLERANCE) * 1000
    result = match_activity_to_workout(_activity(upper_bound_m), [_workout(planned_km)])
    assert result.matched is True
    assert result.mismatch is False


def test_mismatch_just_outside_lower_boundary():
    planned_km = 10.0
    just_under_m = (planned_km * (1 - DISTANCE_TOLERANCE) - 0.01) * 1000
    result = match_activity_to_workout(_activity(just_under_m), [_workout(planned_km)])
    assert result.mismatch is True


def test_mismatch_just_outside_upper_boundary():
    planned_km = 10.0
    just_over_m = (planned_km * (1 + DISTANCE_TOLERANCE) + 0.01) * 1000
    result = match_activity_to_workout(_activity(just_over_m), [_workout(planned_km)])
    assert result.mismatch is True


def test_zero_distance_workout_never_mismatches():
    # Rest/cross days have distance_km=0; any activity against them is clean match
    result = match_activity_to_workout(_activity(5000), [_workout(0.0)])
    assert result.matched is True
    assert result.mismatch is False
