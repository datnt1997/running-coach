"""Daniels-Gilbert VDOT: race result <-> VDOT, planner label, break factor.

The break factor comes from Daniels' Running Formula, Table 15.1 (p. 382).
"""

from __future__ import annotations

import math
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


def planner_label(vdot: float) -> str:
    """Internal label the plan generator needs. Never shown to the runner.

    Cut-offs are ours, not Daniels': below 35 (slower than about a 2:04 half
    marathon) beginner, below 50 (about 1:31) intermediate, else advanced.
    """
    if vdot < 35:
        return "beginner"
    if vdot < 50:
        return "intermediate"
    return "advanced"


def break_factor(days_off: int, cross_trained: bool = False) -> float:
    """Multiplier on VDOT after days_off days without running (Table 15.1, p. 382)."""
    over = max(0, days_off - 5)
    if cross_trained:
        return max(0.900, 1 - 0.0015 * over)
    return max(0.800, 1 - 0.003 * over)
