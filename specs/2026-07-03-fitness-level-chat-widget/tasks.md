# Phase 1.1 — Fitness Assessment Chat Widget: Tasks

## Status Summary (as of implementation)

| Task | Status | Note |
|---|---|---|
| 1.1 — `POST /fitness-chat` endpoint | ✅ Done | 5/5 tests green |
| 1.2 — Register router + Vite proxy | ✅ Done | — |
| 2.1 — FitnessChat component | ✅ Done | Trigger is "Start Assessment", not "Not sure? Let me help →" |
| 2.2 — FitnessChat CSS | ✅ Done (diverged) | No `.fitness-chat--open` slide transition — widget renders conditionally. `.fitness-reason` shipped but is now dead (reason shows in `.assessment-result__reasoning`) |
| 3.1 — GoalForm integration | ✅ Done (superseded) | Rebuilt as the VDOT/PR **three-state UI** (assessment card → chat/manual → result card). The abstract `<select>` was removed; state vars and scenarios below describe the original plan and no longer map 1:1. See `IMPLEMENTATION.md §1–2` |
| 4.1 — Backend tests | ✅ Done | `pytest tests/test_fitness_chat.py -v` → 5 passed |

**Later additions not in the original task list** (see `IMPLEMENTATION.md`): manual VDOT/PR entry (`frontend/src/lib/vdot.js`), nested-form + StrictMode fixes, `button.link-subtle` hover fix, and GoalHistory "View Plan"/"Track" buttons.

---

## Task: 1.1 — POST /fitness-chat endpoint

**Spec section**: `requirements.md §API Contract`, `plan.md Group 1`
**Complexity**: Medium
**Parallel** `[P]`: No
**Depends on**: none
**Estimated time**: 1.5 hours

---

### 1. The goal is clear

> As a **runner on the goal form**, I want **to send a message and receive either a follow-up question or a VDOT-based fitness classification** so that **my fitness level is derived from my actual performance, not a label I have to guess**.

- **Role**: Runner interacting with the goal form chat widget
- **Outcome**: Stateless endpoint that collects three performance signals and returns a VDOT-derived `fitnessLevel` with supporting data
- **Benefit**: Classification accuracy — a 52-min 10K runner gets "intermediate" because VDOT 43 maps there, not because they guessed

---

### 2. The scope is bounded

**In scope:**
- Pydantic models: `ChatMessage`, `FitnessChatRequest`, `FitnessChatResponse`
- System prompt: warm coach persona; collect race time+distance, weekly km, longest run; embed VDOT reference table; output fenced JSON block; thresholds: < 35 = beginner, 35–50 = intermediate, > 50 = advanced
- Parse `AIResponse.content` for ` ```json ` block; extract and validate all fields
- Raise 422 if `fitness_level` ∉ `{beginner, intermediate, advanced}`
- Use `get_ai_client_dep()` — no direct SDK calls

**Non-goals (explicitly deferred):**
- Do not persist chat history or signals to DB
- Do not enforce a server-side turn-count limit
- Do not add streaming support
- Do not change `GoalRequest` model

---

### 3. What is the expected behavior

**Scenario: First call — opening question**
- Given: `history: []`, `message: ""`
- When: `POST /fitness-chat`
- Then: HTTP 200; `done: false`; `message` is a warm coaching question asking about a recent race

**Scenario: Mid-conversation — follow-up**
- Given: `history` has 2 prior turns; `message` contains a user answer
- When: `POST /fitness-chat`
- Then: HTTP 200; `done: false`; `message` is a non-empty follow-up question

**Scenario: Classification ready**
- Given: Claude has collected all 3 signals; embeds ` ```json\n{"fitness_level":"intermediate","vdot":43,"weekly_km":40,"longest_run_km":18,"reasoning":"..."}\n``` `
- When: `POST /fitness-chat`
- Then: HTTP 200; `done: true`; `fitnessLevel: "intermediate"`; `vdot: 43`; `weeklyKm: 40`; `longestRunKm: 18`; `message` non-empty

**Scenario: Invalid fitnessLevel — negative**
- Given: Claude embeds ` ```json\n{"fitness_level":"elite","vdot":65,...}\n``` `
- When: `POST /fitness-chat`
- Then: HTTP 422

---

### 4. Invariants

- [ ] `done: true` only when a valid JSON block with `fitness_level` ∈ valid set is present in `AIResponse.content`
- [ ] When `done: false`, `fitnessLevel`, `vdot`, `weeklyKm`, `longestRunKm`, `reasoning` are absent from the response body
- [ ] `AIClient.generate()` is called exactly once per request
- [ ] No SQL, DB import, or repository call appears anywhere in `fitness_chat.py`

---

### 5. Acceptance criteria

**Automated:**
- [x] `POST /fitness-chat` with empty history → 200, `done: false`, non-empty `message`
- [x] `POST /fitness-chat` with valid JSON block → 200, `done: true`, `fitnessLevel` ∈ valid set, `vdot` is integer
- [x] `POST /fitness-chat` with `fitness_level: "elite"` in JSON block → 422
- [x] `pytest tests/test_fitness_chat.py -v` passes (all 5 cases)

**Release evidence:**
- [x] `curl -X POST http://localhost:8000/fitness-chat -d '{"history":[],"message":""}' ` → 200, `done: false`, readable coach-tone opening question

