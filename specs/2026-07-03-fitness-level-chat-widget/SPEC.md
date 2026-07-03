# Fitness Assessment Chat Widget — Spec

## 1. Objective

Replace the static "Fitness Level" dropdown in `GoalForm` with a **VDOT-based fitness assessment**. Instead of asking the runner to self-classify as beginner/intermediate/advanced (an arbitrary label), fitness level is derived from real performance data via the **VDOT score** (Jack Daniels / Daniels–Gilbert system — the industry standard VO2max proxy).

The runner has three ways to establish their level, all producing the same `{ level, vdot }` result and feeding the same result card:

1. **Start Assessment (chat)** — Claude asks for a recent race time, weekly volume, and longest run, then classifies. For runners who don't know their numbers.
2. **Race Time (PR)** — runner enters a recent race distance + time; the Daniels–Gilbert formula converts it to VDOT **in the browser** (deterministic, instant, no AI call).
3. **VDOT** — power users enter their VDOT directly.

The abstract beginner/intermediate/advanced dropdown is removed from the default view — establishing the level from concrete data is the entire point of this feature.

**Target user:** A runner on the goal intake form who doesn't know whether they're beginner, intermediate, or advanced relative to marathon training.

**Success criterion:** Runner establishes their fitness level in ≤ 5 chat turns *or* one manual entry; the level is set with a one-line reason showing the VDOT basis; the rest of the form is unaffected.

---

## 2. Commands

```bash
# Backend (from repo root, venv active)
uvicorn app.main:app --reload

# Frontend dev server (hot-reload)
cd frontend && npm run dev        # proxies /goal, /goals, /fitness-chat to :8000

# Frontend production build
cd frontend && npm run build      # outputs to frontend/dist/

# Tests
pytest tests/test_fitness_chat.py -v
```

---

## 3. Feature Scope

### In scope
- `POST /fitness-chat` — stateless endpoint; accepts conversation history + latest user message; returns Claude's next question or a final classification with VDOT.
- `FitnessChat` React component — inline chat UI inside `GoalForm`, shown when "Start Assessment" is clicked.
- **Manual entry** — `frontend/src/lib/vdot.js` implements the Daniels–Gilbert formula; a two-mode card in `GoalForm` lets the runner enter a race time (distance + time → VDOT) or a raw VDOT, with a live preview.
- **Three chat signals** Claude collects: recent race time + distance, weekly running km, longest single run in last 3 months.
- Fitness level derived from VDOT (both paths use the same thresholds):
  - VDOT < 35 → `beginner`
  - VDOT 35–50 → `intermediate`
  - VDOT > 50 → `advanced`
- On result (chat or manual): set `fitnessLevel`; show a result card with a level badge, VDOT pill, and one-line reason. Form continues normally. Runner can "Reassess" to start over.

### Out of scope
- Replacing the entire goal form with chat (Phase 4).
- Persisting chat history or raw signals to the database (Phase 1.1 — GoalRequest is unchanged).
- Passing `vdot`/`weeklyKm`/`longestRunKm` through to the plan generator — the improvement in Phase 1.1 is that `fitnessLevel` is accurately derived, not that raw signals flow through. Passing raw signals to Claude's plan prompt is Phase 1.2.
- Streaming responses.
- Authentication.

---

## 4. API Contract

### `POST /fitness-chat`

**Request:**
```json
{
  "history": [
    { "role": "assistant", "content": "..." },
    { "role": "user", "content": "..." }
  ],
  "message": "I ran a 10K in 52 minutes last month"
}
```
`history` is `[]` and `message` is `""` on the first call.

**Response — still asking:**
```json
{
  "done": false,
  "message": "Great — and how many kilometres do you run in a typical week?"
}
```

**Response — classification ready:**
```json
{
  "done": true,
  "fitnessLevel": "intermediate",
  "vdot": 43,
  "weeklyKm": 40,
  "longestRunKm": 18,
  "message": "Based on your 52-min 10K (VDOT 43) and 40 km weekly base, you're solidly intermediate — a good aerobic foundation to build on.",
  "reasoning": "VDOT 43 from 10K 52:00; 40 km/week; longest run 18 km → intermediate"
}
```

`fitnessLevel` ∈ `"beginner"` | `"intermediate"` | `"advanced"`.
`vdot` is a rounded integer.

---

## 5. Architecture

