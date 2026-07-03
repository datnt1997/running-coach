# Phase 1.1 — Fitness Assessment Chat Widget: Requirements

## Scope

### In scope

| Area | Detail |
|---|---|
| Backend endpoint | `POST /fitness-chat` — stateless; accepts conversation history + latest message; returns Claude's next question or a VDOT-based classification |
| Three chat signals | Recent race time + distance (5K / 10K / HM / FM), weekly running km, longest single run in last 3 months |
| Manual entry | `frontend/src/lib/vdot.js` (Daniels–Gilbert formula) + a two-mode card: **Race Time** (distance + time → VDOT, computed in-browser) or **VDOT** (entered directly), with a live preview |
| VDOT classification | VDOT score → fitness level: VDOT < 35 = beginner, 35–50 = intermediate, > 50 = advanced. Chat and manual paths use identical thresholds |
| Frontend component | `FitnessChat.jsx` — inline chat widget opened by "Start Assessment" |
| GoalForm integration | Three UI states — assessment card (Start Assessment + manual entry) → chat/manual → result card (level badge, VDOT pill, reasoning, Reassess). Abstract level dropdown removed from default view |
| Tone | Claude's messages must feel warm and coach-like |

### Out of scope

- Replacing the entire goal form with chat (Phase 4)
- Persisting chat history or raw signals to the database
- Passing `vdot` / `weeklyKm` / `longestRunKm` to the plan generator — Phase 1.1 only improves the accuracy of `fitnessLevel`; passing raw signals through GoalRequest is Phase 1.2
- Any change to the `GoalRequest` model or existing `/goal` endpoint
- Streaming responses
- "Years running consistently" as a signal — VDOT from race time is more objective and sufficient

---

## API Contract

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
`history` is `[]` and `message` is `""` on the first call (triggers opening question).

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
  "message": "Based on your 52-min 10K (VDOT 43) and 40 km weekly base, you're solidly intermediate — a great foundation for structured marathon training.",
  "reasoning": "VDOT 43 from 10K 52:00; 40 km/week; longest run 18 km → intermediate"
}
```

`fitnessLevel` ∈ `"beginner"` | `"intermediate"` | `"advanced"`.
`vdot` is a rounded integer.

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Classification method | VDOT (Daniels–Gilbert) | Industry gold standard; objective, unambiguous, derived from actual performance not self-assessment |
| Three entry paths | Chat, Race Time (PR), or direct VDOT | Chat for "I don't know my numbers"; PR/VDOT for runners who do — no forced conversation |
| Manual VDOT computed in-browser | `vdot.js` runs the Daniels–Gilbert formula client-side | Deterministic and instant; no AI call, no network round-trip for the manual path |
| Accurate reference table | Backend prompt table corrected to real Daniels–Gilbert values | Earlier approximate table (10K 52:00 → 43) was wrong (real value ≈ 38); chat and manual paths must agree |
| Fitness level thresholds | VDOT < 35 = beginner, 35–50 = intermediate, > 50 = advanced | Maps roughly to recreational / club / competitive recreational runners |
| Signals collected (chat) | Race time + distance, weekly km, longest run (3 signals) | Minimum set a real coach needs; "years running" dropped — VDOT captures fitness better than experience |
| Abstract dropdown removed | No beginner/intermediate/advanced select in the default view | The abstract label being unhelpful is the entire reason for this feature |
| GoalRequest unchanged | Phase 1.1 only pre-fills the existing `fitnessLevel` field | Keeps scope tight; raw signals flow through in Phase 1.2 |
| Widget placement | Inline below dropdown, slides open/closed | Form context stays visible; runner can still edit the select after pre-fill |
| Question generation | Claude-driven dynamic follow-ups | Collects signals in any order; skips ones already answered |
| Max turns | ≤ 5 | Enough for 3 signals + a follow-up; respects runner's time |
| Tone | Warm, coach-like | Matches product mission |
| State | Stateless (no DB) | History sent back with each request |
| CSS | Plain, match existing `App.css` | No new packages |

---

## Context

- **Stack:** FastAPI + Pydantic v2; React 18 + Vite, plain CSS. No new dependencies without approval.
- **AI:** Use `AIClient` abstraction via `get_ai_client_dep()`. Never call Anthropic/Gemini SDK directly.
- **VDOT reference** (accurate Daniels–Gilbert, matches `vdot.js` and the system prompt): 5K 35:00 → 26, 5K 25:00 → 38, 5K 20:00 → 50; 10K 60:00 → 32, 10K 52:00 → 38, 10K 45:00 → 45, 10K 40:00 → 52; HM 2:00 → 36, HM 1:45 → 43, HM 1:30 → 51; FM 4:30 → 33, FM 4:00 → 38, FM 3:30 → 45.
- **Patterns to follow:** Route structure from `app/api/goals.py`; component style from `GoalForm.jsx`; fake client pattern from `tests/conftest.py`.
- **Tone rule:** System prompt must open with "You are a warm, encouraging running coach…". Avoid clinical or robotic phrasing.
