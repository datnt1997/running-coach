from datetime import date

from app.hr_zones import missing_for_zones, profile_zones, target_zone, zone_range_text
from app.i18n import language_instruction
from app.models.goal import GoalRequest
from app.vdot import format_pace, training_paces

SYSTEM_PROMPT = """\
You are an expert running coach and sports scientist. You design safe, \
effective, periodized training plans grounded in established endurance-training \
principles.

PERIODIZATION GUIDELINES
- base: Build an aerobic foundation. Predominantly easy Z2 running, gradually \
increasing weekly volume. Establish consistency and durability.
- build: Introduce quality work — tempo runs (Z4) and intervals (Z5) — on top of \
maintained aerobic volume. Develop lactate threshold and efficiency.
- peak: Sharpen with race-specific intensity. Workouts mirror goal pace and \
race demands; volume is high but quality is prioritized.
- taper: Reduce volume by 20-30% over the final 2 weeks while keeping some \
intensity to stay sharp. Arrive at the race fresh and rested.

PROGRESSION RULES
- No single week may increase total mileage by more than 10% versus the \
previous week. Respect this cap strictly, including the first week after a \
phase transition.
- Include recovery/easy days between hard sessions.

HEART-RATE / PACE ZONES
- Z1 (recovery): very easy, regeneration.
- Z2 (aerobic): conversational endurance pace.
- Z3 (marathon pace): comfortably hard, sustained efforts.
- Z4 (threshold): lactate threshold work.
- Z5 (VO2max): short, very hard repeats.
- The athlete's heart-rate zones in bpm are given in the athlete data, computed \
from their own maximum and resting heart rate (heart-rate-reserve method). Quote only those \
numbers. If they are unavailable, give no bpm numbers and never estimate a \
maximum heart rate or zone.

INJURY HISTORY
- Respect the athlete's injury history. For knee issues (e.g. tendinopathy), \
reduce high-impact sessions, cap downhill/steep work, prefer softer surfaces, \
and consider low-impact cross-training to maintain fitness while protecting the \
joint. Adjust intensity and volume conservatively when injury risk is present.

VDOT GUIDANCE
- The athlete's VDOT (Daniels) is their current fitness. Do not ask for or \
assume a level; calibrate everything from VDOT and the weekly availability.
- Easy and long runs use E pace (Z1-Z2). Put the target pace for each run in \
its notes, taken from the training paces given in the athlete data. Never \
invent paces. Do not prescribe repetition (R) work.
- Per-session limits, scaled to that week's total distance:
  - Long run (L): at most 30% of the week if the week is under 64 km; \
otherwise under 25% of the week or 150 minutes, whichever comes first.
  - Threshold (T): at most 10% of the week.
  - Interval (I): at most 8% of the week and never more than 10 km in a \
session, and no more than two I sessions in any week.
- Hold weekly distance steady for about 4 weeks before raising it again, and \
never raise it by more than 10% from one week to the next.
- The target time must be consistent with the VDOT. If it is much faster than \
the VDOT predicts for that distance, still build the best safe plan, but say so \
plainly in the plan summary and do not raise volume or intensity beyond the \
limits above to chase it.

STARTING POINT
- The athlete's current weekly distance and longest recent run are where the \
plan begins. Week 1 total distance must not be more than 10% above the current \
weekly distance, and its long run not more than 10% above the longest recent \
run. If the athlete runs 0 km a week, start with short easy runs only.
- Reach the weekly volume the goal needs by the progression rules, not by a \
jump in week 1.
- If the athlete's current load is low for the race distance, say so plainly \
in the plan summary instead of hiding it.

OUTPUT
- Call the generate_training_plan tool exactly once with the complete plan.
- total_weeks must equal the number of weeks you produce, and the phase \
breakdown counts must sum to total_weeks.
- Each week must contain one workout entry per workout you prescribe, honoring \
the athlete's weekly availability: the workouts per day, distance cap and Quality \
workout permission given for each weekday. A day may hold two workouts when its \
availability allows two workouts; rest days fill the remaining days.
- Keep day, type, phase and pace_zone values in English exactly as specified by \
the tool schema.
- Every workout must have a day, type, distance_km (0 for rest), and pace_zone.
"""


