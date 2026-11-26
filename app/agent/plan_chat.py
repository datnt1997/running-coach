"""Prompt for the Plan chat: the Gem's tone and method, then the Runner's data re-read each turn.

The fixed system prompt holds tone and method only. Personal numbers (heart
rates, zones) and the Plan are passed in per turn from the database.
"""

import re
from datetime import date, timedelta

from app.hr_zones import missing_for_zones, profile_zones, target_zone, zone_for_bpm, zone_range_text
from app.i18n import language_instruction

HISTORY_LIMIT = 20  # messages sent verbatim each turn
SUMMARY_BATCH = 10  # older messages wait until this many can be folded into the Rolling summary at once
MAX_FOLD_BATCH = 20  # most messages sent to one summary call, oldest first
MAX_FOLDS_PER_TURN = 3  # summary calls in one turn, so a backlog catches up in bounded steps
MAX_SUMMARY_CHARS = 4000
MAX_VERBATIM = HISTORY_LIMIT + SUMMARY_BATCH  # most messages ever sent verbatim in one prompt

SUMMARY_SYSTEM_PROMPT = """\
ROLLING SUMMARY TASK. You compress a running coach's conversation with a runner. \
You get the previous summary (may be empty) and the older messages not yet in it. \
Write one updated summary that keeps everything that should shape future coaching: injuries, pain, \
health, schedule limits, preferences, decisions, agreed changes, race news, how training has felt. \
Drop greetings and small talk. Never invent anything. Keep the runner's language. \
Plain text, at most 300 words; reply with the summary only."""


def build_summary_messages(previous: str | None, messages: list[dict]) -> list[dict]:
    """Prompt asking the model to fold `messages` into the previous Rolling summary."""
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    user = f"PREVIOUS SUMMARY:\n{previous or '(none)'}\n\nOLDER MESSAGES:\n{transcript}"
    return [{"role": "system", "content": SUMMARY_SYSTEM_PROMPT}, {"role": "user", "content": user}]

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
- The Goal's race, target time and date can only change by starting a new Goal; say so if asked.

CHANGING THE PLAN
- You never change the Plan yourself. When the runner asks for a change to the Plan (move, shorten, \
swap or drop a workout, handle a missed workout, change a week), or agrees to one you suggested, end your \
reply with, on a final line of its own, the marker [[EDIT: <the requested change in one sentence, with week \
numbers, days and distances>]]. Ask for at most one change per reply.
- The app then proposes the exact change, checks it against Weekly availability, the Long run limit, the \
Weekly volume and past weeks, and shows it to the runner below your reply; it is applied only if the runner \
confirms. So never say the change is made; say you are proposing it.
- A missed Quality workout is never made up; its distance may go to the week's remaining Easy runs.

RETURNING AFTER TIME OFF (Daniels Table 15.2)
- Count the days the runner did not run (rest, illness, travel) from what they tell you and RECENT RUNS.
- Up to 5 days off: for as many days as were missed, run Easy (E, Z2) only, no longer than the runs \
before the break; then train normally. Any Quality workout falling in those days becomes an Easy run \
of at most the same distance; it is not made up later. Pace and VDOT stay the same.
- 6 days or more off: the first half of the return E at about 50% of the earlier weekly volume, the second \
half at about 75%; say the VDOT is lower (Table 15.1) and suggest updating it before Quality work resumes.
- After illness, the medical rule below still comes first: no training until symptoms are gone.
- When the next days of the Plan break this rule, do not say the Plan already fits: name the days, \
propose the change with an [[EDIT]] marker, and still ask for one change per reply (start with the nearest day).
- A Weekly availability limit may be broken only once and only when the runner explicitly asks for it; \
then say plainly which limit is being overridden.
- RECENT PLAN EDITS (when present) says what the app decided. Relay a refusal and its reason honestly \
and offer an alternative within the limits.

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


def _summary_block(summary: str) -> str:
    return f"EARLIER CONVERSATION (summary of older messages, kept for context)\n{summary}"


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


def _zone_label(target: dict) -> str:
    z = f"Z{target['minZone']}" if target["minZone"] == target["maxZone"] else f"Z{target['minZone']}-Z{target['maxZone']}"
    return f"{z} ({target['min']}-{target['max']} bpm)"


def _plan_workouts_on(plan: dict | None, day: date) -> list[dict]:
    if not plan:
        return []
    return [w for w in plan["workouts"] if w["workout_type"] != "rest" and _workout_date(plan, w) == day]


