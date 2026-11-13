"""Fail when code uses an identifier form of a term GLOSSARY.md says to avoid.

Reads every `_Avoid_:` line in GLOSSARY.md and keeps the multi-word terms
("days per week", "hard workout"). Each becomes two identifier patterns,
snake_case (days_per_week) and camelCase (daysPerWeek). Prose is not scanned:
prompts and comments may use ordinary words. Single-word terms are skipped as
too common.

A hit is allowed only through KNOWN, each entry naming why and the issue that
removes it, so the list shrinks as the glossary and the code converge.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["app", "frontend/src", "tests"]
SKIP_PARTS = {"__pycache__", "node_modules", "dist"}
SKIP_PATHS = ("app/db/migrations/",)  # history is immutable

# (file regex, identifier regex, reason)
KNOWN = [
    (r"^tests/test_weekly_availability\.py$", r"days_per_week",
     "the migration test seeds an old-format Goal"),
    (r"^(app/api/goals\.py|tests/.*)$", r"daysPerWeek",
     "GET /goals keeps daysPerWeek for the history page (issue #6 spec)"),
    (r"^(app|tests)/.*$", r"workout_sessions?|WorkoutSession",
     "legacy table and model name; glossary says Planned workout"),
    (r"^(app|frontend/src|tests)/.*$", r"fitness_level|fitnessLevel",
     "not renamed yet; glossary says Planner label (issue #17)"),
    (r"^(app|tests)/.*$", r"training_plans?|TrainingPlan",
     "table and model name stay (glossary Plan entry)"),
]


def avoided_terms(glossary: str) -> list[str]:
    terms = []
    for line in glossary.splitlines():
        if not line.startswith("_Avoid_:"):
            continue
        for item in line.removeprefix("_Avoid_:").split(","):
            item = re.sub(r"\(.*?\)", "", item).strip().strip('"')
            if " " in item and "/" not in item:
                terms.append(item.lower())
    return terms


def patterns(term: str) -> list[re.Pattern]:
    words = term.split()
    snake = "_".join(words)
    camel = words[0] + "".join(w.capitalize() for w in words[1:])
    pascal = "".join(w.capitalize() for w in words)
    return [re.compile(rf"\b({re.escape(x)})\b") for x in (snake, camel, pascal)]


def files():
    for d in SCAN_DIRS:
        for path in (ROOT / d).rglob("*"):
            rel = path.relative_to(ROOT).as_posix()
            if (path.is_file() and path.suffix in {".py", ".js", ".jsx", ".mjs"}
                    and not SKIP_PARTS & set(path.parts) and not rel.startswith(SKIP_PATHS)):
                yield rel, path


def allowed(rel: str, hit: str) -> bool:
    return any(re.search(f, rel) and re.fullmatch(i, hit) for f, i, _ in KNOWN)


def main() -> int:
    terms = avoided_terms((ROOT / "GLOSSARY.md").read_text())
    pats = [(t, p) for t in terms for p in patterns(t)]
    found = []
    for rel, path in files():
        for n, line in enumerate(path.read_text().splitlines(), 1):
            for term, pat in pats:
                for m in pat.finditer(line):
                    if not allowed(rel, m.group(1)):
                        found.append(f"{rel}:{n}: '{m.group(1)}' (glossary avoids \"{term}\")")
    for f in found:
        print(f, file=sys.stderr)
    if found:
        print(f"{len(found)} avoided term(s); use the glossary term or add a KNOWN entry.", file=sys.stderr)
        return 1
    print(f"glossary ok: {len(terms)} multi-word avoided terms, no identifier uses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
