import pytest

from app.hr_zones import heart_rate_zones, missing_for_zones, target_zone, zone_for_bpm


def test_zones_follow_lactate_threshold_with_z5_ending_at_max():
    zones = heart_rate_zones(max_hr=190, lactate_threshold_hr=170)
    # Worked by hand from LTHR 170: Z1 <81%, Z2 81-89%, Z3 90-93%, Z4 94-99%, Z5 100%-max.
    assert zones == [
        {"zone": 1, "min": None, "max": 138},
        {"zone": 2, "min": 139, "max": 151},
        {"zone": 3, "min": 152, "max": 158},
        {"zone": 4, "min": 159, "max": 168},
        {"zone": 5, "min": 169, "max": 190},
    ]


@pytest.mark.parametrize("max_hr, lt", [(170, 170), (160, 170), (0, 150), (190, 0)])
def test_inconsistent_values_are_refused_not_guessed(max_hr, lt):
    with pytest.raises(ValueError):
        heart_rate_zones(max_hr, lt)


def test_missing_values_are_named():
    assert missing_for_zones({"max_hr": None, "lactate_threshold_hr": 170}) == ["max_hr"]
    assert missing_for_zones({"max_hr": None, "lactate_threshold_hr": None}) == [
        "max_hr", "lactate_threshold_hr"]
    assert missing_for_zones({"max_hr": 190, "lactate_threshold_hr": 170}) == []


def test_target_zone_by_workout_type():
    zones = heart_rate_zones(190, 170)
    assert target_zone("easy", zones) == {"minZone": 2, "maxZone": 2, "min": 139, "max": 151}
    assert target_zone("recovery", zones) == {"minZone": 1, "maxZone": 1, "min": None, "max": 138}
    assert target_zone("long", zones)["minZone"] == 2
    assert target_zone("marathon_pace", zones)["minZone"] == 3
    assert target_zone("tempo", zones)["minZone"] == 4
    assert target_zone("interval", zones) == {"minZone": 5, "maxZone": 5, "min": 169, "max": 190}


def test_an_average_heart_rate_falls_in_its_zone_or_nowhere():
    zones = heart_rate_zones(190, 170)
    assert zone_for_bpm(100, zones) == "Z1"
    assert zone_for_bpm(145, zones) == "Z2"
    assert zone_for_bpm(168, zones) == "Z4"
    assert zone_for_bpm(185, zones) == "Z5"
    assert zone_for_bpm(None, zones) is None
    assert zone_for_bpm(145, None) is None  # no profile: no guessed zone


def test_workouts_without_a_heart_rate_target_have_none():
    zones = heart_rate_zones(190, 170)
    for kind in ("rest", "race", "cross", "something_new"):
        assert target_zone(kind, zones) is None
    assert target_zone("easy", None) is None


def test_periodization_text_matches_target_zones():
    from app.agent.prompt import SYSTEM_PROMPT
    assert "tempo runs (Z4) and intervals (Z5)" in SYSTEM_PROMPT
