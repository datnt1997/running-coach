# Running Coach

A personal AI running coach: a runner sets a race goal, receives a training plan, and the plan adapts week by week from their Strava activity.

## Language

### Goal

**Goal**:
The runner's race target: distance, target finish time, race date, weekly availability and injury history. A runner has exactly one active Goal at a time.
_Avoid_: Target, objective

**Weekly availability**:
The runner's hard limits on when and how much they can train, set per weekday: how many workouts (0, 1 or 2), the longest distance per workout, and whether Quality workouts are allowed. A Plan never breaks it; if the target looks out of reach within it, the coach says so.
_Avoid_: Schedule, preferences, days per week

**Training day**:
A weekday on which the weekly availability allows at least one workout. A day with two workouts is still one Training day.
_Avoid_: Run day, session day

**Quality workout**:
A demanding Planned workout: tempo, intervals, repetitions or marathon-pace running, which Daniels calls a Q session. A long run counts only when it includes such faster running. Weekly availability decides which weekdays may hold one.
_Avoid_: Hard workout, key workout, quality session

**Easy run**:
A Planned workout at conversational effort, used for recovery and to build weekly volume. A day may hold one or two.
_Avoid_: Recovery run, filler

**Active Goal**:
The Goal currently being trained for. Creating a new Goal replaces it: the old Goal and its Plan are kept as history but no longer drive Strava matching or the dashboard.
_Avoid_: Current goal, archived (for the replaced one, say "inactive")

**Plan**:
The week-by-week training schedule generated for a Goal. A Goal has exactly one Plan, which the runner can customize afterwards by chatting with the coach.
_Avoid_: Program, schedule, training plan (in prose; the table name `training_plans` stays)

### Training

**Planned workout**:
One prescribed run in a Plan, on a given day of a given week. A day can hold more than one Planned workout.
_Avoid_: Session, workout session, training

**Missed workout**:
A Planned workout whose day has passed with no Activity matched to it. The coach never makes up a missed Quality workout; it spreads the lost distance over the week's remaining Easy runs, within Weekly availability and the Long run limit, and the runner confirms the change.
_Avoid_: Skipped workout, failed workout

**Long run**:
The week's longest Planned workout. It stays within 25% of Weekly volume (30% when the week is under 64 km) or 150 minutes, whichever comes first.
_Avoid_: LSD, endurance run

**Weekly volume**:
The target total distance of one Plan week, set when the Plan is generated and shown to the runner. The coach keeps close to it when it adjusts the week.
_Avoid_: Weekly mileage, weekly load, weekly total

**Activity**:
A run the runner actually recorded on Strava.
_Avoid_: Run, workout (reserved for the prescribed one)

**Match**:
The pairing of an Activity with the Planned workout it fulfils: same day, and where the day holds several Planned workouts, the one whose distance is nearest to the Activity's.
_Avoid_: Link, assignment

**Mismatched**:
A Match whose Activity distance is more than 30% away from its Planned workout's. A Planned workout of 0 km (rest) never mismatches.
_Avoid_: Off-plan

**Unmatched**:
An Activity with no Planned workout left on its day. Not a mismatch.
_Avoid_: Extra run, unplanned run

**Phase**:
One of Daniels' four training stages, each a block of consecutive Plan weeks: I foundation, II repetition work, III interval work, IV final quality work before the race.
_Avoid_: Stage, block, cycle, base/build/peak/taper

**Adherence**:
How closely a matched Activity followed its Planned workout, judged on pace, heart rate and load. Applies only to matched Activities.
_Avoid_: Compliance, score

**Weekly summary**:
A plain-text recap of one Plan week, one per Plan and week.
_Avoid_: Weekly report, digest

### Coach conversations

**Fitness chat**:
The conversation before a Goal exists, in which the coach collects a race result and training signals to compute the runner's VDOT.
_Avoid_: Level chat, assessment chat, chat

**Plan chat**:
The conversation after a Plan exists, in which the runner asks the coach to change the Plan's current and future weeks. It never changes the Goal's race, time or date; those start a new Goal.
_Avoid_: Coach chat, chat

### Fitness assessment

**VDOT**:
The runner's single fitness number, computed from a recent race result (Daniels-Gilbert). It is shown to the runner with one decimal.
_Avoid_: Fitness score, rating

**Predicted times**:
The race times implied by a runner's VDOT. Together with VDOT, these are the only fitness outputs the runner sees.
_Avoid_: Estimates, projections

**Planner label**:
An internal beginner/intermediate/advanced bucket derived from VDOT that steers plan generation. It is never shown to the runner.
_Avoid_: Fitness level, level, rank, tier
