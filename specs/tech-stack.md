# Tech Stack

## Language & Runtime

- **Python 3.12+** — primary language for backend and agent logic.

## API Layer

- **FastAPI** — HTTP endpoints for goal intake, plan retrieval, and webhook callbacks.
- **Pydantic v2** — request/response validation and structured output contracts.

## AI Model

Models are chosen per task, not per app:

| Task | Provider / model |
|---|---|
| Plan generation, activity analysis, weekly summary | **Claude Sonnet** via Anthropic SDK (currently `claude-sonnet-4-6`; evaluate Sonnet 5.5) |
| Fitness assessment chat (`/fitness-chat`) | **Gemini Flash** via Google SDK (exact model TBD by eval; replies in Vietnamese) |

- Sonnet chosen for: reliable JSON-schema structured output, forced tool-use, and periodization logic where plan quality matters. Plan generation is rare, so per-call cost is small.
- Gemini Flash chosen for chat: low cost for a multi-turn conversation, and Vietnamese reply quality (to be verified).
- Fallback consideration: local DeepSeek R1 (via Ollama) for privacy-sensitive analysis if user opts in.

## AI Client Abstraction

All model calls go through a single `AIClient` interface (`ai/client.py`) so the provider can be swapped via config without touching call sites.

```
AIClient (abstract)
├── AnthropicClient   — wraps anthropic SDK, translates to/from Anthropic tool-use format
└── GeminiClient      — wraps google-generativeai SDK, translates to/from Gemini function-calling format
```

- Selected via env var: `AI_PROVIDER=anthropic` (default) or `AI_PROVIDER=gemini`, with a per-task override for the fitness chat (e.g. `CHAT_AI_PROVIDER=gemini`).
- The interface exposes: `generate(messages, tools=None, response_format=None) → AIResponse`.
- Tool definitions are stored in provider-agnostic format inside `ai/tools.py`; each client adapter translates them to its provider's schema at call time.
- `AIResponse` is a provider-neutral dataclass: `{content: str, tool_calls: list[ToolCall], usage: TokenUsage}`.

**Why:** Anthropic and Gemini use different tool/function-calling schema formats. Abstracting at this layer means a provider switch is a one-line env change, not a codebase-wide refactor.

## Agent Orchestration

- **Anthropic tool use (function calling)** — native, no orchestration framework needed for v1.
- Tools defined: `get_strava_activities`, `get_training_load`, `generate_plan`, `update_plan_week`.

## Data & Memory

- **PostgreSQL** — primary store for user profile, goals, and weekly plans.
- **pgvector** — embedding store for training history summaries enabling semantic retrieval ("how did the user handle high-mileage weeks before?").

## External Integrations

- **Strava API (OAuth 2.0)** — source of ground-truth running activity data (pace, heart rate, cadence, elevation, distance).

## Configuration & Secrets

- **python-dotenv** — local `.env` for API keys and DB URL.
- Environment variables: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` (required when the chat uses Gemini), `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `DATABASE_URL`.

## Model Selection Rationale

| Candidate | Decision | Reason |
|---|---|---|
| Claude Sonnet | **Selected** for plans, analysis, summaries | JSON reliability + forced tool use; rare calls so cost is small (~$0.09/plan at list price, unverified) |
| Claude Opus | Skip for v1 | Higher cost, marginal gain for weekly batch analysis |
| Gemini Flash | **Selected** for fitness chat | Cheap multi-turn chat; verify Vietnamese quality and JSON-block reliability in eval |
| Claude Haiku 5.5 | Alternative for chat/analysis | Cheaper than Gemini Flash at list price and no new adapter; revisit if the Gemini eval is weak |
| Llama 3.3 70B | Skip | ~24% sports knowledge degradation; risky for zone/periodization logic |
| DeepSeek R1 (local) | Optional | Privacy mode only; explicit reasoning traces useful for explainability |
