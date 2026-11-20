"""Heart-rate zones from maximum and lactate-threshold heart rate.

Zone edges are shares of lactate-threshold HR (LTHR), after Friel's running zones:
Z1 below 81%, Z2 81-89%, Z3 90-93%, Z4 94-99%, Z5 from 100% up to maximum HR.
The model never invents a zone: only these values reach a prompt or the UI.
"""

from __future__ import annotations

# Upper edge of Z1-Z4 as a share of LTHR; Z5 ends at max HR.
_UPPER_SHARE = (0.81, 0.89, 0.93, 0.99)

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
    return [k for k in ("max_hr", "lactate_threshold_hr") if not profile.get(k)]


def heart_rate_zones(max_hr: int, lactate_threshold_hr: int) -> list[dict]:
    """Five zones as {zone, min, max} in whole bpm; Z1 has no lower edge."""
    if max_hr <= 0 or lactate_threshold_hr <= 0:
        raise ValueError("heart rates must be positive")
    if lactate_threshold_hr >= max_hr:
        raise ValueError("lactate-threshold heart rate must be below maximum heart rate")
    uppers = [round(lactate_threshold_hr * s) for s in _UPPER_SHARE] + [max_hr]
    zones, lower = [], None
    for i, upper in enumerate(uppers, start=1):
        zones.append({"zone": i, "min": lower, "max": upper})
        lower = upper + 1
    return zones


def profile_zones(profile: dict | None) -> list[dict] | None:
    """Zones for a profile row, or None when it lacks (or has inconsistent) values."""
    if missing_for_zones(profile):
        return None
    try:
        return heart_rate_zones(profile["max_hr"], profile["lactate_threshold_hr"])
    except ValueError:
        return None


def zone_for_bpm(bpm: float | None, zones: list[dict] | None) -> str | None:
    """The zone label ("Z2") an average heart rate falls in; None without zones or a reading."""
    if bpm is None or zones is None:
        return None
    for z in zones:
        if z["max"] >= bpm:
            return f"Z{z['zone']}"
    return f"Z{zones[-1]['zone']}"  # above the stored maximum: still the top zone


def zone_range_text(zones: list[dict]) -> str:
    """One line for a prompt: "Z1 up to 138 bpm; Z2 139-151 bpm; ..."."""
    parts = []
    for z in zones:
        span = f"up to {z['max']}" if z["min"] is None else f"{z['min']}-{z['max']}"
        parts.append(f"Z{z['zone']} {span} bpm")
    return "; ".join(parts)


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
