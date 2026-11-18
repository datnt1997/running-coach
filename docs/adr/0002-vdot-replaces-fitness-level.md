---
status: accepted
---

# VDOT replaces the fitness level

A Goal used to carry `fitness_level` (beginner, intermediate or advanced) next to an optional `vdot`. The label was our own bucket derived from VDOT (below 35, below 50, else), shown to the plan generator and never to the runner. Once the fitness chat and manual entry both produced VDOT, the label added no information the model did not already have, and it kept a second name in the code for one idea. We remove it: **VDOT is the only fitness input**. `vdot` is required on a Goal, the plan prompt sends the VDOT and nothing else about fitness, and `planner_label()`, `fitnessLevel` in the API and the `fitness_level` column are gone.

## Considered options

- **Rename the label to `planner_label`.** Makes the code match the old glossary term, but keeps a derived field with a migration and an API change for no behaviour gain.
- **Keep the label and document it.** Cheapest, but the mismatch with VDOT stays.
- **VDOT only (chosen).** One input, one name; the model gets a number it can calibrate paces and load from.

## Consequences

- Migration `007_vdot_replaces_fitness_level.sql` deletes Goals saved without a VDOT (with their Plans, workouts and summaries), makes `vdot` NOT NULL and drops `fitness_level`. This was safe because the only data was the owner's.
- `POST /goal` no longer accepts a fitness level (an old `fitnessLevel` field is ignored) and rejects a request without `vdot`. `GET /goals` returns `vdot` instead of `fitnessLevel`. `POST /fitness-chat` no longer returns `fitnessLevel`.
- The Goal form cannot be submitted until the runner has an assessment (chat, race time or VDOT).
- The plan prompt is not tested against the real model with a bare VDOT; check a generated Plan when the prompt next changes.
- Older files under `specs/` still describe `fitness_level`; each carries a note pointing here.