---

### Files (≤ 3)

| File | What changes |
|------|-------------|
| `app/api/fitness_chat.py` | New file — models, system prompt with VDOT table, route handler, JSON-block parser |

---

### Definition of done

- [x] All §3 scenarios have a passing test
- [x] All §4 invariants have a passing assertion
- [x] All §5 automated criteria are green
- [x] Release evidence completed
- [x] Files touched ≤ 3

---

## Task: 1.2 — Register router and update Vite proxy

**Spec section**: `plan.md Group 1, Task 1.2`
**Complexity**: Low
**Parallel** `[P]`: No
**Depends on**: Task 1.1
**Estimated time**: 0.25 hours

---

### 1. The goal is clear

> As a **developer running the app**, I want **`/fitness-chat` wired into FastAPI and the Vite dev proxy** so that **the frontend can reach the endpoint in both development and production**.

- **Role**: Developer / frontend component
- **Outcome**: Router registered in `app/main.py`; `/fitness-chat` added to `vite.config.js`
- **Benefit**: Without this, all frontend requests get 404 or CORS error in dev

---

### 2. The scope is bounded

**In scope:**
- `app.include_router(fitness_chat.router)` in `app/main.py`
- `'/fitness-chat': 'http://localhost:8000'` in `vite.config.js` `server.proxy`

**Non-goals (explicitly deferred):**
- Do not change any existing router registration
- Do not add authentication middleware

---

### 3. What is the expected behavior

**Scenario: Route registered**
- Given: `uvicorn app.main:app` is running
- When: `GET /fitness-chat` is called
- Then: HTTP 405 (route exists, wrong method — not 404)

**Scenario: Missing router — negative**
- Given: `fitness_chat.router` NOT included in `main.py`
- When: `POST /fitness-chat` is called
- Then: HTTP 404

**Scenario: Vite proxy**
- Given: Vite dev server running; FastAPI on `:8000`
- When: Frontend POSTs to `/fitness-chat`
- Then: Request reaches FastAPI without CORS error

---

### 4. Invariants

- [ ] All existing routers remain registered and unchanged
- [ ] `uvicorn app.main:app` starts without import errors after the change

---

### 5. Acceptance criteria

**Automated:**
- [x] `uvicorn app.main:app` starts without error
- [x] `GET http://localhost:8000/fitness-chat` → 405 (not 404)

**Release evidence:**
- [x] Vite dev server starts; browser network tab shows `/fitness-chat` request reaching FastAPI at 200

---

### Files (≤ 3)

| File | What changes |
|------|-------------|
| `app/main.py` | Add `app.include_router(fitness_chat.router)` |
| `frontend/vite.config.js` | Add `/fitness-chat` to `server.proxy` |

---

### Definition of done

- [x] All §3 scenarios verified
- [x] All §4 invariants hold
- [x] All §5 criteria met
- [x] Files touched ≤ 3

---

## Task: 2.1 — FitnessChat React component

**Spec section**: `requirements.md §Architecture`, `plan.md Group 2`
**Complexity**: Medium
**Parallel** `[P]`: No
**Depends on**: Task 1.2
**Estimated time**: 1.5 hours

