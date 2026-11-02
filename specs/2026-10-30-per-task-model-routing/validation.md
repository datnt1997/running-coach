# Validation: Per-task model routing

## Automated (no API key needed)

```bash
pytest
```

- `validate_config` raises for a missing `GEMINI_API_KEY` only when a Gemini provider is selected.
- Chat dependency returns the Gemini client when `CHAT_AI_PROVIDER=gemini`, and the `AI_PROVIDER` client when unset.
- Unknown provider value raises `ValueError`.
- Fitness chat endpoint tests pass using the fake client override.
- With no new env vars set, behavior matches `main` (all Anthropic).

## Manual eval against the real Gemini API

Run ~10 scripted chat conversations (mix of beginner, intermediate, advanced, "no race time") with `CHAT_AI_PROVIDER=gemini`.

| Check | Pass condition |
|---|---|
| Language | Every assistant message is Vietnamese |
| JSON block | Final turn contains a ```json block that the parser accepts (`fitness_level` in beginner/intermediate/advanced, VDOT 20–80) in 10/10 runs |
| Classification | Level matches the expected VDOT band for the scripted inputs |
| One question at a time | No multi-question dumps in the transcript |
| Cost | Tokens per full conversation recorded from `AIResponse.usage`; priced at the vendor's current page and compared with Haiku 5.5 |

## Decision rule

- Gemini passes all checks and costs less than Haiku 5.5: keep Gemini for chat.
- JSON block fails in more than 1 of 10 runs, or Vietnamese is poor: switch `CHAT_AI_PROVIDER=anthropic` and use Haiku 5.5 for the chat instead.
