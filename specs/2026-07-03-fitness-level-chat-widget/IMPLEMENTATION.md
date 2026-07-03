# Phase 1.1 — Fitness Assessment Widget: IMPLEMENTATION

> As-built reality (not the plan). Branch: `phase-1.1-fitness-level-chat-widget`.
> The spec files describe intent; this describes the code that shipped.

---

## 1. Architecture Map

| File | Owns |
|---|---|
| `app/api/fitness_chat.py` | `POST /fitness-chat` endpoint, Pydantic models, the coach system prompt (`_SYSTEM_PROMPT`), and the JSON-block parser (`_JSON_BLOCK_RE`). |
| `app/main.py` | Registers `fitness_chat.router` (one added line). |
| `frontend/vite.config.js` | Proxies `/fitness-chat` → `:8000` in dev. |
| `frontend/src/lib/vdot.js` | Pure Daniels–Gilbert VDOT math. No React. Exports `RACE_DISTANCES`, `parseTimeToSeconds`, `vdotFromRace`, `levelFromVdot`, `assessRace`, `assessVdot`. |
| `frontend/src/components/FitnessChat.jsx` | The chat widget: fetch loop, message thread, `onResult` callback. |
| `frontend/src/pages/GoalForm.jsx` | The 3-state fitness UI (assessment card → chat/manual → result card) + the rest of the redesigned goal form. |
| `frontend/src/pages/GoalHistory.jsx` | History table. Added the **View Plan** / **Track** action buttons so generated plans are reachable (previously the only link was the hard-to-discover status badge). |
| `frontend/src/App.css` | All styling (chat bubbles, assessment card, seg-toggle, result card, form redesign, `button.link-subtle`, `.row-actions`). Barlow fonts loaded in `frontend/index.html`. |
| `tests/test_fitness_chat.py` + `FakeFitnessChatAIClient` in `tests/conftest.py` | 5 endpoint tests, no DB, no live AI. |

**No new env vars, no new DB migrations, no new dependencies.** Reuses `get_ai_client_dep()` (`AI_PROVIDER` / `ANTHROPIC_API_KEY`).

---

## 2. Data Flow & Dependencies

