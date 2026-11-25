"""Plan edits: the edit step of a Plan chat turn, confirming or declining a proposal, and the edit log.

The chat model asks for a change with [[EDIT: ...]]; the edit model proposes it through
the propose_plan_edit tool; `check_plan_edit` (Python) decides whether it may be shown.
A shown proposal changes nothing until the Runner confirms it, and it is checked again then.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from app.agent.plan_edits import build_edit_messages, parse_proposal, plain, plan_days
from app.agent.validation import check_plan_edit, day_signature, reason_text
from app.ai.client import AIClient
from app.ai.tools import PROPOSE_PLAN_EDIT_TOOL
from app.auth import require_runner
from app.config import app_today
from app.db.connection import get_db
from app.db.repositories import GoalRepository, MatchedDayError, PlanEditRepository, PlanRepository
from app.vdot import training_paces

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plan-edits")


def _runs(workouts: list[dict]) -> list[dict]:
    return [
        {"type": w["type"], "distanceKm": w["distanceKm"], "paceZone": w.get("paceZone")}
        for w in workouts if w["type"].strip().lower() != "rest" and w["distanceKm"] > 0
    ]


def edit_out(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "status": row["status"],
        "request": row["request"],
        "summary": row["summary"],
        "changes": [
            {"week": c["week"], "day": c["day"], "before": _runs(c["before"]), "after": _runs(c["after"])}
            for c in row["changes"]
        ],
        "override": row["override"],
        "reasons": [{**r, "text": reason_text(r)} for r in row["reasons"] or []],
        "createdAt": row["created_at"].isoformat(),
        "decidedAt": row["decided_at"].isoformat() if row["decided_at"] else None,
    }


async def _rule_inputs(db: AsyncConnection, runner_id: UUID, plan: dict, goal: dict) -> dict:
    """What check_plan_edit needs beyond the proposal, read fresh."""
    volumes, overridden = await PlanEditRepository(db, runner_id).plan_history(plan["id"])
    return {
        "start_date": plan["start_date"],
        "total_weeks": plan["total_weeks"],
        "current": plan_days(plan["workouts"]),
        "goal": goal,
        "locked_days": await PlanRepository(db, runner_id).matched_days(plan["id"]),
        "weekly_volumes": volumes,
        "override_weeks_used": overridden,
        "easy_slow_sec_per_km": training_paces(float(goal["vdot"]))["easy_slow"] if goal.get("vdot") else None,
    }


def _week_totals(current: dict, changes: list[dict]) -> dict[int, float]:
    weeks = {c["week"] for c in changes}
    return {
        w: round(sum(x["distanceKm"] for ws in current.get(w, {}).values() for x in ws
                     if x["type"].strip().lower() != "rest"), 2)
        for w in weeks
    }


async def propose_edit(
    db: AsyncConnection, runner_id: UUID, edit_ai: AIClient, plan: dict, goal: dict, request: str, runner_message: str
) -> dict:
    """Ask the edit model for the change, check it, and store it as pending or rejected.

    Call with the Plan chat turn lock held; nothing stays open during the model call.
    """
    edits = PlanEditRepository(db, runner_id)
    today = app_today()
    try:
        inputs = await _rule_inputs(db, runner_id, plan, goal)
        await db.commit()
        response = await edit_ai.generate(
            build_edit_messages(
                request=request, runner_message=runner_message, goal=goal, plan=plan, days=inputs["current"],
                today=today, locked_days=inputs["locked_days"], weekly_volumes=inputs["weekly_volumes"],
                easy_slow_sec_per_km=inputs["easy_slow_sec_per_km"],
            ),
            tools=[PROPOSE_PLAN_EDIT_TOOL],
        )
        call = next(c for c in response.tool_calls if c.name == "propose_plan_edit")
        arguments = plain(call.arguments)
        proposed = parse_proposal(arguments)
        result = check_plan_edit(
            **inputs, proposed=proposed, today=today,
            override=arguments.get("override"), goal_change=arguments.get("goal_change"),
        )
    except Exception:
        logger.exception("Plan edit step produced no usable proposal")
        await db.rollback()
        return await edits.add(plan["id"], request, "rejected", reasons=[{"code": "no_proposal", "params": {}}])

    return await edits.add(
        plan["id"], request, "rejected" if result["reasons"] else "pending",
        summary=str(arguments.get("summary") or "")[:1000],
        changes=result["changes"], override=result["override"], reasons=result["reasons"] or None,
        week_totals=_week_totals(inputs["current"], result["changes"]),
    )


class EditConflict(Exception):
    def __init__(self, detail):
        self.detail = detail


async def apply_edit(db: AsyncConnection, runner_id: UUID, edit_id: UUID) -> dict:
    """Apply a pending edit after checking it again against the Plan as it is now.

    The Plan row is locked for the transaction. Raises LookupError when there is no
    such edit and EditConflict (with the reasons, if any) when it cannot be applied.
    """
    edits, plans = PlanEditRepository(db, runner_id), PlanRepository(db, runner_id)
    edit = await edits.get(edit_id, for_update=True)
    if edit is None:
        raise LookupError
    if edit["status"] != "pending":
        raise EditConflict("No pending edit")
    await plans.lock_plan(edit["plan_id"])
    plan = await plans.get_plan(edit["plan_id"])
    goal = await GoalRepository(db, runner_id).get(plan["goal_id"])
    if await plans.get_latest_plan_id() != plan["id"]:
        return await _reject(db, edits, edit_id, [{"code": "stale", "params": {}}])

    inputs = await _rule_inputs(db, runner_id, plan, goal)
    current = inputs["current"]
    if any(day_signature(current.get(c["week"], {}).get(c["day"], [])) != day_signature(c["before"])
           for c in edit["changes"]):
        return await _reject(db, edits, edit_id, [{"code": "stale", "params": {}}])

    proposed = {w: dict(current.get(w, {})) for w in {c["week"] for c in edit["changes"]}}
    for c in edit["changes"]:
        proposed[c["week"]][c["day"]] = c["after"]
    override = {"week_number": edit["override"]["week"], "day": edit["override"]["day"]} if edit["override"] else None
    result = check_plan_edit(**inputs, proposed=proposed, today=app_today(), override=override)
    if result["reasons"]:
        return await _reject(db, edits, edit_id, result["reasons"])

    try:
        for c in edit["changes"]:
            await plans.replace_day(plan["id"], c["week"], c["day"], c["after"])
    except MatchedDayError as matched:  # a run was matched after the check above
        await db.rollback()
        return await _reject(db, edits, edit_id, [{"code": "matched_day", "params": {"week": matched.week, "day": matched.day}}])
    applied = await edits.decide(edit_id, "applied")
    await db.commit()
    return applied


async def _reject(db: AsyncConnection, edits: PlanEditRepository, edit_id: UUID, reasons: list[dict]):
    row = await edits.decide(edit_id, "rejected", reasons)
    await db.commit()
    if row is None:  # decided elsewhere after a rollback released its lock
        raise EditConflict("No pending edit")
    raise EditConflict({"message": "The edit can no longer be applied", "edit": edit_out(row)})


@router.get("")
async def list_edits(db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)) -> dict:
    """The edit log: every applied edit, newest first."""
    return {"edits": [edit_out(e) for e in await PlanEditRepository(db, runner_id).list_applied()]}
