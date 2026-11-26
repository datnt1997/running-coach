from datetime import date, timedelta

import pytest

from app.agent.validation import GoalOutOfScopeError, long_run_limit_km, validate_goal
from app.models.goal import GoalRequest


@pytest.mark.parametrize("week_km,easy_pace,limit", [
    (45, None, 13.5),   # under 64 km: 30%
    (66, None, 16.5),   # 64 km or more: 25% (research R2 worked case)
    (100, 400, 22.5),   # 150 minutes at 6:40/km comes before 25 km
])
def test_long_run_limit(week_km, easy_pace, limit):
    assert long_run_limit_km(week_km, easy_pace) == limit
from tests.availability import week_with_days


# Fixed reference date so the lead-time boundary cases are deterministic.
TODAY = date(2026, 1, 1)


def _goal(distance: str, target_time: str, race_date: date) -> GoalRequest:
    return GoalRequest(
        distance=distance,
        target_time=target_time,
        race_date=race_date,
        vdot=40.0,
        weekly_km=40,
        longest_run_km=18,
        weekly_availability=week_with_days(4),
        injury_history=None,
    )


def _race_date(weeks: int = 16, extra_days: int = 0) -> date:
    return TODAY + timedelta(weeks=weeks, days=extra_days)


# --- Half marathon target-time bounds -------------------------------------

def test_hm_at_exactly_bound_accepted():
    goal = _goal("half_marathon", "1:44:00", _race_date())
    validate_goal(goal, today=TODAY)  # should not raise


def test_hm_one_second_slower_accepted():
    goal = _goal("half_marathon", "1:44:01", _race_date())
    validate_goal(goal, today=TODAY)  # should not raise


def test_hm_one_second_faster_rejected():
    goal = _goal("half_marathon", "1:43:59", _race_date())
    with pytest.raises(GoalOutOfScopeError):
        validate_goal(goal, today=TODAY)


# --- Full marathon target-time bounds -------------------------------------

def test_fm_at_exactly_bound_accepted():
    goal = _goal("full_marathon", "3:59:00", _race_date(weeks=20))
    validate_goal(goal, today=TODAY)  # should not raise


def test_fm_one_second_faster_rejected():
    goal = _goal("full_marathon", "3:58:59", _race_date(weeks=20))
    with pytest.raises(GoalOutOfScopeError):
        validate_goal(goal, today=TODAY)


# --- Race-date lead-time bounds -------------------------------------------

def test_race_date_exactly_6_weeks_accepted():
    goal = _goal("half_marathon", "1:55:00", _race_date(weeks=6))
    validate_goal(goal, today=TODAY)  # should not raise


def test_race_date_5_weeks_6_days_rejected():
    goal = _goal("half_marathon", "1:55:00", _race_date(weeks=5, extra_days=6))
    with pytest.raises(GoalOutOfScopeError):
        validate_goal(goal, today=TODAY)
