"""Daniels-Gilbert VDOT: race result <-> VDOT, level grading, break factor.

Level data comes from Daniels' Running Formula, Tables 5.6 to 5.8 (pp. 151-159)
and Table 15.1 (p. 382). Only the small thresholds we need are stored here.
"""

from __future__ import annotations

import math
from typing import Literal

Sex = Literal["male", "female"]

# Table 5.6 thresholds for level 1..10 (aged 18-38): start + step * (level - 1).
_LEVEL1 = {"male": 35.0, "female": 31.4}
_STEP = {"male": 5.0, "female": 4.4}

# Tables 5.7 / 5.8: age -> (level 1 male, level 1 female, level 10 male, level 10 female).
# Thresholds between level 1 and 10 are linear in level.
_AGE_BOUNDS: dict[int, tuple[float, float, float, float]] = {
    6: (16.1, 16.1, 40.4, 40.4),
    7: (17.7, 17.4, 44.2, 43.5),
    8: (19.3, 18.7, 47.9, 46.5),
    9: (20.9, 20.0, 51.5, 49.4),
    10: (22.5, 21.3, 55.0, 52.2),
    11: (24.1, 22.6, 58.4, 54.9),
    12: (25.7, 23.9, 61.8, 57.5),
    13: (27.3, 25.2, 65.1, 60.0),
    14: (28.9, 26.5, 68.3, 62.4),
    15: (30.5, 27.8, 71.4, 64.7),
    16: (32.0, 29.0, 74.4, 66.9),
    17: (33.5, 30.2, 77.3, 69.0),
    18: (35.0, 31.4, 80.0, 71.0),
    39: (34.1, 30.4, 79.1, 70.5),
    40: (33.2, 29.5, 78.2, 69.6),
    41: (32.4, 28.7, 77.4, 68.8),
    42: (31.5, 27.8, 76.5, 67.9),
    43: (30.6, 26.9, 75.6, 67.0),
    44: (29.7, 26.0, 74.7, 66.1),
    45: (28.8, 25.1, 73.8, 65.2),
    46: (28.0, 24.3, 73.0, 64.4),
    47: (27.1, 23.4, 72.1, 63.5),
    48: (26.2, 22.5, 71.2, 62.6),
    49: (25.3, 21.6, 70.3, 61.7),
    50: (24.4, 20.7, 69.4, 60.8),
    51: (23.6, 19.9, 68.6, 59.9),
    52: (22.7, 19.0, 67.7, 59.1),
    53: (21.8, 18.1, 66.8, 58.2),
    54: (20.9, 17.2, 65.9, 57.3),
    55: (20.0, 16.3, 65.0, 56.4),
    56: (19.2, 15.5, 64.2, 55.5),
    57: (18.3, 14.6, 63.3, 54.7),
    58: (17.4, 13.7, 62.4, 53.8),
}
_MIN_AGE, _MAX_AGE = 6, 58


def _velocity_vo2(distance_m: float, minutes: float) -> tuple[float, float]:
    v = distance_m / minutes  # metres per minute
    vo2 = -4.6 + 0.182258 * v + 0.000104 * v * v
    pct = (
        0.8
        + 0.1894393 * math.exp(-0.012778 * minutes)
        + 0.2989558 * math.exp(-0.1932605 * minutes)
    )
    return vo2, pct


def vdot_from_race(distance_m: float, seconds: float) -> float:
    """Daniels-Gilbert VDOT for a race of distance_m metres run in seconds."""
    if distance_m <= 0 or seconds <= 0:
        raise ValueError("distance and time must be positive")
    vo2, pct = _velocity_vo2(distance_m, seconds / 60)
    return vo2 / pct


def race_time_for_vdot(vdot: float, distance_m: float) -> float:
    """Seconds a runner of this VDOT needs for distance_m (inverse of vdot_from_race)."""
    if vdot <= 0 or distance_m <= 0:
        raise ValueError("vdot and distance must be positive")
    lo, hi = 1.0, 24 * 3600.0  # VDOT falls as time grows, so bisect
    for _ in range(100):
        mid = (lo + hi) / 2
        if vdot_from_race(distance_m, mid) > vdot:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def level_thresholds(sex: Sex, age: int | None) -> list[float]:
    """VDOT needed for book levels 1..10 for this sex and age (Tables 5.6-5.8)."""
    s = 0 if sex == "male" else 1
    if age is None or 18 <= age <= 38:
        lo = _LEVEL1[sex]
        return [lo + _STEP[sex] * i for i in range(10)]
    bounded = min(max(age, _MIN_AGE), _MAX_AGE)
    bounds = _AGE_BOUNDS[bounded]
    lo, hi = bounds[s], bounds[2 + s]
    return [lo + (hi - lo) * i / 9 for i in range(10)]


def level_for(vdot: float, sex: Sex | None = None, age: int | None = None) -> int:
    """Book level 1..10. Unknown sex uses the male column; unknown age gets no adjustment."""
    thresholds = level_thresholds(sex or "male", age)
    level = 1
    for i, t in enumerate(thresholds, start=1):
        if vdot >= t:
            level = i
    return level


def fitness_label(level: int) -> str:
    """Planner label for a book level. Our choice, not the book's (research.md R3)."""
    if level <= 2:
        return "beginner"
    if level <= 5:
        return "intermediate"
    return "advanced"


def break_factor(days_off: int, cross_trained: bool = False) -> float:
    """Multiplier on VDOT after days_off days without running (Table 15.1, p. 382)."""
    over = max(0, days_off - 5)
    if cross_trained:
        return max(0.900, 1 - 0.0015 * over)
    return max(0.800, 1 - 0.003 * over)
