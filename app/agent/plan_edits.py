"""The Plan chat's edit step: the request the coach hands over, the edit model's prompt, its proposal.

The chat model never edits the Plan. It ends a reply with [[EDIT: <request>]]; the edit
model (PLAN_EDIT_AI_PROVIDER) turns the request into a propose_plan_edit tool call;
`app.agent.validation.check_plan_edit` decides whether it may be shown to the Runner.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import date, timedelta

from app.agent.validation import WEEKDAYS, long_run_limit_km, reason_text

_MARKER = re.compile(r"\[\[EDIT:\s*(.*?)\s*\]\]", re.DOTALL)
_UNCLOSED_MARKER = re.compile(r"\[\[EDIT:.*", re.DOTALL)
MAX_REQUEST_CHARS = 500


def split_edit_request(reply: str) -> tuple[str, str | None]:
    """The reply without its [[EDIT: ...]] marker, and the requested change if there is one."""
    found = _MARKER.findall(reply)
    visible = _UNCLOSED_MARKER.sub("", _MARKER.sub("", reply)).strip()
    request = " ".join(found[0].split()) if found else ""
    return visible, (request[:MAX_REQUEST_CHARS] or None)


def workout(type_: str, km, pace_zone=None, notes=None) -> dict:
    return {
        "type": str(type_).strip(),
        "distanceKm": round(float(km or 0), 2),
        "paceZone": pace_zone or None,
        "notes": notes or None,
    }


def plan_days(rows: list[dict]) -> dict[int, dict[str, list[dict]]]:
    """A Plan's workout rows as week -> day -> workouts."""
    out: dict[int, dict[str, list[dict]]] = {}
    for r in rows:
        out.setdefault(r["week_number"], {}).setdefault(r["day_of_week"], []).append(
            workout(r["workout_type"], r["distance_km"], r["pace_zone"], r["notes"])
        )
    return out


def plain(value):
    """Tool-call arguments as plain dicts and lists (Gemini returns proto containers)."""
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [plain(v) for v in value]
    if hasattr(value, "items"):
        return {k: plain(v) for k, v in value.items()}
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        return [plain(v) for v in value]
    return value


def parse_proposal(arguments: dict) -> dict[int, dict[str, list[dict]]]:
    """The tool call's weeks as week -> day -> workouts. Raises ValueError on malformed input.

    A proposal that only asks for a Goal change may give no weeks; the rules reject it as such.
    """
    weeks = arguments.get("weeks")
    if weeks is None and arguments.get("goal_change"):
        weeks = []
    if not isinstance(weeks, list) or not (weeks or arguments.get("goal_change")):
        raise ValueError("no weeks")
    out: dict[int, dict[str, list[dict]]] = {}
    for week in weeks:
        number = int(week["week_number"])
        if number in out:
            raise ValueError(f"week {number} given twice")
        days: dict[str, list[dict]] = {}
        for w in week.get("workouts") or []:
            if w.get("day") not in WEEKDAYS:
                raise ValueError(f"bad day {w.get('day')!r}")
            km = float(w.get("distance_km") or 0)
            if not 0 <= km <= 100:
                raise ValueError(f"bad distance {km}")
            days.setdefault(w["day"], []).append(workout(w.get("type") or "easy", km, w.get("pace_zone"), w.get("notes")))
        out[number] = days
    return out


EDIT_SYSTEM_PROMPT = """\
PLAN EDIT TASK. You change a runner's training Plan by calling the propose_plan_edit tool exactly once. \
The app checks your proposal against hard rules and refuses it if any is broken, so follow them:
- Never change a day before TODAY, nor a day that already has a run matched to it.
- Weekly availability (below) is a hard limit per weekday: number of runs, longest run, whether Quality \
workouts (tempo, interval, repetition, marathon_pace) are allowed. Break it only if the runner explicitly \
asked to break it once; then name that one day in `override`.
- A week never totals more than its Weekly volume (below). The longest run stays within the Long run limit.
- A missed workout: never make up a missed Quality workout. Spread the lost distance over the week's \
remaining Easy runs, within the limits above, or let it go.
- Never change the race, target time or race date; if that is asked, fill `goal_change` instead.
- Give every workout of each week you change, unchanged days included. Keep each week's phase.
Write the summary in the runner's language."""


def _availability_lines(availability: list[dict]) -> list[str]:
    lines = []
    for d in availability:
        if d["slots"] == 0:
            lines.append(f"- {d['day']}: rest day, no runs")
            continue
        cap = f"at most {d['maxKm']} km each" if d.get("maxKm") is not None else "no distance cap"
        quality = "Quality allowed" if d.get("qualityAllowed", True) else "no Quality workouts"
        lines.append(f"- {d['day']}: up to {d['slots']} run(s), {cap}, {quality}")
    return lines


def build_edit_messages(
    *,
    request: str,
    runner_message: str,
    goal: dict,
    plan: dict,
    days: dict[int, dict[str, list[dict]]],
    today: date,
    locked_days: set[tuple[int, str]],
    weekly_volumes: dict[int, float],
    easy_slow_sec_per_km: int | None,
) -> list[dict]:
    """Prompt for the edit model: the rules, the editable weeks, and the request."""
    start = plan["start_date"]
    current_week = max(1, (today - start).days // 7 + 1)
    lines = [
        f"TODAY: {today.strftime('%A')} {today.isoformat()} (Plan week {current_week})",
        f"GOAL: {goal['distance']} in {goal['target_time']}, race date {goal['race_date']} (fixed)",
        "WEEKLY AVAILABILITY:",
        *_availability_lines(goal["weekly_availability"]),
        "PLAN WEEKS FROM THE CURRENT ONE (earlier weeks cannot change):",
    ]
    for week in range(current_week, plan["total_weeks"] + 1):
        week_days = days.get(week, {})
        volume = weekly_volumes.get(week, round(sum(w["distanceKm"] for ws in week_days.values() for w in ws), 2))
        limit = long_run_limit_km(volume, easy_slow_sec_per_km)
        lines.append(f"Week {week}: Weekly volume {volume} km, Long run limit about {limit} km")
        for day in WEEKDAYS:
            when = start + timedelta(days=(week - 1) * 7 + WEEKDAYS.index(day))
            tags = []
            if when < today:
                tags.append("past, cannot change")
            if (week, day) in locked_days:
                tags.append("run matched, cannot change")
            runs = ", ".join(
                f"{w['type']} {w['distanceKm']} km" + (f" {w['paceZone']}" if w["paceZone"] else "")
                for w in week_days.get(day, [])
            ) or "nothing"
            tag = f" ({'; '.join(tags)})" if tags else ""
            lines.append(f"  {day} {when.isoformat()}: {runs}{tag}")
    lines += ["", f"THE RUNNER SAID: {runner_message}", f"REQUESTED CHANGE: {request}"]
    return [{"role": "system", "content": EDIT_SYSTEM_PROMPT}, {"role": "user", "content": "\n".join(lines)}]


def recent_edits_block(edits: list[dict]) -> str | None:
    """Plan chat prompt block: the latest edit proposals and what became of them."""
    if not edits:
        return None
    lines = ["RECENT PLAN EDITS (newest first; the app's decisions, relay refusals honestly)"]
    for e in edits:
        text = f"- {e['status']}: {e['request']}"
        if e.get("summary"):
            text += f" ({e['summary']})"
        if e.get("reasons"):
            text += "; refused because " + "; ".join(reason_text(r) for r in e["reasons"])
        if e.get("override"):
            text += f"; one-off availability override on week {e['override']['week']} {e['override']['day']}"
        lines.append(text)
    return "\n".join(lines)
