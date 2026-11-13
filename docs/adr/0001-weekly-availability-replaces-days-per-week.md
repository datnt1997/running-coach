---
status: accepted
---

# Weekly availability replaces days per week

A Goal used to carry one number, `days_per_week` (3 to 7), which reached the model only as a prompt line and was never checked. Runners have per-weekday limits that a count cannot express: two workouts on Wednesday, no more than 3 km on weekdays, hard workouts only on Saturday and Sunday. We replace it with **Weekly availability**: for each weekday, how many workouts (0, 1 or 2), the longest distance per workout, and whether Quality workouts are allowed. The limits are hard: Python checks every generated Plan against them (the model proposes, Python verifies, as with VDOT), and if the target looks out of reach inside them the coach says so instead of breaking a limit. `days_per_week` becomes derived: the number of Training days.

## Considered options

- **Keep days per week.** Cheapest, but it cannot say which day, how far or how hard, and nothing enforces it.
- **Add a workouts-per-week count beside days.** Controls total load, not placement or distance, and most runners do not know what number to pick.
- **Count runs per week instead of days.** Changes the meaning of stored values and still leaves placement to the model.
- **Soft preferences in free text** (for example `injury_history`). The model may ignore them and Python cannot check them.

## Consequences

- Needs a migration: existing Goals become that many one-workout days with no distance cap and Quality workouts allowed.
- The Goal form changes from a 3 to 7 picker to a seven-day grid; presets keep it quick.
- Plan generation needs a post-generation check, and Quality workouts need a type the code can recognise (today `type` is free text).
- The runner can change availability through Plan chat for the current week onward without starting a new Goal. Changing the race, target time or date still does.
