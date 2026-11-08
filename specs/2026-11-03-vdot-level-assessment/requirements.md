# Requirements: VDOT-based level assessment (sex, age, Strava estimate)

## Objective

The fitness assessment chat estimates a runner's current fitness with Daniels' VDOT, grades the level for the runner's **sex and age** using the book's performance tables, predicts race times, and passes **VDOT** to the plan generator. Runners with Strava connected can get the estimate from their real runs; everyone else keeps the existing question flow.

Source: *Daniels' Running Formula* (local PDF at `references/daniels-running-formula.pdf`, git-ignored, copyrighted: never commit it or long quotes from it). Page numbers below are printed page numbers of the Vietnamese edition.

## Why

- Today's thresholds (VDOT < 35 beginner, 35–50 intermediate, > 50 advanced) match only the **male** column of Table 5.6 (p. 151). A woman with VDOT 45 is level 4–5 in the book but "intermediate" here.
- The book also adjusts levels by age (Tables 5.7 and 5.8, from about age 39). The app ignores age.
- The plan generator receives only `fitness_level` (`app/models/goal.py`, `app/agent/prompt.py:70`). VDOT never reaches the server.

## Verified facts (done during the interview)

- `frontend/src/lib/vdot.js` (`vdotFromRace`) reproduces Table 5.1 (p. 132) for 5K, 10K, 15K, half and full marathon within 0.10 VDOT (rows VDOT 30–76). 1600m and 3200m drift up to 0.74. Distances under 5K are not supported by this feature.
- The book's worked example (p. 130) gives VDOT 55.2; the formula gives 55.26. The book prints 93.7% of max for a 30-minute race where the formula gives 93.0%. Cause unknown; final VDOT agrees.

## Assumptions (correct me before implementation)

1. **VDOT is computed in code, not by the model.** The chat collects signals; Python converts them to VDOT, level, and predictions. Today the model estimates VDOT from a table in its prompt; that is the less reliable path.
2. Sex is asked as a choice the runner picks (male / female). The book only gives two columns; no other value is graded. If the runner declines, use the male column? **Open: decide the fallback.**
3. Age is stored nowhere. The chat asks for age in years; the chat history is not persisted beyond the existing behavior.
4. The 1–10 book level is shown to the runner; the planner receives VDOT plus the existing `fitness_level` label (kept so nothing downstream breaks). Mapping from level to label is an open item (see plan task R3).
5. Race predictions use the same formula inverted (find the time for a distance that gives the same VDOT), for 5K, 10K, half and full marathon only.
6. The Strava estimate is a **second path** that sits beside the existing question flow. Its run-selection rule is not decided yet (see plan tasks R2 and 6).

## In scope

- Chat asks sex and age first, every time. Nothing about them is stored.
- Backend `app/vdot.py`: VDOT from a race result, equivalent race times, level lookup by sex and age.
- Chat result shows VDOT, level, predicted 5K / 10K / HM / FM times.
- Migration `005_goal_vdot.sql`: nullable `vdot` column on `user_goals`.
- `GoalRequest` accepts optional `vdot`; it is saved and put in the plan prompt.
- Strava-based estimate for connected runners, after the research tasks settle the rules.
- Tests for each piece; no test needs an API key or network.

## Out of scope

- Storing sex or age.
- Distances under 5K; predictions beyond 5K / 10K / HM / FM.
- Heart-rate-based VDOT.
- Race-day projections that depend on the training plan.
- Changing model routing (`CHAT_AI_PROVIDER`) or migrating the Gemini SDK.
- Replacing the existing question flow.

## Requirements

1. The chat asks sex and age before any other question.
2. Level for a given VDOT, sex and age follows Table 5.6 (p. 151) with the age adjustment from Tables 5.7 / 5.8, implemented in `app/vdot.py` and unit-tested against hand-checked rows.
3. `app/vdot.py` VDOT matches Table 5.1 within 0.15 for 5K–marathon at every VDOT the table covers.
4. Predicted times for a VDOT reproduce Table 5.1 rows to within 1% of the printed time.
5. `user_goals.vdot` exists (nullable). Older goals stay null and behave as today.
6. When `GoalRequest.vdot` is set, the plan prompt includes it; when null, the prompt is unchanged.
7. If Strava has too little qualifying data, the chat falls back to the question flow and says so.
8. Default behavior with no Strava connection is the existing question flow plus the new sex / age questions.

## Boundaries

- Always: keep tests runnable without API keys (fakes via `dependency_overrides`); keep the Vietnamese replies.
- Ask first: new dependencies, anything beyond migration 005, storing personal data.
- Never: commit the PDF or long passages from it; commit real keys; change JSON-block keys the parser relies on without updating the parser and its tests in the same change.