---

### 1. The goal is clear

> As a **runner who clicked "Not sure? Let me help →"**, I want **a chat interface that asks me about my running and tells me my fitness level based on my actual performance** so that **I don't have to guess from a label**.

- **Role**: Runner interacting with the inline chat widget
- **Outcome**: React component that drives a multi-turn conversation and calls `onResult` with VDOT-based classification data
- **Benefit**: Encapsulates all chat state and API calls — `GoalForm` only receives the result

---

### 2. The scope is bounded

**In scope:**
- Props: `onResult(fitnessLevel, vdot, weeklyKm, longestRunKm, reasoning)`
- State: `messages[]`, `input`, `loading`
- First render: POST `{ history: [], message: "" }` → display opening question
- Each turn: POST with full history; append reply; on `done: true` call `onResult`
- Disable input while `loading`

**Non-goals (explicitly deferred):**
- Do not handle collapse/open (parent controls visibility)
- Do not stream responses
- Do not render VDOT number to the user — that's GoalForm's job via `reasoning`

---

### 3. What is the expected behavior

**Scenario: Opens and shows first question**
- Given: Component mounts
- When: Initial render completes
- Then: One assistant message with coach-tone opening question; input enabled

**Scenario: User sends a message**
- Given: One assistant message displayed; user types answer
- When: User submits
- Then: User message appended; `loading: true`; assistant follow-up appended on response

**Scenario: Classification received**
- Given: Conversation has progressed; server returns `done: true` with `vdot`, `weeklyKm`, `longestRunKm`
- When: Response processed
- Then: `onResult(fitnessLevel, vdot, weeklyKm, longestRunKm, reasoning)` called once; input disabled

**Scenario: Submit while loading — negative**
- Given: `loading: true`
- When: User presses Enter or clicks send
- Then: No additional POST fired; input remains disabled

---

### 4. Invariants

- [ ] `onResult` called exactly once — never on `done: false` responses
- [ ] Each POST includes all accumulated history plus the new message
- [ ] Empty `input` does not dispatch a POST
- [ ] `loading` is `true` between POST dispatch and response; `false` otherwise

---

### 5. Acceptance criteria

**Release evidence:**
- [ ] Opening question appears within 3 s of component mounting
- [ ] Send 2 answers; each receives a follow-up; thread grows correctly
- [ ] On classification, `onResult` fires; GoalForm's select is pre-filled and VDOT reason hint appears
- [ ] Rapid double-submit does not send two requests

---

### Files (≤ 3)

| File | What changes |
|------|-------------|
| `frontend/src/components/FitnessChat.jsx` | New file — chat component |

---

### Definition of done

- [x] All §3 scenarios verified manually
- [x] All §4 invariants confirmed by code inspection and manual test
- [x] Release evidence completed
- [x] Files touched ≤ 3

---

## Task: 2.2 — FitnessChat CSS

**Spec section**: `requirements.md §Context`, `plan.md Group 2`
**Complexity**: Low
**Parallel** `[P]`: Yes — can run concurrently with Task 2.1
**Depends on**: none
**Estimated time**: 0.5 hours

---

### 1. The goal is clear

> As a **runner viewing the chat widget**, I want **the chat to look like it belongs in the goal form** so that **the experience feels consistent, not bolted-on**.

- **Role**: Runner reading the chat thread
- **Outcome**: Chat bubbles, input row, slide-open container using existing `App.css` palette
- **Benefit**: No visual inconsistency; no new CSS library

---

### 2. The scope is bounded

**In scope:**
- `.fitness-chat` container with CSS height transition
- `.fc-bubble--assistant` (left) and `.fc-bubble--user` (right)
- `.fc-input-row` — text input + send button
- `.fitness-reason` — small hint below the select after pre-fill
- Colors and radii match existing `App.css` values

**Non-goals:**
- No JS animation library
- No dark mode
- No new hex color values not already in `App.css`

---

### 3. What is the expected behavior

**Scenario: Widget opens**
- Given: Parent adds `.fitness-chat--open` class
- When: CSS transition runs
- Then: Widget slides open smoothly; content visible

