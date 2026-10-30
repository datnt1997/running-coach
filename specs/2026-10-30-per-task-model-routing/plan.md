# Plan: Per-task model routing

Small vertical slices; run `pytest` after each.

## Tasks

- [ ] **1. Config**: add `CHAT_AI_PROVIDER` to `app/config.py`; make `validate_config()` check the key for each selected provider.
  - Files: `app/config.py`
  - Verify: new unit tests for `validate_config` (anthropic only, gemini chat only, both, missing key).

- [ ] **2. Factory**: refactor `get_ai_client()` to take a provider name; add `get_chat_ai_client()` and `get_chat_ai_client_dep()`.
  - Files: `app/ai/factory.py`
  - Verify: tests that the chat dependency honors `CHAT_AI_PROVIDER`, falls back to `AI_PROVIDER`, and raises on unknown values.

- [ ] **3. Wire the chat endpoint**: switch `fitness_chat.py` to `get_chat_ai_client_dep`; update `tests/test_fitness_chat.py` (and `conftest.py` if needed) to override the new dependency.
  - Files: `app/api/fitness_chat.py`, `tests/test_fitness_chat.py`, `tests/conftest.py`
  - Verify: `pytest tests/test_fitness_chat.py` passes; other endpoint tests still override `get_ai_client_dep`.

- [ ] **4. Gemini model env**: `GeminiClient` default model from `GEMINI_MODEL`.
  - Files: `app/ai/gemini_client.py`
  - Verify: test with `monkeypatch.setenv`.

- [ ] **5. Docs/env**: update `.env.example` and `CLAUDE.md` env table.
  - Files: `.env.example`, `CLAUDE.md`

- [ ] **6. Manual check**: `pip install -e ".[gemini]"`, set `CHAT_AI_PROVIDER=gemini` and `GEMINI_API_KEY`, run the chat against the real API (see `validation.md`).

## Risks

- Gemini may drop or reformat the trailing ```json block. Mitigation: eval in `validation.md`; fall back to Haiku 5.5 on the same factory with no new adapter.
- `google-generativeai` may be deprecated. Mitigation: separate migration task, not blocking.
- Gemini Flash pricing changes (a rise is reported for 2027-01-01). Mitigation: cost check is part of validation.
