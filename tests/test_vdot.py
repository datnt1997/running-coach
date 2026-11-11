import pytest

from app.vdot import (
    break_factor,
    planner_label,
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


def test_planner_label():
    assert [planner_label(v) for v in (20, 34.9, 35, 40.2, 49.9, 50, 80)] == [
        "beginner", "beginner", "intermediate", "intermediate", "intermediate", "advanced", "advanced",
    ]


def test_break_factor_table_15_1():
    assert break_factor(0) == 1.0
    assert break_factor(5) == 1.0
    assert break_factor(42) == pytest.approx(0.889, abs=0.001)
    assert break_factor(42, cross_trained=True) == pytest.approx(0.944, abs=0.001)
    assert break_factor(200) == 0.8
    assert break_factor(200, cross_trained=True) == 0.9
