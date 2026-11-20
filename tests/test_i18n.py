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
        vdot=40.0, weekly_km=40, longest_run_km=18, weekly_availability=week_with_days(4),
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


def _analysis_text(profile):
    class P:
        workout_type, distance_km, pace_zone = "tempo", 8, "T"

    class A:
        distance, moving_time, average_heartrate = 8000, 2400, 168

    return "\n".join(m["content"] for m in build_activity_analysis_messages(P, A, profile))


def test_analysis_prompt_includes_lactate_threshold_when_set():
    text = _analysis_text({"max_hr": 190, "resting_hr": 50, "lactate_threshold_hr": 171})
    assert "171" in text and "lactate" in text.lower()


def test_analysis_prompt_omits_lactate_threshold_when_unset():
    for profile in (None, {"max_hr": 190, "resting_hr": 50}, {"lactate_threshold_hr": None}):
        assert "lactate" not in _analysis_text(profile).lower()
