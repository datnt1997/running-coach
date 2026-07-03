---
name: implementation-doc
description: Writes IMPLEMENTATION.md documenting the AS-BUILT reality of a phase after it ships — the exact files, data flow, tech choices/compromises, and gotchas the next developer or AI needs. Trigger after finishing a phase's implementation, or when the user says "document the implementation", "write IMPLEMENTATION.md", "implementation doc", or invokes /implementation-doc.
---

# Implementation Doc

Write an `IMPLEMENTATION.md` that captures how a phase was **actually built**, not how it was planned. The spec files (`requirements.md`, `plan.md`, `validation.md`) describe intent; this document describes reality — the map a future developer or AI needs to safely change the code without re-reading every file.

Invoke this **after** a phase's implementation is complete (tests passing), typically right before merge.

## Workflow

### 1. Identify the phase

Determine which phase was just implemented:
- Default to the most recently modified `specs/YYYY-MM-DD-<feature-name>/` directory.
- If ambiguous, ask the user which phase to document.

The file is written to that spec directory: `specs/YYYY-MM-DD-<feature-name>/IMPLEMENTATION.md`.

### 2. Ground the doc in the ACTUAL code

Do not write from memory or from the spec's intentions. Inspect what was really built:
- `git diff main...HEAD --stat` (or the branch's diff) to see every file the phase touched.
- Read the key files that changed — trace the real data flow, not the planned one.
- Note anything that diverged from `plan.md` (the plan is intent; the code is truth).

### 3. Write `IMPLEMENTATION.md`

The document MUST contain these four sections. Keep each one concrete and specific — reference real file paths, function names, and env vars.

#### 1. Architecture Map
A quick list of the exact files that drive this feature and what each one owns.
> Example: "Endpoint in `app/api/fitness_chat.py`; VDOT math in `frontend/src/lib/vdot.js`; UI states in `frontend/src/pages/GoalForm.jsx`; chat widget in `frontend/src/components/FitnessChat.jsx`."

#### 2. Data Flow & Dependencies
How data moves through the feature end to end — where state lives, what calls what, what is or isn't persisted.
> Example: "Chat is stateless — full history is POSTed back each turn; nothing is written to the DB. Classification is parsed from a fenced JSON block in Claude's reply. Raw VDOT/km signals live only in React state and are NOT submitted with the goal form."

#### 3. Specific Tech Choices & Compromises
Why it was built this way — the non-obvious decisions and trade-offs, including anything that diverged from the plan.
> Example: "VDOT is computed in-browser via the Daniels–Gilbert formula (deterministic, no AI call) for the manual path; the chat path relies on Claude estimating from a reference table. The two must stay in sync — the prompt table was corrected to match the formula."

#### 4. Known Edge Cases / Gotchas
Things the next developer or AI should NOT touch, or that will break in non-obvious ways.
> Example: "Do not wrap the chat input in a `<form>` — it renders inside GoalForm's form and nested forms collapse, submitting the outer form. The mount effect is guarded with a ref because React StrictMode double-invokes it."

### 4. Confirm

Show the user the path written and a one-line summary of each section. Do not commit or merge unless asked.

## Constraints

- Document **as-built reality**, never planned intent — if the code diverged from `plan.md`, describe the code and note the divergence.
- Every claim must be verifiable against a real file, function, or env var. No hand-waving.
- Keep it tight — this is a map for the next person, not a tutorial. Prefer specifics over prose.
- One `IMPLEMENTATION.md` per phase, living in that phase's spec directory.
