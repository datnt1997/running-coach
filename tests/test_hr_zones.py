import pytest

from app.hr_zones import heart_rate_zones, missing_for_zones, target_zone, zone_for_bpm


def test_zones_are_shares_of_heart_rate_reserve_with_z5_ending_at_max():
    zones = heart_rate_zones(max_hr=190, resting_hr=50)
    # HRR 140. Worked by hand: 50 + 140 * share, rounded half up to whole bpm.
    # Z1 49-63%: 118.6 -> 119 .. 138.2 -> 138; Z2 to 74%: 153.6 -> 154;
    # Z3 to 84%: 167.6 -> 168; Z4 to 90%: 176; Z5 to max HR 190.
    assert zones == [
        {"zone": 1, "min": 119, "max": 138},
        {"zone": 2, "min": 139, "max": 154},
        {"zone": 3, "min": 155, "max": 168},
        {"zone": 4, "min": 169, "max": 176},
        {"zone": 5, "min": 177, "max": 190},
    ]


@pytest.mark.parametrize("max_hr, resting", [(170, 170), (160, 170), (0, 50), (190, 0)])
def test_inconsistent_values_are_refused_not_guessed(max_hr, resting):
    with pytest.raises(ValueError):
        heart_rate_zones(max_hr, resting)


def test_missing_values_are_named():
    assert missing_for_zones({"max_hr": None, "resting_hr": 50}) == ["max_hr"]
    assert missing_for_zones({"max_hr": None, "resting_hr": None}) == ["max_hr", "resting_hr"]
    assert missing_for_zones({"max_hr": 190, "resting_hr": 50}) == []
    # The lactate-threshold heart rate is not needed for zones.
    assert missing_for_zones({"max_hr": 190, "resting_hr": 50, "lactate_threshold_hr": None}) == []


def test_target_zone_by_workout_type():
    zones = heart_rate_zones(190, 50)
    assert target_zone("easy", zones) == {"minZone": 2, "maxZone": 2, "min": 139, "max": 154}
    assert target_zone("recovery", zones) == {"minZone": 1, "maxZone": 1, "min": 119, "max": 138}
    assert target_zone("long", zones)["minZone"] == 2
    assert target_zone("marathon_pace", zones)["minZone"] == 3
    assert target_zone("tempo", zones)["minZone"] == 4
    assert target_zone("interval", zones) == {"minZone": 5, "maxZone": 5, "min": 177, "max": 190}


def test_an_average_heart_rate_falls_in_its_zone_or_nowhere():
    zones = heart_rate_zones(190, 50)
    assert zone_for_bpm(100, zones) == "Z1"  # below the Z1 minimum still counts as Z1
    assert zone_for_bpm(145, zones) == "Z2"
    assert zone_for_bpm(168, zones) == "Z3"
    assert zone_for_bpm(176, zones) == "Z4"
    assert zone_for_bpm(185, zones) == "Z5"
    assert zone_for_bpm(None, zones) is None
    assert zone_for_bpm(145, None) is None  # no profile: no guessed zone


def test_zone_range_text_lists_every_zone_with_both_edges():
    from app.hr_zones import zone_range_text
    assert zone_range_text(heart_rate_zones(190, 50)) == (
        "Z1 119-138 bpm; Z2 139-154 bpm; Z3 155-168 bpm; Z4 169-176 bpm; Z5 177-190 bpm")


def test_workouts_without_a_heart_rate_target_have_none():
    zones = heart_rate_zones(190, 50)
    for kind in ("rest", "race", "cross", "something_new"):
        assert target_zone(kind, zones) is None
    assert target_zone("easy", None) is None


def test_periodization_text_matches_target_zones():
    from app.agent.prompt import SYSTEM_PROMPT
    assert "tempo runs (Z4) and intervals (Z5)" in SYSTEM_PROMPT
