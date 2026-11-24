"""Prompt for the Plan chat: the Gem's tone and method, then the Runner's data re-read each turn.

The fixed system prompt holds tone and method only. Personal numbers (heart
rates, zones) and the Plan are passed in per turn from the database.
"""

import re
from datetime import date, timedelta

from app.hr_zones import missing_for_zones, profile_zones, target_zone, zone_range_text
from app.i18n import language_instruction

HISTORY_LIMIT = 20  # messages sent verbatim each turn

SYSTEM_PROMPT = """\
You are the runner's personal running coach, continuing one long conversation with them. \
Your method is Daniels' Running Formula; paces, VDOT and heart-rate zones are computed by \
the app, so use only the numbers given to you below and never invent or estimate one. \
If you do not know something, say so plainly.

TONE
- Analytical and direct, like a friend who coaches. No filler emotion, no flattery, no long preambles.
- Keep replies short and useful.

METHOD
- For every session you prescribe, state the target heart-rate zone and the physiological purpose \
(aerobic or anaerobic, and why the session exists).
- Show training plans and weekly schedules as tables.
- You may explain and advise, but you cannot change the Plan in this conversation; \
the Goal's race, target time and date can only change by starting a new Goal.

REMEMBERING FACTS
- When the runner tells you something lasting about themselves (an old injury, a schedule limit, \
a preference, a health condition) that you do not already know, propose remembering it. End your reply \
with a question in the form "I'll remember: <fact>. OK?" (in the runner's language) and, on a final line of \
its own, the machine-readable marker [[REMEMBER: <fact>]] with the same short fact. Propose at most one \
fact per reply. The fact is saved only if the runner confirms, so never say it is already saved.
- Do not propose anything listed under WHAT YOU REMEMBER, nor passing details (today's tiredness, one workout).

PAIN AND MEDICAL RULE
- Never diagnose an injury or illness.
- For sharp pain, chest symptoms (pain, tightness, palpitations) or dizziness: tell the runner to \
stop running, rest and see a doctor. Do not prescribe training until they have been seen.
- For milder aches, suggest easing off and see a doctor if it persists; never push a hard workout \
on top of reported pain.
"""


def _profile_block(profile: dict | None) -> str:
    profile = profile or {}
    lines = ["RUNNER PROFILE (from the profile page; the only source of personal numbers)"]
    lines.append(f"- Maximum heart rate: {profile.get('max_hr') or 'not entered yet (chưa nhập)'}")
    lines.append(f"- Resting heart rate: {profile.get('resting_hr') or 'not entered yet (chưa nhập)'}")
    if profile.get("lactate_threshold_hr"):
        lines.append(f"- Lactate-threshold heart rate: {profile['lactate_threshold_hr']}")
    zones = profile_zones(profile)
    if zones:
        lines.append(f"- Heart-rate zones: {zone_range_text(zones)}")
    else:
        lines.append(
            "- Heart-rate zones: unavailable until max and resting heart rate are entered; "
            "tell the runner to fill in their profile and do not estimate zones."
        )
    return "\n".join(lines)


def _facts_block(facts: list[dict]) -> str:
    lines = ["WHAT YOU REMEMBER ABOUT THE RUNNER (confirmed facts; re-read each turn)"]
    lines += [f"- {f['text']}" for f in facts] or ["- Nothing yet."]
    return "\n".join(lines)


def _declined_block(declined: list[str]) -> str:
    lines = ["RECENTLY DECLINED (the runner said no; do not propose these again)"]
    return "\n".join(lines + [f"- {t}" for t in declined])


_MARKER = re.compile(r"\[\[REMEMBER:\s*(.*?)\s*\]\]", re.DOTALL)
_UNCLOSED_MARKER = re.compile(r"\[\[REMEMBER:.*", re.DOTALL)
MAX_FACT_CHARS = 300


def split_proposal(reply: str) -> tuple[str, str | None]:
    """The reply without its [[REMEMBER: ...]] marker, and the proposed fact if there is a usable one."""
    found = _MARKER.findall(reply)
    visible = _UNCLOSED_MARKER.sub("", _MARKER.sub("", reply)).strip()
    fact = " ".join(found[0].split()) if found else ""
    return visible, (fact[:MAX_FACT_CHARS] or None)


_DAY_OFFSET = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def _today_block(today: date) -> str:
    return f"TODAY\n- {today.strftime('%A')} {today.isoformat()}. Use this date for \"today\", \"tomorrow\" and \"this week\"; never ask the runner what day it is."


def _workout_date(plan: dict, w: dict) -> date | None:
    start = plan.get("start_date")
    if not isinstance(start, date):
        return None
    return start + timedelta(days=(w["week_number"] - 1) * 7 + _DAY_OFFSET.get(w["day_of_week"], 0))


def _plan_block(goal: dict | None, plan: dict | None, zones: list[dict] | None) -> str:
    if plan is None or goal is None:
        return "PLAN\n- The runner has no Plan yet."
    lines = [
        "PLAN (current; re-read each turn)",
        f"- Goal: {goal['distance']} in {goal['target_time']}, race date {goal['race_date']}",
        f"- Plan starts {plan['start_date']}, {plan['total_weeks']} weeks. {plan['summary']}",
    ]
    week = None
    for w in plan["workouts"]:
        if w["week_number"] != week:
            week = w["week_number"]
            lines.append(f"Week {week} ({w['phase']}):")
        target = target_zone(w["workout_type"], zones)
        if target:
            label = f"Z{target['minZone']}" if target["minZone"] == target["maxZone"] else (
                f"Z{target['minZone']}-Z{target['maxZone']}"
            )
            zone = f"{label} ({target['min']}-{target['max']} bpm)"
        else:
            zone = w["pace_zone"] or "no HR target"
        km = float(w["distance_km"]) if w["distance_km"] is not None else 0.0
        note = f" - {w['notes']}" if w.get("notes") else ""
        d = _workout_date(plan, w)
        when = f"{w['day_of_week']} {d.isoformat()}" if d else w["day_of_week"]
        lines.append(f"  {when}: {w['workout_type']} {km:.1f} km, {zone}{note}")
    return "\n".join(lines)


def build_messages(
    profile: dict | None,
    goal: dict | None,
    plan: dict | None,
    history: list[dict],
    today: date | None = None,
    facts: list[dict] | None = None,
    declined: list[str] | None = None,
) -> list[dict]:
    """System prompt + this turn's profile and Plan + the last messages verbatim."""
    blocks = [_today_block(today or date.today()), _profile_block(profile), _facts_block(facts or [])]
    if declined:
        blocks.append(_declined_block(declined))
    blocks.append(_plan_block(goal, plan, profile_zones(profile)))
    context = "\n\n".join(blocks)
    system = f"{SYSTEM_PROMPT}\n{language_instruction()}\n\n{context}"
    # The window can start mid-exchange; providers require the first message to be the runner's.
    start = next((i for i, m in enumerate(history) if m["role"] == "user"), len(history))
    return [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m["content"]} for m in history[start:]
    ]
