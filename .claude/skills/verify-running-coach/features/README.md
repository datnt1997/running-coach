# Running Coach verification map

Maintained source for verifying user-facing behavior. Read this, then the matching feature file.

## Baseline preconditions

- `scripts/launch.sh` reported ready and `scripts/doctor.sh` exits 0. App at `http://127.0.0.1:8010/app`.
- Database starts empty (no goals). Features that need a goal create one through `new-goal.md` first.
- UI is Vietnamese. Dates: race date must be at least 70 days from today (use a date ~4 months out).
- Never drive an instance this run did not start.

## Driving conventions

- Prefer accessible names and placeholders (`1:55:00`, `52:00`) over positions. Re-run `read_page` (interactive) after each state change; refs change.
- Wait for the plan: after submit the page shows a spinner until `plan_status` is `ready`; with the fake AI that takes about a second.
- Delete uses a native confirm dialog; see SKILL.md.

## Proof and skip reporting

- Save a screenshot and a `psql` second view per feature under `$EVIDENCE/<feature>/`.
- Report unreachable paths with the attempted step and unmet precondition.

## Feature entry contract

Each file: H1, one paragraph, then exactly four H2s: Sub-features, How to get to it (user POV), Driving it with Claude in Chrome + psql, Gotchas.

## Features

- [New goal and plan](./new-goal.md): form, manual VDOT/race-time entry, fitness chat, plan generation. (Proven end to end.)
- [Plan view](./plan-view.md): phases, weeks, workout tables.
- [This week dashboard](./dashboard.md): current-week workouts.
- [Goal history](./history.md): list, view, delete goals.
- [Strava connect page](./strava-status.md): connected/not-connected status at `/`.
