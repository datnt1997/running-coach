# Validation: Multi-language support

## Automated

- `app.i18n`: default `vi`; unknown `APP_LANGUAGE` fails startup.
- Each prompt builder (chat, plan, analysis, weekly summary) includes the language instruction.
- Plan creation stores `language`; plan responses return it.
- Frontend: `npm run build` passes; every key used by `t()` exists in `vi.js`.
- `grep -rnP "[ăâêôơưđ]" frontend/src --include=*.jsx` returns nothing (all Vietnamese lives in the dictionary).

## Manual (real API)

1. `APP_LANGUAGE=vi`: chat greeting, chat replies, new plan summary and notes, analysis rationale and weekly summary are all Vietnamese; JSON block still parses.
2. Day / type / phase labels show Vietnamese; enums in API responses remain English.

## Extensibility proof (task 6)

Add `en.js` and set `APP_LANGUAGE=en` with no other code change. UI, chat, new plan and summaries switch to English. If anything else needed editing, the design failed the "without redesigning" test; list those spots and fix them.
