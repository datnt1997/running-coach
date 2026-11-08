# Validation: VDOT-based level assessment

## Automated (no API key needed)

```bash
pytest
cd frontend && npm run build && npm run check:i18n && npm run check:vdot
```

- `tests/test_vdot.py`: VDOT from race time matches Table 5.1 within 0.15 (5K–FM); predicted times match within 1%; level by sex matches Table 5.6; age examples from R1 pass.
- Goal endpoint: with `vdot`, it is saved and shows in the plan prompt; without it, behavior matches `main`.
- Fitness chat tests (fake client): sex and age are asked before anything else; a full assessment returns VDOT, level and predicted times; missing signals do not finish early.
- Strava estimate tests (fake client): enough data, too little data, no connection (falls back to questions).

## Status (2026-11-08)

- Tasks 1-5 and 7 done and committed on branch `vdot-level-assessment`; automated checks above pass (`tests/test_model_routing.py::test_gemini_model_env` fails on `main` too, unrelated).
- Task 6 (Strava estimate) not started: blocked on the R2 sample payload.
- Manual steps below not yet run (no browser run, no live AI call).

## Manual

1. Run through the chat as a man and as a woman with the same 10K time; the level should differ where Table 5.6 says it does.
2. Run again as an older runner (R1 examples); the level should reflect the age adjustment.
3. Confirm the predicted 5K / 10K / HM / FM times against the book's Table 5.1 for the printed VDOT.
4. Generate a plan; check the prompt (or logs) includes VDOT and the stored `user_goals.vdot` is set.
5. With Strava connected, check the estimate against a known recent race.

## Decision rule

- All automated checks pass and the manual comparisons match the book: ship.
- Strava estimate is unreliable on the manual comparison (more than about 2 VDOT off a known race): ship tasks 1–5 and 7 without task 6, and keep the question flow as the only path.