**Chat path (stateless):**
1. `FitnessChat` mounts → POSTs `{ history: [], message: "" }`. Backend injects `_FIRST_CALL_STARTER` as the user turn (Anthropic requires ≥1 user message) → returns the opening question.
2. Each user turn POSTs `{ history: <all prior turns>, message: <new answer> }`. **History is computed from React `messages` state *before* the new user message is appended** — the new message travels in the `message` field, never in `history`. The backend prepends history then appends message. Do not "fix" this to include the new message in history; it would duplicate the turn.
3. Backend calls `AIClient.generate(messages)` **exactly once** per request. It regex-scans `AIResponse.content` for a ```` ```json ```` block. If found + valid → `done: true` with `{ fitnessLevel, vdot, weeklyKm, longestRunKm, reasoning }` (the JSON block is stripped from the shown `message`). Otherwise → `done: false` with the raw text.
4. On `done: true`, `FitnessChat` calls `onResult(...)` → `GoalForm.handleAssessmentResult()`.

**Manual path (fully client-side, no network):**
- `GoalForm` computes `assessRace(raceDist, raceTime)` / `assessVdot(vdotInput)` from `vdot.js` on every render → live `{ vdot, level }` preview. "Use this" → `confirmManual()` → `handleAssessmentResult()`.

**Both paths converge** on `handleAssessmentResult(level, vdot, weeklyKm, longestRunKm, reasoning)`, which: `set('fitnessLevel', level)`, stores `assessmentData` in local state, flips to the result card. **`vdot` / `weeklyKm` / `longestRunKm` live only in React state — they are NOT part of the `POST /goal` body.** Only `fitnessLevel` reaches the backend. Nothing from the chat is persisted.

**Reaching a generated plan (history → plan view):** `GoalHistory` fetches `GET /goals`. Each row's action button links to `/goals/:goalId` (`PlanView`), which polls `GET /goal/:goalId/plan` every 3 s while `generating`. The button label depends on `planStatus`: `ready` → "View Plan", `generating` → "Track", `failed` → no button (Delete only). The status badge itself is now a plain indicator, no longer a link.

---

## 3. Specific Tech Choices & Compromises

- **VDOT is computed two different ways.** The manual path uses the real Daniels–Gilbert formula in `vdot.js` (deterministic, instant, offline). The chat path relies on Claude estimating VDOT, guided by a reference table baked into `_SYSTEM_PROMPT`. **These must stay in sync:** the prompt table was corrected to match the formula (e.g. 10K 52:00 is VDOT ≈ 38, not the 43 originally hardcoded). If you change thresholds in `levelFromVdot()`, change them in the prompt too.
- **The abstract beginner/intermediate/advanced `<select>` was removed entirely** — this diverges from the original `plan.md`, which kept the dropdown with a "Not sure?" helper beside it. The later idea-refine iteration (Directions 1 + 4) made the label an output, not an input. `form.fitnessLevel` still exists in form state and is what's submitted; it's just never set via a visible dropdown in the default view.
- **Classification is parsed from a fenced JSON block, not tool use.** The endpoint uses a plain `generate(messages)` call (no tools/`response_format`) and regex-extracts the block. Chosen because it's a lightweight conversational turn, not structured plan generation.
- **Co-located change on this branch:** `app/agent/validation.py` bounds were tightened to `full_marathon: 3:59:00` and `half_marathon: 1:44:00` (was 4:00:00 / 1:45:00). Not part of the fitness feature, but shipped on the same branch — see `specs/mission.md` and Phase 1 spec updates.

---

## 4. Known Edge Cases / Gotchas

- **Never wrap the chat input in a `<form>`.** `FitnessChat` renders inside GoalForm's `<form>`. Nested forms are invalid HTML — the browser collapses them and the inner "Send" submits the *outer* goal form (this was the "form resets on answer" bug). The input row is a `<div>`; Send is `type="button"` with `onClick`, and Enter is handled via `onKeyDown`.
- **The mount fetch is guarded by `startedRef`.** React StrictMode double-invokes mount effects in dev; without the guard you get two opening questions and two POSTs. Don't remove it.
- **Every non-submit button in `GoalForm` must be `type="button"`** (days-picker, seg-toggle, Start Assessment, Back, Use this, Reassess). A bare `<button>` inside the form defaults to `type="submit"` and will fire `handleSubmit`.
- **The global `button:hover` rule (`App.css:112`, `background: #0b5ed7`) has specificity `(0,2,1)` and clobbers plain class-based hovers.** A link-styled button must use a selector that outranks it — `button.link-subtle:hover` (not `.link-subtle:hover`, which is only `(0,2,0)` and loses, producing an ugly blue box on the Reassess/Back/manual-toggle links). Any new "text link that's really a `<button>`" needs the same `button.<class>` treatment.
- **A 422 from `/fitness-chat` is not gracefully handled in the UI.** If Claude emits a syntactically valid JSON block with an invalid `fitness_level`, the endpoint returns 422 (FastAPI `{detail: ...}` shape). `FitnessChat.sendTurn` blindly reads `data.message`, so the user sees an empty assistant bubble. Rare in practice (the prompt constrains the value), but don't assume the frontend surfaces this error.
- **Raw signals are display-only.** Passing `vdot`/`weeklyKm`/`longestRunKm` to the plan generator is explicitly Phase 1.2. Adding them to the `POST /goal` body requires changing the `GoalRequest` model first — don't do it silently.
- **`parseTimeToSeconds` accepts `MM:SS` and `H:MM:SS`.** The distance's expected format is only a placeholder hint (`RACE_DISTANCES[key].timeHint`); the parser itself doesn't enforce which format goes with which distance. A `5K` entered as `1:55:00` will parse and produce a (nonsensical) VDOT.