### Backend — `app/api/fitness_chat.py`
- Single `POST /fitness-chat` route using `get_ai_client_dep()`.
- Pydantic models: `ChatMessage`, `FitnessChatRequest`, `FitnessChatResponse(done, message, fitnessLevel=None, vdot=None, weeklyKm=None, longestRunKm=None, reasoning=None)`.
- System prompt instructs Claude to:
  - Be a warm, encouraging running coach.
  - Collect the three signals in any order: race time + distance, weekly km, longest run.
  - Once all three are known, output a fenced JSON classification block:
    ```
    ```json
    {
      "fitness_level": "intermediate",
      "vdot": 43,
      "weekly_km": 40,
      "longest_run_km": 18,
      "reasoning": "..."
    }
    ```
    ```
  - VDOT reference table in the prompt (accurate Daniels–Gilbert values, matching `vdot.js`): 5K 35:00→26, 5K 25:00→38, 5K 20:00→50; 10K 60:00→32, 10K 52:00→38, 10K 45:00→45, 10K 40:00→52; HM 2:00→36, HM 1:45→43, HM 1:30→51; FM 4:30→33, FM 4:00→38, FM 3:30→45.
  - Fitness level threshold: VDOT < 35 = beginner, 35–50 = intermediate, > 50 = advanced.
- Parse `AIResponse.content` for the JSON block via regex; validate `fitness_level` ∈ valid set → 422 if not.
- No DB writes. No new repositories.
- Register router in `app/main.py`.

### Frontend — `frontend/src/lib/vdot.js`
- Pure functions, no React. Implements the **Daniels–Gilbert VDOT model**:
  - `parseTimeToSeconds(str)` — accepts `MM:SS` or `H:MM:SS`.
  - `vdotFromRace(distanceMeters, timeSeconds)` — the formula.
  - `levelFromVdot(vdot)` — thresholds (< 35 / ≤ 50 / else).
  - `assessRace(distanceKey, timeStr)` and `assessVdot(input)` — convenience wrappers returning `{ vdot, level }` or `null`.
  - `RACE_DISTANCES` — 5K / 10K / half / full metadata (meters, label, time hint, placeholder).

### Frontend — `frontend/src/components/FitnessChat.jsx`
- Props: `onResult(fitnessLevel, vdot, weeklyKm, longestRunKm, reasoning)`
- State: `messages[]`, `input`, `loading`
- First render: POST `{ history: [], message: "" }` → display opening question.
- Each turn: append to history, POST, append reply; on `done: true` call `onResult`.
- Plain CSS, no UI library.

### `GoalForm.jsx` changes
- Keep the `fitnessLevel` field in form state (GoalRequest model unchanged in Phase 1.1). The abstract `<select>` is removed from the default view.
- Fitness section has three UI states:
  - **A — not assessed:** assessment card with "Start Assessment" (opens chat) and "I know my race time or VDOT" (opens manual entry). Manual entry is a segmented toggle (Race Time / VDOT) with live preview and a "Use this" confirm.
  - **B — chat open:** `FitnessChat` embedded.
  - **C — assessed:** result card (level badge, VDOT pill, weekly/longest chips when present, reasoning, "Reassess").
- Chat calls `onResult`; manual entry calls `confirmManual()` — both route through `handleAssessmentResult(level, vdot, weeklyKm, longestRunKm, reasoning)`.
- Raw signals (`vdot`, `weeklyKm`, `longestRunKm`) are held in local React state only — not submitted with the form in Phase 1.1.

---

## 6. Code Style

- Python: typed signatures, `AIClient` abstraction, no raw SQL.
- React: functional components, `useState`, plain CSS — match `GoalForm.jsx` style.
- No new npm packages.
- No comments unless the why is non-obvious.

---

## 7. Testing Strategy

**`tests/test_fitness_chat.py`** — uses `FakeFitnessChatAIClient` via `app.dependency_overrides`.

| Test | Assertion |
|---|---|
| First call (empty history) | 200, `done: false`, non-empty `message` |
| Mid-conversation | 200, `done: false`, follow-up question |
| Final turn — valid JSON block with vdot | 200, `done: true`, `fitnessLevel` valid, `vdot` integer |
| Invalid `fitnessLevel` in JSON block | 422 |
| Long history (5 prior turns) | 200, no error |

---

## 8. Boundaries

| Category | Rule |
|---|---|
| **Always do** | Use `AIClient` abstraction. Keep stateless. Pre-fill only, never auto-submit. |
| **Ask first** | Any change to `GoalRequest` model or `/goal` endpoint. Passing raw signals to the plan generator (Phase 1.2). Adding new DB migrations. |
| **Never do** | Call Anthropic/Gemini SDK directly in route handlers. Store chat messages in DB. Replace the full form with chat (Phase 4). |
