---
name: changelog
description: Update CHANGELOG.md in the project root with the work done since the last entry, grouped under date headings. Invoke this manually before merging a branch. If no CHANGELOG.md exists, bootstrap it from git history.
---

# Changelog

Maintain a `CHANGELOG.md` in the project root. Entries are grouped under `##` date
headings (`YYYY-MM-DD`, newest first), with one bullet per notable change.

This skill is invoked manually, typically right before merging a branch.

## Steps

1. **Check for `CHANGELOG.md`** in the project root.

2. **If it does not exist — bootstrap it from git history:**
   - Run `git log --pretty=format:'%ad%x09%s' --date=short` to list every commit
     with its date and subject.
   - Group commits by date (newest date first). Under each `## YYYY-MM-DD`
     heading, write one bullet per commit, rewritten as a concise,
     human-readable change (drop `feat:`/`fix:` prefixes; describe the change,
     not the commit ceremony). Merge trivial/duplicate commits into one bullet.
   - Write the file with the header shown in [Format](#format).

3. **If it exists — add the work done since the last entry:**
   - Determine today's date with `date +%F`.
   - Find what changed since the changelog was last updated. Look at, in order:
     - commits not yet reflected: `git log --pretty=format:'%ad%x09%s' --date=short`
       and compare against bullets already in the file;
     - uncommitted work: `git status --short` and `git diff --stat` (plus
       `git diff` for specifics) so in-progress changes about to be merged are captured.
   - Summarize that work as bullets. Group them under a `## <today>` heading.
     - If a heading for today already exists, append the new bullets to it
       (don't duplicate existing ones).
     - Otherwise insert a new `## <today>` section directly below the header,
       above the most recent existing date.

4. **Show the user the bullets you added** and stop. Do not commit or merge
   unless asked — the user drives those.

## Writing good bullets

- One change per bullet, phrased in the past tense or as a noun phrase
  ("Added Strava OAuth flow", not "I added...").
- Describe user- or developer-facing impact, not file-by-file mechanics.
- Group related commits into a single bullet when they form one logical change.
- Skip noise: formatting-only commits, merge commits, WIP checkpoints.
- Keep the project's existing tone and granularity if the file already has entries.

## Format

```markdown
# Changelog

All notable changes to this project are recorded here, grouped by date (newest first).

## 2026-06-15

- Bootstrapped the running coach app with goal intake and AI-based training plan generation.

## 2026-06-13

- Initial project skeleton and specs.
```
