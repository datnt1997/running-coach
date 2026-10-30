# Requirements: Per-task model routing (Sonnet for plans, Gemini for chat)

## Objective

Plan generation, activity analysis and weekly summaries stay on Claude Sonnet. The fitness assessment chat (`POST /fitness-chat`) moves to Gemini Flash to cut cost, and keeps replying in Vietnamese. Context: `specs/tech-stack.md` (updated 2026-10-30).

## Assumptions (correct me before implementation)

1. Only the fitness chat changes provider. Plans, analysis and summaries stay on Anthropic.
2. The provider for the chat is chosen by a new env var `CHAT_AI_PROVIDER`; when unset it falls back to `AI_PROVIDER`, so existing setups behave exactly as today.
3. We keep the current `google-generativeai` SDK for now. Migrating to `google-genai` is a separate task.
4. The exact Gemini model is not decided. It is set by a `GEMINI_MODEL` env var, with `gemini-2.0-flash` as the code default until the eval picks one.
5. Vietnamese replies and the trailing JSON block are already in `app/api/fitness_chat.py` (done earlier in this branch).

## In scope

- `CHAT_AI_PROVIDER` config and a chat-specific client dependency.
- `GEMINI_API_KEY` validation at startup, only when a Gemini provider is actually selected.
- `GEMINI_MODEL` env override.
- `.env.example` entries.
- Tests for routing and validation.

## Out of scope

- Moving to `google-genai`.
- Forcing function calling in `GeminiClient` (the chat uses plain text, no tools). Required only if Gemini is later used for plans or analysis.
- Provider routing for plans, analysis or summaries.
- Changing the `AIClient` interface.

## Requirements

1. `get_chat_ai_client_dep()` in `app/ai/factory.py` returns the client for `CHAT_AI_PROVIDER`, falling back to `AI_PROVIDER`. Unknown values raise `ValueError`.
2. `app/api/fitness_chat.py` uses `get_chat_ai_client_dep`; no other endpoint changes.
3. `validate_config()` requires `ANTHROPIC_API_KEY` if any selected provider is `anthropic`, and `GEMINI_API_KEY` if any selected provider is `gemini`.
4. `GeminiClient` reads its model from `GEMINI_MODEL` when set.
5. `.env.example` documents `CHAT_AI_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`.
6. Default behavior with none of the new vars set is unchanged.

## Boundaries

- Always: keep tests runnable without any API key (fakes via `dependency_overrides`).
- Ask first: new dependencies, SDK migration, DB changes.
- Never: commit real keys; change JSON-block keys/values in the chat prompt (parser depends on them).
