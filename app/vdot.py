"""Daniels-Gilbert VDOT: race result <-> VDOT, training paces, break factor.

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


# Training paces (Daniels, Table 5.2, p. 136). Each intensity runs at a fixed share
# of VO2max, so the pace for a VDOT follows from the same oxygen-cost formula.
# The shares were fitted to the printed table: E 63-73%, T 88%, I 97.3%. Marathon
# pace rises from 78% at VDOT 30 to 82.5% at VDOT 60, so it is interpolated.
_EASY_SLOW, _EASY_FAST = 0.63, 0.73
_THRESHOLD, _INTERVAL = 0.88, 0.973
_MARATHON_SHARE = ((30, 0.778), (40, 0.802), (50, 0.817), (60, 0.825))


def _marathon_share(vdot: float) -> float:
    if vdot <= _MARATHON_SHARE[0][0]:
        return _MARATHON_SHARE[0][1]
    for (v0, s0), (v1, s1) in zip(_MARATHON_SHARE, _MARATHON_SHARE[1:]):
        if vdot <= v1:
            return s0 + (s1 - s0) * (vdot - v0) / (v1 - v0)
    return _MARATHON_SHARE[-1][1]


def _seconds_per_km(vdot: float, share: float) -> int:
    """Seconds per km at `share` of VO2max for this VDOT."""
    c = -4.6 - vdot * share
    metres_per_min = (-0.182258 + math.sqrt(0.182258**2 - 4 * 0.000104 * c)) / (2 * 0.000104)
    return round(1000 / metres_per_min * 60)


def training_paces(vdot: float) -> dict[str, int]:
    """Daniels training paces for a VDOT, in whole seconds per km.

    Keys: easy_fast, easy_slow (the E range), marathon, threshold, interval.
    """
    if vdot <= 0:
        raise ValueError("vdot must be positive")
    return {
        "easy_fast": _seconds_per_km(vdot, _EASY_FAST),
        "easy_slow": _seconds_per_km(vdot, _EASY_SLOW),
        "marathon": _seconds_per_km(vdot, _marathon_share(vdot)),
        "threshold": _seconds_per_km(vdot, _THRESHOLD),
        "interval": _seconds_per_km(vdot, _INTERVAL),
    }


def format_pace(seconds_per_km: int) -> str:
    return f"{seconds_per_km // 60}:{seconds_per_km % 60:02d}"


def break_factor(days_off: int, cross_trained: bool = False) -> float:
    """Multiplier on VDOT after days_off days without running (Table 15.1, p. 382)."""
    over = max(0, days_off - 5)
    if cross_trained:
        return max(0.900, 1 - 0.0015 * over)
    return max(0.800, 1 - 0.003 * over)
