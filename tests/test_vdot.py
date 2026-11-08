import pytest

from app.vdot import (
    break_factor,
    fitness_label,
    level_for,
    level_thresholds,
    race_time_for_vdot,
    vdot_from_race,
)

K5, K10, HM, FM = 5000, 10000, 21097.5, 42195


def secs(t: str) -> int:
    n = 0
    for part in t.split(":"):
        n = n * 60 + int(part)
    return n


# Table 5.6 (p. 151-154): printed race times at exact level VDOTs.
TABLE_56 = [
    # vdot, 5K, 10K, half, marathon
    (35.0, "26:59", "56:03", "2:04:13", "4:16:02"),  # male level 1
    (50.0, "19:56", "41:21", "1:31:36", "3:10:49"),  # male level 4
    (65.0, "15:54", "33:01", "1:12:54", "2:32:35"),  # male level 7
    (80.0, "13:18", "27:41", "1:00:55", "2:07:39"),  # male level 10
    (31.4, "29:32", "1:01:24", "2:15:55", "4:39:07"),  # female level 1
    (53.4, "18:50", "39:05", "1:26:30", "3:00:29"),  # female level 6
]


@pytest.mark.parametrize("vdot,t5,t10,thm,tfm", TABLE_56)
def test_vdot_from_race_matches_table(vdot, t5, t10, thm, tfm):
    for dist, t in ((K5, t5), (K10, t10), (HM, thm), (FM, tfm)):
        assert vdot_from_race(dist, secs(t)) == pytest.approx(vdot, abs=0.15)


@pytest.mark.parametrize("vdot,t5,t10,thm,tfm", TABLE_56)
def test_race_time_for_vdot_within_one_percent(vdot, t5, t10, thm, tfm):
    for dist, t in ((K5, t5), (K10, t10), (HM, thm), (FM, tfm)):
        assert race_time_for_vdot(vdot, dist) == pytest.approx(secs(t), rel=0.01)


def test_race_time_inverts_vdot():
    t = race_time_for_vdot(45.0, HM)
    assert vdot_from_race(HM, t) == pytest.approx(45.0, abs=1e-6)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        vdot_from_race(0, 100)
    with pytest.raises(ValueError):
        race_time_for_vdot(0, 5000)


def test_levels_table_56():
    assert level_thresholds("male", 30)[0] == pytest.approx(35.0)
    assert level_thresholds("male", 30)[9] == pytest.approx(80.0)
    assert level_thresholds("female", 30)[3] == pytest.approx(44.6)
    assert level_for(45.0, "male", 30) == 3
    assert level_for(45.0, "female", 30) == 4  # the gap this feature fixes
    assert level_for(10.0, "male", 30) == 1
    assert level_for(99.0, "female", 30) == 10


def test_unknown_sex_and_age_use_male_unadjusted():
    assert level_for(50.0) == level_for(50.0, "male", 30) == 4


def test_age_adjustment_book_example_58_year_old_woman():
    # 7:00 on 1600 m is VDOT 40.5 = level 7 at 58 (Table 5.8), level 3 when young.
    assert level_for(40.5, "female", 58) == 7
    assert level_for(40.5, "female", 30) == 3
    assert level_for(36.0, "female", 58) == 6


def test_age_adjustment_book_example_10_year_old_girl():
    # 7:18 on 1600 m is VDOT 38.6 = level 6 at 10 (Table 5.7), same as an
    # 18-year-old woman at 53.4.
    assert level_for(38.6, "female", 10) == 6
    assert level_for(53.4, "female", 18) == 6


def test_age_39_lowers_thresholds_and_adults_are_equal():
    assert level_thresholds("male", 38) == level_thresholds("male", 18)
    assert level_thresholds("male", 39)[0] == pytest.approx(34.1)
    assert level_thresholds("female", 39)[9] == pytest.approx(70.5)
    assert level_for(34.5, "male", 39) == 1
    assert level_for(34.5, "male", 38) == 1  # 34.5 < 35.0 clamps to 1
    assert level_for(40.0, "male", 39) == 2  # needs 39.1 at 39, 40.0 at 38


def test_age_clamped_beyond_book_range():
    assert level_thresholds("male", 70) == level_thresholds("male", 58)
    assert level_thresholds("male", 3) == level_thresholds("male", 6)


def test_fitness_label():
    assert [fitness_label(n) for n in (1, 2, 3, 5, 6, 10)] == [
        "beginner", "beginner", "intermediate", "intermediate", "advanced", "advanced",
    ]


def test_break_factor_table_15_1():
    assert break_factor(0) == 1.0
    assert break_factor(5) == 1.0
    assert break_factor(42) == pytest.approx(0.889, abs=0.001)
    assert break_factor(42, cross_trained=True) == pytest.approx(0.944, abs=0.001)
    assert break_factor(200) == 0.8
    assert break_factor(200, cross_trained=True) == 0.9
