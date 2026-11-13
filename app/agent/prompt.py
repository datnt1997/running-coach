from datetime import date

from app.i18n import language_instruction
from app.models.goal import GoalRequest

SYSTEM_PROMPT = """\
You are an expert running coach and sports scientist. You design safe, \
effective, periodized training plans grounded in established endurance-training \
principles.

PERIODIZATION GUIDELINES
- base: Build an aerobic foundation. Predominantly easy Z2 running, gradually \
increasing weekly volume. Establish consistency and durability.
- build: Introduce quality work — tempo runs (Z3) and intervals (Z4) — on top of \
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
- Z1 (recovery): < 65% of HRmax — very easy, regeneration.
- Z2 (aerobic): 65-75% of HRmax — conversational endurance pace.
- Z3 (tempo): 75-85% of HRmax — comfortably hard, sustained efforts.
- Z4 (threshold): 85-92% of HRmax — lactate threshold intervals.
- Z5 (VO2max): 92-100% of HRmax — short, very hard repeats.

INJURY HISTORY
- Respect the athlete's injury history. For knee issues (e.g. tendinopathy), \
reduce high-impact sessions, cap downhill/steep work, prefer softer surfaces, \
and consider low-impact cross-training to maintain fitness while protecting the \
joint. Adjust intensity and volume conservatively when injury risk is present.

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


def build_user_prompt(goal: GoalRequest, today: date | None = None) -> str:
    if today is None:
        today = date.today()
    weeks_until_race = _weeks_until_race(goal.race_date, today)
    distance_label = goal.distance.replace("_", " ").title()
    injury = goal.injury_history or "none reported"
    vdot_line = (
        f"- VDOT (Daniels): {goal.vdot:g}. Use it to calibrate training paces "
        "and weekly load\n"
        if goal.vdot is not None
        else ""
    )

    return (
        "Design a periodized training plan for the following athlete and goal:\n"
        f"- Distance: {distance_label}\n"
        f"- Target finish time: {goal.target_time}\n"
        f"- Race date: {goal.race_date.isoformat()}\n"
        f"- Weeks until race: {weeks_until_race}\n"
        f"- Current fitness level: {goal.fitness_level}\n"
        f"{vdot_line}"
        "- Weekly availability (hard limits, per weekday):\n"
        f"{_availability_lines(goal)}\n"
        f"- Injury history: {injury}\n\n"
        "Build the plan to span the full lead-up to the race. Apply the "
        "periodization, progression, and zone guidelines from your instructions. "
        "Never break the weekly availability limits, and respect injury history."
    )


def build_messages(goal: GoalRequest, today: date | None = None) -> list[dict]:
    return [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n{language_instruction()}"},
        {"role": "user", "content": build_user_prompt(goal, today=today)},
    ]


# ---------------------------------------------------------------------------
# Activity analysis prompts
# ---------------------------------------------------------------------------

_ANALYSIS_SYSTEM_PROMPT = """\
You are an expert running coach analyzing a completed run against its planned workout.

Assess adherence across three dimensions:
- pace_adherence: was the actual pace within the prescribed zone? ('on_target', 'too_fast', 'too_slow')
- hr_adherence: was average HR consistent with the prescribed effort zone? ('on_target', 'above_prescribed', 'below_prescribed')
- load_adherence: was total load (volume × intensity) appropriate? ('on_target', 'overreaching', 'underloaded')

Zone reference (using default HRmax 180 bpm when actual HRmax unknown):
Z1 <65% · Z2 65-75% · Z3 75-85% · Z4 85-92% · Z5 92-100%

Call the analyze_activity tool with your assessment and a brief rationale.
"""


def build_activity_analysis_messages(
    planned,
    actual,
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
        f"- Target zone: {planned.pace_zone}\n\n"
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
                f"HR: {a.get('hr_adherence', 'n/a')}, "
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
