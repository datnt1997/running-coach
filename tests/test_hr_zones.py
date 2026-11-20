import pytest

from app.hr_zones import heart_rate_zones, missing_for_zones, profile_zones, target_zone, zone_for_bpm


def test_zones_match_the_garmin_screen():
    # Max 194, resting 48 (HRR 146): Garmin shows Z1 120-139, Z2 140-155,
    # Z3 156-170, Z4 171-178, Z5 above 178.
    zones = heart_rate_zones(max_hr=194, resting_hr=48)
    assert [(z["min"], z["max"]) for z in zones] == [
        (120, 139), (140, 155), (156, 170), (171, 178), (179, 194)]


def test_zones_are_shares_of_heart_rate_reserve_with_z5_ending_at_max():
    zones = heart_rate_zones(max_hr=190, resting_hr=50)
    # HRR 140. Each zone starts at 50 + 140 * share, rounded half up: 118.6 -> 119,
    # 138.2 -> 138, 153.6 -> 154, 167.6 -> 168, 176; the zone before ends one lower.
    assert zones == [
        {"zone": 1, "min": 119, "max": 137},
        {"zone": 2, "min": 138, "max": 153},
        {"zone": 3, "min": 154, "max": 167},
        {"zone": 4, "min": 168, "max": 175},
        {"zone": 5, "min": 176, "max": 190},
    ]


@pytest.mark.parametrize("max_hr, resting", [(170, 170), (160, 170), (0, 50), (190, 0)])
def test_inconsistent_values_are_refused_not_guessed(max_hr, resting):
    with pytest.raises(ValueError):
        heart_rate_zones(max_hr, resting)


def test_missing_values_are_named():
    assert missing_for_zones({"max_hr": None, "resting_hr": 50}) == ["max_hr"]
    assert missing_for_zones({"max_hr": None, "resting_hr": None}) == ["max_hr", "resting_hr"]
    assert missing_for_zones({"max_hr": 190, "resting_hr": 50}) == []


def test_target_zone_by_workout_type():
    zones = heart_rate_zones(190, 50)
    assert target_zone("easy", zones) == {"minZone": 2, "maxZone": 2, "min": 138, "max": 153}
    assert target_zone("recovery", zones) == {"minZone": 1, "maxZone": 1, "min": 119, "max": 137}
    assert target_zone("long", zones)["minZone"] == 2
    assert target_zone("marathon_pace", zones)["minZone"] == 3
    assert target_zone("tempo", zones)["minZone"] == 4
    assert target_zone("interval", zones) == {"minZone": 5, "maxZone": 5, "min": 176, "max": 190}


def test_an_average_heart_rate_falls_in_its_zone_or_nowhere():
    zones = heart_rate_zones(190, 50)
    assert zone_for_bpm(100, zones) == "Z1"  # below the Z1 minimum still counts as Z1
    assert zone_for_bpm(145, zones) == "Z2"
    assert zone_for_bpm(167, zones) == "Z3"
    assert zone_for_bpm(168, zones) == "Z4"
    assert zone_for_bpm(175, zones) == "Z4"
    assert zone_for_bpm(176, zones) == "Z5"
    assert zone_for_bpm(185, zones) == "Z5"
    assert zone_for_bpm(None, zones) is None
    assert zone_for_bpm(145, None) is None  # no profile: no guessed zone


def test_zone_range_text_lists_every_zone_with_both_edges():
    from app.hr_zones import zone_range_text
    assert zone_range_text(heart_rate_zones(190, 50)) == (
        "Z1 119-137 bpm; Z2 138-153 bpm; Z3 154-167 bpm; Z4 168-175 bpm; Z5 176-190 bpm")


def test_workouts_without_a_heart_rate_target_have_none():
    zones = heart_rate_zones(190, 50)
    for kind in ("rest", "race", "cross", "something_new"):
        assert target_zone(kind, zones) is None
    assert target_zone("easy", None) is None


def test_periodization_text_matches_target_zones():
    from app.agent.prompt import SYSTEM_PROMPT
    assert "tempo runs (Z4) and intervals (Z5)" in SYSTEM_PROMPT


def test_lactate_threshold_does_not_change_zones_or_missing():
    base = {"max_hr": 190, "resting_hr": 50}
    with_lthr = {**base, "lactate_threshold_hr": 171}
    assert profile_zones(with_lthr) == profile_zones(base)
    assert missing_for_zones({"lactate_threshold_hr": 171}) == ["max_hr", "resting_hr"]