**Scenario: Widget closed — negative**
- Given: `.fitness-chat--open` absent
- When: Component rendered
- Then: Height 0; content not visible; no layout shift on surrounding form fields

---

### 4. Invariants

- [ ] `.fitness-chat` when closed does not push form fields down (height 0, overflow hidden)
- [ ] All color values reuse existing `App.css` variables — no new hex values

---

### 5. Acceptance criteria

**Release evidence:**
- [ ] 1280px: bubbles aligned; input row flush to bottom
- [ ] 375px: no horizontal overflow; text wraps cleanly
- [ ] Open/close 3 times: no layout jump on surrounding fields

---

### Files (≤ 3)

| File | What changes |
|------|-------------|
| `frontend/src/App.css` | Add `.fitness-chat`, bubble, input-row, `.fitness-reason` rules |

---

### Definition of done

- [x] Chat styling shipped (bubbles, input row, palette match)
- [~] Slide-open `.fitness-chat--open` scenario — NOT implemented; widget renders conditionally instead
- [x] Release evidence completed
- [x] Files touched ≤ 3

---

## Task: 3.1 — GoalForm integration

**Spec section**: `requirements.md §GoalForm integration`, `plan.md Group 3`
**Complexity**: Medium
**Parallel** `[P]`: No
**Depends on**: Task 2.1, Task 2.2
**Estimated time**: 1 hour

---

### 1. The goal is clear

> As a **runner on the goal form**, I want **the chat result to pre-fill my fitness level with a VDOT-based reason I can trust** so that **I know exactly why the classification was made and can override it if I disagree**.

- **Role**: Runner filling in the goal form
- **Outcome**: Button → chat → `fitnessLevel` pre-filled with VDOT reason; raw signals held in local state; form unchanged otherwise
- **Benefit**: Additive — runners who know their level are unaffected; those who don't get a coach-quality classification

---

### 2. The scope is bounded

**In scope:**
- New state: `fitnessChatOpen`, `fitnessChatReason`, `fitnessChatVdot`, `fitnessChatWeeklyKm`, `fitnessChatLongestRun`
- "Not sure? Let me help →" button below the `fitnessLevel` select
- `onResult`: `set('fitnessLevel', level)`, store raw signals in local state, `setFitnessChatOpen(false)`
- `<small className="fitness-reason">` showing VDOT-based reason below select

**Non-goals (explicitly deferred):**
- Do not pass `vdot`/`weeklyKm`/`longestRunKm` to `POST /goal` — Phase 1.2
- Do not auto-submit the form on classification
- Do not hide or lock the select while chat is open or after pre-fill
- Do not change `handleSubmit` or `validate()`

---

### 3. What is the expected behavior

**Scenario: Button opens chat**
- Given: Form loaded; `fitnessChatOpen: false`
- When: Runner clicks "Not sure? Let me help →"
- Then: `fitnessChatOpen: true`; `FitnessChat` renders and slides open

**Scenario: VDOT classification pre-fills select**
- Given: Chat open; runner completes conversation
- When: `onResult("intermediate", 43, 40, 18, "VDOT 43 from 10K 52:00…")` fires
- Then: `fitnessLevel` select shows `"intermediate"`; reason hint shows "VDOT 43 from 10K 52:00…"; chat collapses

**Scenario: Manual override after pre-fill**
- Given: Select pre-filled with `"intermediate"`
- When: Runner changes select to `"beginner"`
- Then: `form.fitnessLevel` is `"beginner"`; form submits with `"beginner"`

**Scenario: Form submits without using chat — negative**
- Given: Runner never clicked "Not sure?"; set `fitnessLevel` manually
- When: Form submitted
- Then: Submission unchanged — no regression; raw signal state is `null`/`0` and irrelevant

---

### 4. Invariants

- [ ] `FitnessChat` rendered only when `fitnessChatOpen: true`
- [ ] `onResult` sets `fitnessLevel` via existing `set()` helper
- [ ] `fitnessLevel` select remains enabled at all times
- [ ] `handleSubmit` and `validate()` are not modified
- [ ] `vdot`/`weeklyKm`/`longestRunKm` are NOT included in the form body sent to `POST /goal`

---

### 5. Acceptance criteria

