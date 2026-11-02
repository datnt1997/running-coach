# Requirements: Multi-language support

Source: `specs/mission.md` Success Definition: "The app supports multiple languages. The MVP ships in Vietnamese; English can be added later without redesigning the app."

## Objective

Make language a setting instead of hardcoded text. Ship Vietnamese (`vi`) as the only enabled language now. Adding English (`en`) later should mean adding one frontend dictionary and registering the language code, with no code changes in pages, prompts or endpoints.

## Where language is hardcoded today

| Layer | Where | Today |
|---|---|---|
| Frontend UI strings | `GoalForm`, `GoalHistory`, `PlanView`, `Dashboard`, `FitnessChat`, `App.jsx` (~100 lines) | Vietnamese literals inline |
| Display labels | `frontend/src/lib/labels.js` | Vietnamese day / type / phase maps |
| `<html lang>` | `frontend/index.html` | `vi` (`app/api/ui.py` legacy page: `en`) |
| Chat prompt + starter | `app/api/fitness_chat.py` | "Reply in Vietnamese" line and a Vietnamese `_FIRST_CALL_STARTER` |
| Plan prompt | `app/agent/prompt.py` `SYSTEM_PROMPT` | "Write summary and notes in Vietnamese" line |
| Analysis rationale, weekly summary | `app/agent/prompt.py` | English, unspecified |
| Backend error text | `goals.py`, `validation.py` | English |

## Assumptions (correct me before implementation)

1. Single-user app, so language is one app-level setting, not per-account.
2. The API keeps stable English identifiers (`Mon`, `easy`, `base`, `beginner`, JSON keys). Only display text is localized.
3. Language is fixed per plan: a plan generated in Vietnamese stays Vietnamese. Switching language later does not re-translate old plans.
4. No new frontend dependency: a small dictionary + `t(key)` helper, not `react-i18next`. Revisit if plural/format needs grow.
5. Dates, numbers and units (km) stay as they are; locale formatting is out of scope.

## In scope

- Frontend `t(key, params)` helper with `vi` dictionary and `DEFAULT_LANG = 'vi'`; all page strings and `labels.js` move into the dictionary.
- Backend `LANGUAGES` registry (`vi` now) and one helper that adds a "write all user-facing text in <language>" instruction to every AI prompt: chat, plan, analysis rationale, weekly summary.
- A single `APP_LANGUAGE` env var (default `vi`) read by the backend and exposed to the frontend (via `GET /config` or the `<html lang>` served by FastAPI).
- Persist the language used on each plan (`language` column on `training_plans`, new migration) so stored content is labeled.
- Make the chat opening message and error messages language-aware.

## Out of scope

- Adding the English dictionary itself (follow-up task; this spec only proves it is cheap).
- Per-user language switcher UI.
- Translating existing stored plans.
- Locale-specific date / number formatting, right-to-left languages.

## Requirements

1. No Vietnamese literal remains in a `.jsx` file; all visible text comes from the dictionary.
2. Every AI call that produces user-visible text receives the language instruction from one shared helper.
3. Changing `APP_LANGUAGE` to an unregistered code fails fast at startup with a clear error.
4. Adding a language = add `frontend/src/i18n/<code>.js`, add the code to the backend registry. Nothing else.
5. Default behaviour with no env var set is identical to today (Vietnamese).

## Boundaries

- Always: keep API enums and the chat JSON block (`fitness_level` etc.) in English.
- Ask first: adding an i18n library, DB schema changes beyond the one `language` column.
- Never: translate values the code branches on (`rest`, `base`, `beginner`, ...).