def _activities_block(activities: list[dict], zones: list[dict] | None, plan: dict | None = None) -> str:
    header = (
        "RECENT ACTIVITIES (Strava, newest first; each with its Match and Adherence; re-read each turn)\n"
        "Analyse any run the runner asks about, matched or not: an unmatched run still has its distance, pace and "
        "heart rate, so compare it with the Plan's workout for that date and the heart-rate zones. "
        "Never say you cannot access the tracklog when it is listed here."
    )
    if not activities:
        return f"{header}\n- The runner has no Activities logged yet."
    lines = [header]
    for a in activities:
        km = float(a["distance_km"])
        if a.get("workout_type"):
            if a["planned_distance_km"] is not None:
                match = f"matched to {a['workout_type']} {float(a['planned_distance_km']):.1f} km" + (
                    " (mismatched distance)" if a["mismatch"] else ""
                )
            else:
                match = f"matched to {a['workout_type']}"
            target = target_zone(a["workout_type"], zones)
            goal = f"target {_zone_label(target)}" if target else "target zone unavailable"
            adherence = (
                f"Adherence: pace {a['pace_adherence'] or 'unavailable'}, "
                f"heart rate {a['hr_adherence'] or 'unavailable'}, load {a['load_adherence'] or 'unavailable'}"
            )
        else:
            match, goal, adherence = "unmatched (no stored Match)", None, None
            planned = _plan_workouts_on(plan, a["activity_date"])
            if planned:
                w = planned[0]
                target = target_zone(w["workout_type"], zones)
                km_plan = f" {float(w['distance_km']):.1f} km" if w.get("distance_km") is not None else ""
                goal = f"Plan that day: {w['workout_type']}{km_plan}" + (f", target {_zone_label(target)}" if target else "")
            else:
                goal = "no Planned workout on that date"
            if a.get("avg_hr_bpm") and zone_for_bpm(a["avg_hr_bpm"], zones):
                goal += f"; average heart rate falls in {zone_for_bpm(a['avg_hr_bpm'], zones)}"
        hr = f"average heart rate {round(a['avg_hr_bpm'])} bpm" if a.get("avg_hr_bpm") else "average heart rate unavailable"
        parts = [f"{a['activity_date'].isoformat()}: {km:.1f} km, {match}"]
        if a.get("pace_sec_per_km"):
            parts.append(f"pace {a['pace_sec_per_km'] // 60}:{a['pace_sec_per_km'] % 60:02d}/km")
        parts.append(hr)
        if goal:
            parts.append(goal)
        if adherence:
            parts.append(adherence)
        lines.append("- " + "; ".join(parts))
    return "\n".join(lines)


TAPER_WINDOW_DAYS = 21  # taper guidance appears this close to the race


def _race_block(goal: dict | None, today: date) -> str | None:
    if goal is None:
        return None
    race = goal["race_date"]
    days = (race - today).days
    if days < 0:
        return f"RACE COUNTDOWN\n- The race on {race.isoformat()} has passed."
    when = "race day is today" if days == 0 else f"{days} days to the race"
    lines = ["RACE COUNTDOWN", f"- {when} ({race.isoformat()})."]
    if days <= TAPER_WINDOW_DAYS:
        lines += [
            "TAPER AND RACE-WEEK GUIDANCE",
            "- The race date is fixed; never move it or suggest postponing. Taper inside it.",
            "- Ground advice in the imported Plan above (its remaining workouts and distances up to the race) "
            "and in the RECENT ACTIVITIES; do not invent sessions or numbers.",
            "- Taper principle: keep intensity, cut volume progressively over the final weeks, keep the "
            "last days easy, no new things in race week.",
            "- If the runner reports fatigue or pain, change the suggestion: cut volume and intensity more, "
            "swap quality for easy or rest, and apply the PAIN AND MEDICAL RULE. Never add work to compensate.",
        ]
    return "\n".join(lines)


def build_messages(
    profile: dict | None,
    goal: dict | None,
    plan: dict | None,
    history: list[dict],
    today: date | None = None,
    facts: list[dict] | None = None,
    declined: list[str] | None = None,
    summary: str | None = None,
    activities: list[dict] | None = None,
    edits: str | None = None,
) -> list[dict]:
    """System prompt + this turn's profile, Plan, Activities, race countdown and Rolling summary + the last messages verbatim."""
    today = today or date.today()
    blocks = [_today_block(today), _profile_block(profile), _facts_block(facts or [])]
    if declined:
        blocks.append(_declined_block(declined))
    zones = profile_zones(profile)
    blocks.append(_plan_block(goal, plan, zones))
    blocks.append(_activities_block(activities or [], zones, plan))
    race = _race_block(goal, today)
    if race:
        blocks.append(race)
    if edits:
        blocks.append(edits)
    if summary:
        blocks.append(_summary_block(summary))
    context = "\n\n".join(blocks)
    system = f"{SYSTEM_PROMPT}\n{language_instruction()}\n\n{context}"
    # The window can start mid-exchange; providers require the first message to be the runner's.
    start = next((i for i, m in enumerate(history) if m["role"] == "user"), len(history))
    return [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m["content"]} for m in history[start:]
    ]
