from datetime import date, timedelta

import pytest

from app.agent.validation import GoalOutOfScopeError, validate_goal
from app.models.goal import GoalRequest


# Fixed reference date so the lead-time boundary cases are deterministic.
TODAY = date(2026, 1, 1)


def _goal(distance: str, target_time: str, race_date: date) -> GoalRequest:
    return GoalRequest(
        distance=distance,
        target_time=target_time,
        race_date=race_date,
        fitness_level="intermediate",
        days_per_week=4,
        injury_history=None,
    )


def _race_date(weeks: int = 16, extra_days: int = 0) -> date:
    return TODAY + timedelta(weeks=weeks, days=extra_days)


# --- Half marathon target-time bounds -------------------------------------

def test_hm_at_exactly_bound_accepted():
    goal = _goal("half_marathon", "1:45:00", _race_date())
    validate_goal(goal, today=TODAY)  # should not raise


def test_hm_one_second_slower_accepted():
    goal = _goal("half_marathon", "1:45:01", _race_date())
    validate_goal(goal, today=TODAY)  # should not raise


def test_hm_one_second_faster_rejected():
    goal = _goal("half_marathon", "1:44:59", _race_date())
    with pytest.raises(GoalOutOfScopeError):
        validate_goal(goal, today=TODAY)


# --- Full marathon target-time bounds -------------------------------------

def test_fm_at_exactly_bound_accepted():
    goal = _goal("full_marathon", "4:00:00", _race_date(weeks=20))
    validate_goal(goal, today=TODAY)  # should not raise


def test_fm_one_second_faster_rejected():
    goal = _goal("full_marathon", "3:59:59", _race_date(weeks=20))
    with pytest.raises(GoalOutOfScopeError):
        validate_goal(goal, today=TODAY)


# --- Race-date lead-time bounds -------------------------------------------

def test_race_date_exactly_10_weeks_accepted():
    goal = _goal("half_marathon", "1:55:00", _race_date(weeks=10))
    validate_goal(goal, today=TODAY)  # should not raise


def test_race_date_9_weeks_6_days_rejected():
    goal = _goal("half_marathon", "1:55:00", _race_date(weeks=9, extra_days=6))
    with pytest.raises(GoalOutOfScopeError):
        validate_goal(goal, today=TODAY)
