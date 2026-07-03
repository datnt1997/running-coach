# Phase 1.1 — Fitness Assessment Chat Widget: Implementation Plan

## Assumptions

1. CSS goes into `App.css` — no per-component CSS files exist in this project.
2. Claude's JSON classification is embedded in its reply as a fenced ` ```json ` block — regex-extracted server-side; if absent → `done: false`.
3. `/fitness-chat` is added to `vite.config.js` proxy alongside `/goal` and `/goals`.
4. `FakeFitnessChatAIClient` lives in `tests/conftest.py` alongside the existing fake clients.
5. No new Python packages needed — `AIClient.generate(messages)` handles plain-text calls without tools.
6. `GoalRequest` model is NOT changed in Phase 1.1 — `vdot`/`weeklyKm`/`longestRunKm` are held in React local state only and not submitted with the form.

---

## Implementation Order

```
Group 1: Backend endpoint      ← no frontend dependency
    ↓
Group 2: FitnessChat component ← depends on /fitness-chat existing
    ↓
Group 3: GoalForm integration  ← depends on FitnessChat component
    ↓
Group 4: Tests                 ← depends on endpoint + conftest pattern
```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Claude computes VDOT inaccurately | Embed a VDOT reference table in the system prompt (5K/10K/HM/FM sample times → VDOT); validate VDOT is a plausible integer (20–80) in the parser |
| JSON block not cleanly embedded | Use strict fenced block format in the prompt; regex-parse; treat parse failure as `done: false` |
| Runner has no recent race time | System prompt instructs Claude to fall back to pace-effort question ("What pace do you run at a comfortable effort?") and estimate VDOT from that |
| Mobile layout breaks | Widget max-width matches form at 480px; tested manually at 375px |

---

## Group 1 — Backend Endpoint

- [ ] **Task 1.1** — Create `app/api/fitness_chat.py`
  - Acceptance: `POST /fitness-chat` returns `{done: false, message}` while collecting signals; `{done: true, fitnessLevel, vdot, weeklyKm, longestRunKm, message, reasoning}` on classification; 422 if `fitnessLevel` is invalid
  - Verify: `curl -X POST http://localhost:8000/fitness-chat -H "Content-Type: application/json" -d '{"history":[],"message":""}' ` → 200, `done: false`, coach-tone opening question
  - Files: `app/api/fitness_chat.py`
  - Notes:
    - Pydantic models: `ChatMessage(role, content)`, `FitnessChatRequest(history, message)`, `FitnessChatResponse(done, message, fitnessLevel=None, vdot=None, weeklyKm=None, longestRunKm=None, reasoning=None)`
    - System prompt: warm coach persona; collect three signals (race time+distance, weekly km, longest run); include VDOT reference table; output fenced JSON block when confident; thresholds: VDOT < 35 = beginner, 35–50 = intermediate, > 50 = advanced; fallback if no race time
    - Parse `AIResponse.content` for ` ```json ` block; extract all fields; validate `fitness_level` ∈ `{beginner, intermediate, advanced}` and `vdot` is integer 20–80
    - Raise 422 on invalid `fitness_level`; default invalid `vdot` to 0 (non-blocking)

- [ ] **Task 1.2** — Register router and update Vite proxy
  - Acceptance: `/fitness-chat` reachable at runtime and proxied in Vite dev
  - Verify: `uvicorn app.main:app` starts clean; `curl -X GET http://localhost:8000/fitness-chat` → 405
  - Files: `app/main.py`, `frontend/vite.config.js`

---

## Group 2 — Frontend Component

- [ ] **Task 2.1** — Create `frontend/src/components/FitnessChat.jsx`
  - Acceptance: Renders chat thread; each turn POSTs with full history; on `done: true` calls `onResult(fitnessLevel, vdot, weeklyKm, longestRunKm, reasoning)`
  - Verify: Manual — complete a chat session; confirm `onResult` fires with all fields
  - Files: `frontend/src/components/FitnessChat.jsx`
  - Notes:
    - Props: `onResult(fitnessLevel, vdot, weeklyKm, longestRunKm, reasoning)`
    - State: `messages[]`, `input`, `loading`
    - First render: POST `{ history: [], message: "" }` → opening question
    - Each turn: append user message, POST, append Claude reply; on `done: true` call `onResult`

- [ ] **Task 2.2** — Add FitnessChat CSS to `App.css`
  - Acceptance: Assistant/user bubbles, input row, slide-open container — styled to match existing palette
  - Verify: Visual check at 1280px and 375px
  - Files: `frontend/src/App.css`

---

## Group 3 — GoalForm Integration

- [ ] **Task 3.1** — Integrate FitnessChat into `GoalForm.jsx`
  - Acceptance: Button opens chat; `onResult` pre-fills `fitnessLevel` select and stores `vdot`/`weeklyKm`/`longestRunKm` in local state; VDOT-based reason hint shown; chat collapses; form submits with pre-filled value; user can still override select
  - Verify: Full manual walkthrough per `validation.md` §2
  - Files: `frontend/src/pages/GoalForm.jsx`
  - Notes:
    - New state: `fitnessChatOpen`, `fitnessChatReason`, `fitnessChatVdot`, `fitnessChatWeeklyKm`, `fitnessChatLongestRun`
    - `onResult`: `set('fitnessLevel', level)`, store raw signals in local state, `setFitnessChatOpen(false)`
    - Raw signals are display-only in Phase 1.1 — not submitted with the form

---

## Group 4 — Tests

- [ ] **Task 4.1** — Add `FakeFitnessChatAIClient` to `tests/conftest.py` and write `tests/test_fitness_chat.py`
  - Acceptance: 5 tests pass; no DB required
  - Verify: `pytest tests/test_fitness_chat.py -v` → 5 passed
  - Files: `tests/conftest.py`, `tests/test_fitness_chat.py`
  - Test cases:
    1. First call (empty history + message) → 200, `done: false`, non-empty `message`
    2. Mid-conversation → 200, `done: false`, follow-up
    3. Final turn with valid JSON block (including `vdot`) → 200, `done: true`, `fitnessLevel` valid, `vdot` integer
    4. Invalid `fitnessLevel` → 422
    5. History with 5 turns → 200, no error
