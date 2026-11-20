"""Heart-rate zones from maximum and resting heart rate (Garmin's default %HRR zones).

This is the heart-rate-reserve (Karvonen) method: HRR = max HR - resting HR and
bpm = resting HR + share * HRR. Garmin's default bands, as a share of HRR:
Z1 49-63%, Z2 63-74%, Z3 74-84%, Z4 84-90%, Z5 90-100% (Z5 ends at max HR).
Edges are rounded half up to whole bpm; each zone starts one bpm above the
previous one. The model never invents a zone: only these values reach a prompt or the UI.
"""

from __future__ import annotations

import math

# Z1 lower edge, then each zone's upper edge, as a share of heart-rate reserve.
_LOWER_SHARE = 0.49
_UPPER_SHARE = (0.63, 0.74, 0.84, 0.90, 1.00)

# Target zone range (min, max) per workout type. Types missing here (rest, race,
# cross) have no heart-rate target.
_TARGET = {
    "recovery": (1, 1),
    "shakeout": (1, 2),
    "easy": (2, 2),
    "long": (2, 2),
    "marathon_pace": (3, 3),
    "tempo": (4, 4),
    "interval": (5, 5),
}


def missing_for_zones(profile: dict | None) -> list[str]:
    profile = profile or {}
    return [k for k in ("max_hr", "resting_hr") if not profile.get(k)]


def _bpm(resting_hr: int, reserve: int, share: float) -> int:
    return math.floor(resting_hr + share * reserve + 0.5)  # half up, not banker's rounding


def heart_rate_zones(max_hr: int, resting_hr: int) -> list[dict]:
    """Five zones as {zone, min, max} in whole bpm."""
    if max_hr <= 0 or resting_hr <= 0:
        raise ValueError("heart rates must be positive")
    if resting_hr >= max_hr:
        raise ValueError("resting heart rate must be below maximum heart rate")
    reserve = max_hr - resting_hr
    zones, lower = [], _bpm(resting_hr, reserve, _LOWER_SHARE)
    for i, share in enumerate(_UPPER_SHARE, start=1):
        upper = max_hr if share == 1.0 else _bpm(resting_hr, reserve, share)
        zones.append({"zone": i, "min": lower, "max": upper})
        lower = upper + 1
    return zones


def profile_zones(profile: dict | None) -> list[dict] | None:
    """Zones for a profile row, or None when it lacks (or has inconsistent) values."""
    if missing_for_zones(profile):
        return None
    try:
        return heart_rate_zones(profile["max_hr"], profile["resting_hr"])
    except ValueError:
        return None


def zone_for_bpm(bpm: float | None, zones: list[dict] | None) -> str | None:
    """The zone label ("Z2") an average heart rate falls in; None without zones or a reading.

    Below the Z1 minimum still counts as Z1; above the maximum, the top zone."""
    if bpm is None or zones is None:
        return None
    for z in zones:
        if z["max"] >= bpm:
            return f"Z{z['zone']}"
    return f"Z{zones[-1]['zone']}"


def zone_range_text(zones: list[dict]) -> str:
    """One line for a prompt: "Z1 119-138 bpm; Z2 139-154 bpm; ..."."""
    return "; ".join(f"Z{z['zone']} {z['min']}-{z['max']} bpm" for z in zones)


def target_zone(workout_type: str, zones: list[dict] | None) -> dict | None:
    """The zone range a workout type should be run in, with its bpm limits."""
    span = _TARGET.get(workout_type)
    if zones is None or span is None:
        return None
    lo, hi = span
    return {
        "minZone": lo, "maxZone": hi,
        "min": zones[lo - 1]["min"], "max": zones[hi - 1]["max"],
    }
