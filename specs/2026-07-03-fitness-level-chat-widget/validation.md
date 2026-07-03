# Phase 1.1 — Fitness Assessment Chat Widget: Validation

## Definition of Done

Phase 1.1 is ready to merge when all checks below pass.

---

## 1. Automated Tests

Run with: `pytest tests/test_fitness_chat.py -v`

| # | Test | Pass criterion |
|---|---|---|
| 1.1 | First call (empty history + empty message) | HTTP 200; `done: false`; `message` is non-empty string |
| 1.2 | Mid-conversation turn | HTTP 200; `done: false`; `message` is a non-empty follow-up question |
| 1.3 | Final turn — fake AI embeds valid JSON block | HTTP 200; `done: true`; `fitnessLevel` ∈ `{beginner, intermediate, advanced}`; `vdot` is an integer; `weeklyKm` and `longestRunKm` are numbers; `message` non-empty |
| 1.4 | Fake AI returns invalid `fitnessLevel` (e.g. `"elite"`) | HTTP 422 |
| 1.5 | History with 5 prior turns | HTTP 200; processes without error |

No database required. All tests use `FakeFitnessChatAIClient` via `app.dependency_overrides`.

---

## 2. Manual Walkthrough

Start the app:
```bash
uvicorn app.main:app --reload
cd frontend && npm run dev
```
Open **http://localhost:5173/app**.

| Step | Expected behaviour |
|---|---|
| Load the goal form | Fitness Level dropdown shows `beginner / intermediate / advanced`; "Not sure? Let me help →" button visible below it |
| Click "Not sure? Let me help →" | Chat slides open; Claude's opening question appears immediately (asks about a recent race time) |
| Answer 3 signals across ≤ 5 turns | Each reply triggers a warm follow-up; Claude covers race time + distance, weekly km, longest run |
| Claude classifies | Final message cites VDOT (e.g. "VDOT 43 from your 52-min 10K"); dropdown pre-filled; one-line reason visible below select |
| Widget collapses | Chat area closes; form looks normal with pre-filled dropdown |
| Submit the form | Form submits with pre-filled `fitnessLevel` — no regression to existing goal flow |
| Manual override | Runner can still change the dropdown after pre-fill; form submits with the manually selected value |

---

## 3. Tone Check

Read Claude's messages during the walkthrough and confirm:
- [ ] Opening question feels like a coach starting a conversation — not a form prompt
- [ ] Follow-up questions acknowledge the previous answer ("Nice — a 52-min 10K is a solid base…")
- [ ] Classification message is encouraging and cites VDOT, not just a label
- [ ] No message sounds clinical, robotic, or like a survey

---

## 4. VDOT Accuracy Check

Manually verify classification boundaries with these inputs:

| Race input | Expected VDOT | Expected level |
|---|---|---|
| 5K in 35:00 | ~30 | beginner |
| 10K in 52:00 | ~43 | intermediate |
| 10K in 45:00 | ~52 | advanced |
| HM in 1:55:00 | ~44 | intermediate |
| FM in 4:30:00 | ~39 | intermediate |

---

## 5. Regression Check

- [ ] Existing `POST /goal` flow is unaffected (GoalRequest model unchanged)
- [ ] Goal form submits correctly with all three fitness level values — both chat-derived and manually selected
- [ ] `GET /goal/{goalId}/plan` polling and plan view still work end-to-end

---

## 6. Merge Blockers

- Anthropic/Gemini SDK called directly in `fitness_chat.py` (must use `AIClient`)
- Chat history persisted to DB
- Any change to `GoalRequest` model or `/goal` endpoint
- Widget auto-submits the form on classification (must only pre-fill)
- `vdot` / `weeklyKm` / `longestRunKm` passed to `POST /goal` (out of scope for Phase 1.1)
- Plain CSS replaced with a UI library
