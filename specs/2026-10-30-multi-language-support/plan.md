# Plan: Multi-language support

Vertical slices, shippable one at a time. Run the frontend build and `pytest` (see warning below) after each.

- [ ] **1. Backend language registry + prompt helper**
  - `app/i18n.py`: `LANGUAGES = {"vi": "Vietnamese (tiếng Việt)"}`, `get_language()` from `APP_LANGUAGE`, `language_instruction()`.
  - Startup validation in `app/config.py`.
  - Verify: unit tests (default `vi`, unknown code raises).

- [ ] **2. Apply the helper to all AI prompts**
  - Replace the hardcoded "Vietnamese" lines in `fitness_chat.py` and `prompt.py`; add it to analysis rationale and weekly summary prompts.
  - Move `_FIRST_CALL_STARTER` per language.
  - Verify: prompt tests assert the instruction is present in each message list; fake-client tests still pass.

- [ ] **3. Persist plan language**
  - Migration `004_plan_language.sql`; write on plan create; return `language` in plan responses.
  - Ask first: confirm schema change.
  - Verify: endpoint test; migration applies on a fresh test DB.

- [ ] **4. Frontend i18n core**
  - `frontend/src/i18n/index.js` (`t`, `DEFAULT_LANG`), `vi.js` dictionary; `labels.js` becomes dictionary lookups; language from `/config` or env.
  - Verify: `npm run build`; a small script/test that every `t('key')` used exists in `vi.js`.

- [ ] **5. Migrate pages one by one**
  - `FitnessChat`, `GoalForm`, `GoalHistory`, `PlanView`, `Dashboard`, `App`. One commit per page.
  - Verify: grep shows no Vietnamese literals in `.jsx`; manual page check.

- [ ] **6. Prove it: add `en` dictionary (follow-up, optional)**
  - Copy `vi.js` → `en.js`, register `en`, set `APP_LANGUAGE=en`, confirm UI and AI replies switch.

## Risks

- Prompt drift: other prompt text is English, so the model may ignore the instruction on some calls. Mitigation: put the instruction last and test on the real API.
- Missing keys render as raw key names. Mitigation: dev-mode console warning plus the key-existence check.
- Stored plans in an old language mixed with a new setting. Mitigation: `language` column on plans (task 3).

## WARNING: tests wipe the dev database

`pytest` currently drops all tables in the database named by `DATABASE_URL` in `.env` (happened on 2026-10-30). Do not run `pytest` for these tasks until the tests use a separate `TEST_DATABASE_URL` (separate fix, recommended first).
