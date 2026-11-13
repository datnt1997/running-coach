"""Helpers that build a Weekly availability for tests."""

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_PICK_ORDER = ["Mon", "Wed", "Fri", "Sat", "Tue", "Thu", "Sun"]


def week_with_days(n: int) -> list[dict]:
    """n Training days with one slot each, no cap, Quality workouts allowed."""
    chosen = set(_PICK_ORDER[:n])
    return [
        {"day": d, "slots": 1 if d in chosen else 0, "maxKm": None, "qualityAllowed": True}
        for d in DAYS
    ]
