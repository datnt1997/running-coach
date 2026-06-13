# Roadmap

Each phase ships a thin vertical slice — end-to-end working functionality — before expanding.

---

## Phase 1 — Goal Intake + Static Plan Generation

**Deliverable:** User answers a few questions; agent returns a structured weekly training plan as JSON and human-readable text.

- Conversational intake: goal (race distance + finish-time target + date), current fitness level, days available per week, any injury history.
- Validate goal against supported bounds: HM no faster than sub 1:45:00 (~4:58/km), FM no faster than sub 4:00:00 (~5:41/km). Reject or warn if out of scope.
- Claude Sonnet 4.6 generates a periodized plan (base → build → peak → taper) using sports-science principles.
- Plan stored in PostgreSQL (user profile + weekly schedule).
- FastAPI endpoint: `POST /goal`, `GET /plan`.
- No Strava yet — plan based purely on user-declared inputs.

---

## Phase 2 — Strava Sync + Real Data Analysis

**Deliverable:** Agent reads the user's actual runs from Strava and annotates the plan with real vs. prescribed performance.

- Strava OAuth 2.0 flow (`GET /strava/connect`, callback handler).
- Webhook or polling sync: pull recent activities after each run.
- Claude analyzes each activity against the planned workout using the three core signals: **pace** (zone adherence), **heart rate** (effort level vs. prescription), and **load** (volume × intensity).
- Weekly summary stored and surfaced to user: "You ran your tempo 12s/km too fast — HR zone 4 vs. prescribed zone 3."
- FastAPI endpoints: `GET /activities`, `GET /weekly-summary`.

---

## Phase 3 — Adaptive Re-Planning

**Deliverable:** Agent automatically adjusts the upcoming week's plan based on actual training load and performance trend.

- Compute Training Stress Score (TSS), Acute Training Load (ATL), Chronic Training Load (CTL), and Form (TSB) from Strava data.
- Claude re-generates the next week when: missed workouts, injury signal (HR spike + pace drop), or outperformance trend.
- Diff shown to user: what changed and why.
- pgvector used to retrieve comparable weeks from training history for context.
- FastAPI endpoint: `POST /replan`.

---

## Phase 4 — Conversational Check-ins + Memory

**Deliverable:** User can chat with the coach in natural language; agent remembers preferences, history, and emotional state.

- Chat endpoint: `POST /chat` — user can ask "why is this week easier?", "I felt terrible on Tuesday", "can we move long run to Sunday?".
- Agent has access to full training history (pgvector semantic search) and current plan.
- Preference memory: user-stated preferences (prefers morning runs, avoids hills) stored and injected into future plan prompts.
- Handles plan modifications requested in natural language.

---

## Phase 5 — Polish & Reliability

**Deliverable:** Production-ready reliability, observability, and a minimal UI.

- Structured logging + error handling for Strava API failures and model timeouts.
- Rate limiting on Anthropic API calls.
- Simple web UI (or CLI) for non-API users.
- Automated weekly re-plan trigger (cron or Strava webhook).
