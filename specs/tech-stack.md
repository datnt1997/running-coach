# Tech Stack

## Language & Runtime

- **Python 3.12+** — primary language for backend and agent logic.

## API Layer

- **FastAPI** — HTTP endpoints for goal intake, plan retrieval, and webhook callbacks.
- **Pydantic v2** — request/response validation and structured output contracts.

## AI Model

- **Claude Sonnet 4.6** (`claude-sonnet-4-6`) via Anthropic SDK — primary analysis and plan generation engine.
  - Chosen for: strongest running/physiology domain knowledge among tested models, reliable JSON-schema structured output, full tool-use/function-calling support for Strava API calls.
  - Fallback consideration: local DeepSeek R1 (via Ollama) for privacy-sensitive analysis if user opts in.

## AI Client Abstraction

All model calls go through a single `AIClient` interface (`ai/client.py`) so the provider can be swapped via config without touching call sites.

```
AIClient (abstract)
├── AnthropicClient   — wraps anthropic SDK, translates to/from Anthropic tool-use format
└── GeminiClient      — wraps google-generativeai SDK, translates to/from Gemini function-calling format
```

- Selected via env var: `AI_PROVIDER=anthropic` (default) or `AI_PROVIDER=gemini`.
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
- Environment variables: `ANTHROPIC_API_KEY`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `DATABASE_URL`.

## Model Selection Rationale

| Candidate | Decision | Reason |
|---|---|---|
| Claude Sonnet 4.6 | **Selected** | Best sports-physiology knowledge + JSON reliability + tool use |
| Claude Opus 4.8 | Skip for v1 | 2× cost, marginal gain for weekly batch analysis |
| Gemini 2.5 Flash | Backup | 10× cheaper but weaker sports domain knowledge |
| Llama 3.3 70B | Skip | ~24% sports knowledge degradation; risky for zone/periodization logic |
| DeepSeek R1 (local) | Optional | Privacy mode only; explicit reasoning traces useful for explainability |
