# SDD Task Template

> **Split triggers** — create a new task if any of these are true:
> - Acceptance criteria > 6
> - Estimated time > 3 hours
> - Files touched > 3
> - More than one seam is covered

---

## Task: [ID] — [one-line title]

**Spec section**: [Link or section reference — e.g. `rollup-spec.md §4`]
**Complexity**: [Low / Medium / High]
**Parallel** `[P]`: [Yes — can run concurrently with [IDs] / No]
**Depends on**: [Task IDs that must be complete first, or "none"]
**Estimated time**: [≤ 3 hours — if more, split the task]

---

### 1. The goal is clear

> As a **[role]**, I want **[outcome]** so that **[benefit/reason]**.

- **Role**: [who benefits — e.g. "status-records viewer", "view config author", "generic runtime"]
- **Outcome**: [what they get — describe the observable result, not the implementation]
- **Benefit**: [why it matters — the reason this task needs to exist]

---

### 2. The scope is bounded

**In scope:**
- [Concrete thing 1 this task does]
- [Concrete thing 2 this task does]

**Non-goals (explicitly deferred):**
- [Thing that seems related but belongs in a later task]
- [Thing an implementor might add but must not — e.g. "do not mirror operator matrix in the backend"]

---

### 3. What is the expected behavior

Use **Given / When / Then** per scenario. Write at least one negative scenario (an outcome that must be absent or rejected).

> **Given** = precondition / system state before the action
> **When** = the trigger or action being tested
> **Then** = the observable outcome — measurable, not prose

**Scenario: [Happy path name]**
- Given: [system state — e.g. columns with operator SUM, filtered values [10, 20, null]]
- When: [action — e.g. computeRollups(specs, filterContext) is called]
- Then: [outcome — e.g. returns `{ qty: 30 }` (null excluded, cast via ::numeric)]

**Scenario: [Edge case name]**
- Given: [state]
- When: [action]
- Then: [outcome]

**Scenario: [Negative case — must have at least one]**
- Given: [e.g. qty column is masked for caller's role]
- When: [same action]
- Then: [e.g. `{}` is returned — key `qty` is absent, not `null` or `0`]

---

### 4. Invariants

Rules that must hold across **all** scenarios regardless of implementation path. Each invariant maps directly to a **property-based test** or assertion.

> Objective language only — no "should", "correctly", "properly". Every item must be pass/fail verifiable.

- [ ] [Positive invariant — e.g. "COUNT('') = 1; an empty string is non-NULL and is always counted"]
- [ ] [Negative invariant — e.g. "A masked column produces no key in the rollups map — not even null or 0"]
- [ ] [Boundary invariant — e.g. "A partial rollup object with no operator is never persisted"]

> If you cannot write a property test for an invariant, it is underspecified — rewrite it.

---

### 5. Acceptance criteria

**Max 6 items.** More than 6 = split the task. Objective/measurable only — no subjective language.

**Automated (must have a passing test before done):**
- [ ] [Specific assertion — e.g. `expect(result.qty).toBe(30)` for SUM over filtered set]
- [ ] [Negative assertion — e.g. `expect(result).not.toHaveProperty('maskedField')`]
- [ ] [Type check — `tsc --noEmit` passes (portal) or `npm run build` passes (services)]

**Release evidence (staging/manual — only if not automatable):**
- [ ] [Exact steps + what to observe — e.g. "Set Qty→SUM, save, open ungrouped list → footer total matches manual sum of visible records"]

> All Given/When/Then scenarios in §3 must map to at least one item here. If a scenario has no acceptance criterion, it will not be tested.

---

### Files (≤ 3)

| File | What changes |
|------|-------------|
| `path/to/file.ts` | [one-line description of the seam] |
| `path/to/file.spec.ts` | [covers §3 scenarios and §4 invariants] |

> More than 3 files = split the task.

---

## Definition of done

- [ ] All §3 scenarios have a passing test
- [ ] All §4 invariants have a passing property test or assertion
- [ ] All §5 automated criteria are green
- [ ] Release evidence step completed (if applicable)
- [ ] `tsc --noEmit` / `npm run build` passes
- [ ] No `builderType` conditional introduced in generic code
- [ ] Files touched ≤ 3