**Release evidence:**
- [ ] Click "Not sure?" → chat opens; other fields unaffected
- [ ] Complete chat → select pre-filled; VDOT reason hint visible; chat collapsed
- [ ] Change select after pre-fill → form submits with new value
- [ ] Submit form without chat → plan generates correctly (regression)

---

### Files (≤ 3)

| File | What changes |
|------|-------------|
| `frontend/src/pages/GoalForm.jsx` | Add `fitnessChatOpen`/reason/vdot state, button, conditional `FitnessChat` render, reason hint |

---

### Definition of done

- [x] Fitness assessment integrated into GoalForm; `fitnessLevel` set from result; form regression-free
- [~] Original scenarios (select pre-fill, "Not sure?" trigger, override-via-select) — superseded by the three-state VDOT/PR UI. See `IMPLEMENTATION.md §1–2`
- [x] Release evidence completed (manual walkthrough)
- [x] Files touched ≤ 3 (GoalForm.jsx; +vdot.js added under Task-list extras)

---

## Task: 4.1 — Backend tests

**Spec section**: `validation.md §1`, `plan.md Group 4`
**Complexity**: Medium
**Parallel** `[P]`: No
**Depends on**: Task 1.1, Task 1.2
**Estimated time**: 1 hour

---

### 1. The goal is clear

> As a **developer merging this feature**, I want **automated tests covering all endpoint scenarios** so that **regressions are caught before merge without a live AI call or database**.

- **Role**: Developer / CI pipeline
- **Outcome**: 5 passing tests using `FakeFitnessChatAIClient`; no DB or real AI required
- **Benefit**: Fast, deterministic, safe to run in CI

---

### 2. The scope is bounded

**In scope:**
- `FakeFitnessChatAIClient` in `tests/conftest.py` — configurable between "question" and "classification" modes
- 5 test functions in `tests/test_fitness_chat.py`
- `app.dependency_overrides[get_ai_client_dep]` pattern matching existing tests

**Non-goals:**
- Do not test the React component
- Do not test against a real AI provider
- Do not add DB fixtures — endpoint is stateless

---

### 3. What is the expected behavior

**Scenario: First call**
- Given: Fake returns plain text (no JSON block); `history: []`, `message: ""`
- When: `POST /fitness-chat`
- Then: 200; `done: false`; `message` non-empty

**Scenario: Mid-conversation**
- Given: Fake returns plain text; `history` has 2 prior turns
- When: `POST /fitness-chat`
- Then: 200; `done: false`; `message` non-empty

**Scenario: Classification**
- Given: Fake returns content with ` ```json\n{"fitness_level":"intermediate","vdot":43,"weekly_km":40,"longest_run_km":18,"reasoning":"..."}\n``` `
- When: `POST /fitness-chat`
- Then: 200; `done: true`; `fitnessLevel: "intermediate"`; `vdot: 43`; integers for `weeklyKm` and `longestRunKm`

**Scenario: Invalid fitnessLevel — negative**
- Given: Fake returns ` ```json\n{"fitness_level":"elite","vdot":65,...}\n``` `
- When: `POST /fitness-chat`
- Then: 422

**Scenario: Long history**
- Given: `history` has 5 turns; fake returns plain text
- When: `POST /fitness-chat`
- Then: 200; no server error

---

### 4. Invariants

- [ ] `FakeFitnessChatAIClient` used via `app.dependency_overrides` — no monkeypatching
- [ ] No `DATABASE_URL` required for any test in this file
- [ ] `app.dependency_overrides.clear()` called after each test

---

### 5. Acceptance criteria

**Automated:**
- [x] `pytest tests/test_fitness_chat.py -v` → 5 passed, 0 failed
- [x] Tests pass without `DATABASE_URL` set
- [x] Test 1.3 asserts `vdot == 43` (integer, not string)

---

### Files (≤ 3)

| File | What changes |
|------|-------------|
| `tests/conftest.py` | Add `FakeFitnessChatAIClient` class |
| `tests/test_fitness_chat.py` | New file — 5 test functions |

---

### Definition of done

- [x] All §3 scenarios have a passing test
- [x] All §4 invariants verified
- [x] `pytest tests/test_fitness_chat.py -v` is green
- [x] Files touched ≤ 3
