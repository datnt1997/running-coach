import pytest

from app import config, i18n
from app.agent.prompt import (
    build_activity_analysis_messages,
    build_messages,
    build_weekly_summary_messages,
)
from app.models.goal import GoalRequest
from tests.availability import week_with_days


def test_default_language_is_vietnamese():
    assert i18n.get_language() == "vi"


def test_unknown_language_raises(monkeypatch):
    monkeypatch.setattr(config, "APP_LANGUAGE", "xx")
    with pytest.raises(ValueError):
        i18n.get_language()
    with pytest.raises(RuntimeError, match="APP_LANGUAGE"):
        config.validate_config()


def test_language_instruction_names_language():
    assert "Vietnamese" in i18n.language_instruction()


def test_plan_prompt_has_instruction():
    goal = GoalRequest(
        distance="half_marathon", target_time="1:55:00", race_date="2030-01-01",
        fitness_level="intermediate", weekly_availability=week_with_days(4),
    )
    assert i18n.language_instruction() in build_messages(goal)[0]["content"]


def test_weekly_summary_prompt_has_instruction():
    messages = build_weekly_summary_messages(1, [])
    assert i18n.language_instruction() in messages[0]["content"]


def test_analysis_prompt_has_instruction():
    class P:
        workout_type, distance_km, pace_zone = "easy", 5, "Z2"

    class A:
        distance, moving_time, average_heartrate = 5000, 1800, None

    messages = build_activity_analysis_messages(P, A)
    assert i18n.language_instruction() in messages[0]["content"]
