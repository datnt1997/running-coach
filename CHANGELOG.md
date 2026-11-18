# Changelog

All notable changes to this project are recorded here, grouped by date (newest first).

## 2026-11-18

- VDOT is now the only fitness input (issue #17, ADR 0002). Removed `fitness_level` and the beginner/intermediate/advanced Planner label: `POST /goal` no longer takes `fitnessLevel` and requires `vdot`; `GET /goals` and `POST /fitness-chat` no longer return `fitnessLevel`; migration 007 deletes Goals saved without a VDOT, then drops the column. The Goal form cannot be submitted before the fitness assessment is done.
- The plan prompt now gets Daniels training paces computed in Python from the VDOT (`training_paces`, checked against Table 5.2) and a `VDOT GUIDANCE` section with the long run, threshold and interval limits.
- Fixed the fitness chat scrolling the whole page to the bottom after each message.
- Older specs that mention `fitness_level` carry a "superseded" note pointing to the ADR.

## 2026-06-17

- Added Phase 2 specs for Strava sync and real-data analysis: requirements, implementation plan, and validation criteria covering OAuth connect flow, webhook ingestion, activity-to-workout matching, and Claude-powered pace/HR/load analysis.

## 2026-06-15

- Bootstrapped the running coach application with goal intake and AI-based training plan generation.

## 2026-06-13

- Initial specs and project skeleton.
