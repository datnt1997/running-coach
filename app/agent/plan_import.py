"""Parse a pasted or CSV plan into Planned workouts (no AI, no guessing).

Header row required: week, phase, day, type, distance_km; optional pace_zone, notes.
Cells are comma or tab separated (a paste from a Sheet is tab separated).
Every bad row is reported with its line number; nothing is repaired.
"""

import csv
import io
from dataclasses import dataclass

from app.models.goal import MAX_WORKOUT_KM, WEEKDAYS

REQUIRED = ("week", "phase", "day", "type", "distance_km")
OPTIONAL = ("pace_zone", "notes")


@dataclass(frozen=True)
class RowError:
    line: int
    message: str


class PlanImportError(Exception):
    def __init__(self, errors: list[RowError]):
        self.errors = errors
        super().__init__("; ".join(f"line {e.line}: {e.message}" for e in errors))


@dataclass(frozen=True)
class ImportedWorkout:
    week_number: int
    phase: str
    day: str
    workout_type: str
    distance_km: float
    pace_zone: str | None
    notes: str | None


def parse_plan_csv(text: str) -> list[ImportedWorkout]:
    lines = [(n, raw) for n, raw in enumerate(text.splitlines(), start=1) if raw.strip()]
    if not lines:
        raise PlanImportError([RowError(1, "no rows to import")])

    header_line, header_raw = lines[0]
    delimiter = "\t" if "\t" in header_raw else ","
    header = [c.strip().lower() for c in next(csv.reader([header_raw], delimiter=delimiter))]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise PlanImportError(
            [RowError(header_line, f"missing column(s): {', '.join(missing)}")]
        )
    if len(lines) == 1:
        raise PlanImportError([RowError(header_line, "no workout rows after the header")])

    index = {name: header.index(name) for name in REQUIRED + OPTIONAL if name in header}
    workouts: list[ImportedWorkout] = []
    errors: list[RowError] = []

    for line_no, raw in lines[1:]:
        cells = [c.strip() for c in next(csv.reader([raw], delimiter=delimiter))]
        if len(cells) < len(REQUIRED) or len(cells) < max(index[c] for c in REQUIRED) + 1:
            errors.append(RowError(line_no, "too few cells"))
            continue

        def cell(name: str) -> str | None:
            i = index.get(name)
            return (cells[i] or None) if i is not None and i < len(cells) else None

        problems: list[str] = []
        week = _int(cell("week"))
        if week is None or week < 1:
            problems.append(f"week must be a whole number from 1, got {cell('week')!r}")
        day = next((d for d in WEEKDAYS if d.lower() == (cell("day") or "").lower()), None)
        if day is None:
            problems.append(f"day must be one of {', '.join(WEEKDAYS)}, got {cell('day')!r}")
        distance = _float(cell("distance_km"))
        if distance is None or not 0 <= distance <= MAX_WORKOUT_KM:
            problems.append(
                f"distance_km must be a number from 0 to {MAX_WORKOUT_KM}, got {cell('distance_km')!r}"
            )
        if cell("phase") is None:
            problems.append("phase is empty")
        if cell("type") is None:
            problems.append("type is empty")

        if problems:
            errors.append(RowError(line_no, "; ".join(problems)))
            continue
        workouts.append(
            ImportedWorkout(
                week_number=week,
                phase=cell("phase"),
                day=day,
                workout_type=cell("type"),
                distance_km=distance,
                pace_zone=cell("pace_zone"),
                notes=cell("notes"),
            )
        )

    if errors:
        raise PlanImportError(errors)
    return workouts


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