def _weeks_until_race(race_date: date, today: date) -> int:
    return max((race_date - today).days // 7, 0)


def _availability_lines(goal: GoalRequest) -> str:
    lines = []
    for d in goal.weekly_availability:
        if d.slots == 0:
            lines.append(f"- {d.day}: rest")
            continue
        workouts = f"{d.slots} workout" + ("s" if d.slots > 1 else "")
        cap = f"max {d.max_km:g} km each" if d.max_km is not None else "no distance cap"
        quality = "Quality workouts allowed" if d.quality_allowed else "no Quality workouts"
        lines.append(f"- {d.day}: up to {workouts}, {cap}, {quality}")
    return "\n".join(lines)


def zones_line(profile: dict | None) -> str:
    """The prompt line for the runner's heart-rate zones, or why there are none."""
    zones = profile_zones(profile)
    if zones is not None:
        return f"- Heart-rate zones: {zone_range_text(zones)}\n"
    missing = missing_for_zones(profile)
    why = (
        f"the profile has no {', '.join(missing)}" if missing
        else "the profile's heart rates are inconsistent"
    )
    return (
        f"- Heart-rate zones: unavailable ({why}). "
        "Do not state or estimate heart-rate numbers.\n"
    )


def build_user_prompt(
    goal: GoalRequest, today: date | None = None, profile: dict | None = None
) -> str:
    if today is None:
        today = date.today()
    weeks_until_race = _weeks_until_race(goal.race_date, today)
    distance_label = goal.distance.replace("_", " ").title()
    injury = goal.injury_history or "none reported"
    paces = training_paces(goal.vdot)
    vdot_line = (
        f"- VDOT (Daniels): {goal.vdot:g}. Use it to calibrate weekly load\n"
        "- Training paces per km: "
        f"easy {format_pace(paces['easy_fast'])}-{format_pace(paces['easy_slow'])}, "
        f"marathon {format_pace(paces['marathon'])}, "
        f"threshold {format_pace(paces['threshold'])}, "
        f"interval {format_pace(paces['interval'])}\n"
        f"- Current running: {goal.weekly_km:g} km per week, "
        f"longest recent run {goal.longest_run_km:g} km\n"
    )

    return (
        "Design a periodized training plan for the following athlete and goal:\n"
        f"- Distance: {distance_label}\n"
        f"- Target finish time: {goal.target_time}\n"
        f"- Race date: {goal.race_date.isoformat()}\n"
        f"- Weeks until race: {weeks_until_race}\n"
        f"{vdot_line}"
        f"{zones_line(profile)}"
        "- Weekly availability (hard limits, per weekday):\n"
        f"{_availability_lines(goal)}\n"
        f"- Injury history: {injury}\n\n"
        "Build the plan to span the full lead-up to the race. Apply the "
        "periodization, progression, and zone guidelines from your instructions. "
        "Never break the weekly availability limits, and respect injury history."
    )


def build_messages(
    goal: GoalRequest, today: date | None = None, profile: dict | None = None
) -> list[dict]:
    return [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n{language_instruction()}"},
        {"role": "user", "content": build_user_prompt(goal, today=today, profile=profile)},
    ]


# ---------------------------------------------------------------------------
# Activity analysis prompts
# ---------------------------------------------------------------------------

_ANALYSIS_SYSTEM_PROMPT = """\
You are an expert running coach analyzing a completed run against its planned workout.

Assess adherence across three dimensions:
- pace_adherence: was the actual pace within the prescribed zone? ('on_target', 'too_fast', 'too_slow')
- hr_adherence: was average HR consistent with the prescribed effort zone? ('on_target', 'above_prescribed', 'below_prescribed', or 'unavailable' when no comparison is possible)
- load_adherence: was total load (volume × intensity) appropriate? ('on_target', 'overreaching', 'underloaded')

Heart-rate zones come from the athlete's own profile and are given below with the \
target zone for this workout. Compare the average heart rate with that target zone \
only. If the target zone or the average heart rate is unavailable, never guess a \
maximum heart rate or zone: say in the rationale that the heart-rate comparison is \
unavailable, and set hr_adherence to 'unavailable'.

Call the analyze_activity tool with your assessment and a brief rationale.
"""


def _target_hr_text(workout_type: str, profile: dict | None) -> str:
    zones = profile_zones(profile)
    if zones is None:
        return "Target heart-rate zone: unavailable (no usable heart-rate profile)"
    target = target_zone(workout_type, zones)
    if target is None:
        return "Target heart-rate zone: none for this workout type"
    lo, hi = target["minZone"], target["maxZone"]
    label = f"Z{lo}" if lo == hi else f"Z{lo}-Z{hi}"
    span = f"up to {target['max']}" if target["min"] is None else f"{target['min']}-{target['max']}"
    return f"Target heart-rate zone: {label} ({span} bpm)"


def build_activity_analysis_messages(
    planned,
    actual,
    profile: dict | None = None,
) -> list[dict]:
    from datetime import timedelta

    pace_str = "unknown"
    if actual.distance > 0:
        pace_secs = actual.moving_time / (actual.distance / 1000)
        t = timedelta(seconds=int(pace_secs))
        mins, secs = divmod(int(t.total_seconds()), 60)
        pace_str = f"{mins}:{secs:02d} /km"

    user_content = (
        f"Planned workout:\n"
        f"- Type: {planned.workout_type}\n"
        f"- Distance: {planned.distance_km} km\n"
        f"- Target zone: {planned.pace_zone}\n"
        f"- {_target_hr_text(planned.workout_type, profile)}\n\n"
        f"Actual activity:\n"
        f"- Distance: {actual.distance / 1000:.2f} km\n"
        f"- Moving time: {timedelta(seconds=actual.moving_time)}\n"
        f"- Avg pace: {pace_str}\n"
        f"- Avg heart rate: {actual.average_heartrate if actual.average_heartrate else 'not recorded'} bpm\n"
    )

    return [
        {"role": "system", "content": f"{_ANALYSIS_SYSTEM_PROMPT}\n{language_instruction()}"},
        {"role": "user", "content": user_content},
    ]


def build_weekly_summary_messages(week_number: int, analyses: list[dict]) -> list[dict]:
    if not analyses:
        body = f"Week {week_number} had no recorded activities. State that no data is available."
    else:
        rows = []
        for a in analyses:
            rows.append(
                f"- {a.get('day_of_week', '?')} {a.get('workout_type', '?')}: "
                f"planned {a.get('planned_distance_km', '?')} km ({a.get('pace_zone', '?')}), "
                f"actual {float(a['distance_km']):.1f} km | "
                f"pace: {a.get('pace_adherence', 'n/a')}, "
                f"HR: {a.get('hr_adherence') or 'n/a'}, "
                f"load: {a.get('load_adherence', 'n/a')}"
            )
        body = (
            f"Summarize week {week_number} training adherence in 2-3 sentences.\n\n"
            + "\n".join(rows)
        )

    return [
        {
            "role": "system",
            "content": "You are a running coach writing a concise weekly performance summary.\n"
            + language_instruction(),
        },
        {"role": "user", "content": body},
    ]
