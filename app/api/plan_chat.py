import logging
from datetime import date
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from pydantic import BaseModel, field_validator

from app.agent.plan_chat import (
    HISTORY_LIMIT, MAX_FOLD_BATCH, MAX_FOLDS_PER_TURN, MAX_SUMMARY_CHARS, MAX_VERBATIM, SUMMARY_BATCH, build_messages, build_summary_messages, split_proposal,
)
from app.ai.client import AIClient
from app.agent.plan_edits import recent_edits_block, split_edit_request
from app.ai.factory import get_chat_ai_client_dep, get_plan_edit_ai_client_dep
from app.api.plan_edits import EditConflict, apply_edit, edit_out, propose_edit
from app.api.profile_facts import fact_out
from app.api.strava import RUN_TYPES, get_strava_client
from app.auth import require_runner
from app.timezone import runner_today
from app.db.connection import get_db
from app.db.repositories import (
    ActivityAnalysisRepository, ChatMessageRepository, GoalRepository, PlanEditRepository, PlanRepository, ProfileFactRepository,
    ProfileRepository,
    RollingSummaryRepository, StravaConnectionRepository,
)
from app.strava.client import StravaClient, get_valid_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plan-chat")

MAX_MESSAGE_CHARS = 4000
RECENT_ACTIVITIES = 10  # latest Activities listed in each turn's prompt


class SendMessageRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be blank")
        if len(value) > MAX_MESSAGE_CHARS:
            raise ValueError(f"message is longer than {MAX_MESSAGE_CHARS} characters")
        return value


def _out(row: dict, edits: dict | None = None) -> dict:
    proposal = (
        {"text": row["proposed_fact"], "status": row["proposal_status"]} if row["proposed_fact"] else None
    )
    edit = (edits or {}).get(row["plan_edit_id"])
    return {
        "proposal": proposal,
        "planEdit": edit_out(edit) if edit else None,
        "id": str(row["id"]),
        "role": row["role"],
        "content": row["content"],
        "createdAt": row["created_at"].isoformat(),
    }


@asynccontextmanager
async def _turn_lock(db: AsyncConnection, runner_id: UUID):
    """Serialize whole turns per Runner with a session-level advisory lock.

    A transaction-level lock would force the transaction to stay open during the
    AI call. The session lock survives commits, so reads and writes can commit
    around the model call while a second request (double click, two tabs, retry
    racing a slow send) waits here and then re-checks the conversation state.
    """
    key = f"plan_chat:{runner_id}"
    await db.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (key,))
    await db.commit()
    try:
        yield
    finally:
        try:
            await db.rollback()
            await db.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))
            await db.commit()
        except Exception:
            logger.exception("Could not release the Plan chat lock")  # closing the connection releases it


async def _roll_summary(db: AsyncConnection, runner_id: UUID, ai_client: AIClient) -> tuple[str | None, list[dict]]:
    """The Rolling summary and the messages still sent verbatim.

    Messages beyond the last HISTORY_LIMIT are folded into the summary once SUMMARY_BATCH
    of them wait, at most MAX_FOLD_BATCH per call and MAX_FOLDS_PER_TURN calls per turn
    (oldest first, so a backlog catches up over later turns); raw messages stay stored. If the model cannot summarize, the turn goes
    on without it and the fold is retried next turn; the prompt stays bounded either way.
    """
    summaries = RollingSummaryRepository(db, runner_id)
    current = await summaries.get()
    covered = current["covered_seq"] if current else 0
    summary = current["content"] if current else None
    pending = await ChatMessageRepository(db, runner_id).list_after(covered)
    folds = 0
    while folds < MAX_FOLDS_PER_TURN:
        older = pending[:-HISTORY_LIMIT]
        if len(older) < SUMMARY_BATCH:
            break
        batch = older[:MAX_FOLD_BATCH]  # oldest first, so a backlog never skips messages
        folds += 1
        await db.commit()
        try:
            response = await ai_client.generate(build_summary_messages(summary, batch))
            text = response.content.strip()[:MAX_SUMMARY_CHARS]
            if not text:
                raise ValueError("empty summary")
            await summaries.save(text, batch[-1]["seq"])
            await db.commit()
            summary, pending = text, pending[len(batch):]
        except Exception:
            logger.exception("Rolling summary failed; continuing without folding")
            await db.rollback()
            break
    return summary, pending[-MAX_VERBATIM:]


async def _recent_activities(db: AsyncConnection, runner_id: UUID, strava_client: StravaClient) -> list[dict]:
    """The latest runs, read live from Strava so runs from before the webhook count too.

    Each carries our stored analysis (Match, Adherence) when there is one. Without a Strava
    connection, or when Strava cannot be reached, fall back to the stored analyses.
    """
    stored = await ActivityAnalysisRepository(db, runner_id).list_recent(RECENT_ACTIVITIES)
    if await StravaConnectionRepository(db, runner_id).get() is None:
        return stored
    try:
        token = await get_valid_access_token(db, runner_id, strava_client)
        recent = await strava_client.list_activities(token, limit=RECENT_ACTIVITIES * 2)
    except Exception:
        logger.warning("Could not read live Strava activities; using stored analyses", exc_info=True)
        return stored
    runs = [a for a in recent if a.type in RUN_TYPES][:RECENT_ACTIVITIES]
    analyses = await ActivityAnalysisRepository(db, runner_id).by_strava_ids([a.id for a in runs])
    out = []
    for a in runs:
        analysis = analyses.get(a.id) or {}
        km = a.distance / 1000
        out.append({
            "activity_date": date.fromisoformat(a.start_date_local[:10]),
            "distance_km": km,
            "pace_sec_per_km": round(a.moving_time / km) if km > 0 else None,
            "avg_hr_bpm": a.average_heartrate,
            "workout_type": analysis.get("workout_type"),
            "planned_distance_km": analysis.get("planned_distance_km"),
            "mismatch": analysis.get("mismatch", False),
            "pace_adherence": analysis.get("pace_adherence"),
            "hr_adherence": analysis.get("hr_adherence"),
            "load_adherence": analysis.get("load_adherence"),
        })
    return out


async def _outs(db: AsyncConnection, runner_id: UUID, rows: list[dict]) -> list[dict]:
    edits = await PlanEditRepository(db, runner_id).by_ids([r["plan_edit_id"] for r in rows if r["plan_edit_id"]])
    return [_out(r, edits) for r in rows]


async def _reply(
    db: AsyncConnection, runner_id: UUID, ai_client: AIClient, answering: UUID, strava_client: StravaClient,
    edit_ai: AIClient, today: date,
) -> dict:
    """Ask the model to answer the stored conversation and store its reply.

    Profile and Plan are read fresh; the last HISTORY_LIMIT messages go verbatim and older ones as a Rolling summary.
    Call with the turn lock held. The reads are committed before the model call so
    no transaction stays open while it runs.
    """
    plans = PlanRepository(db, runner_id)
    plan_id = await plans.get_latest_plan_id()
    plan = await plans.get_plan(plan_id) if plan_id else None
    goal = await GoalRepository(db, runner_id).get(plan["goal_id"]) if plan else None
    profile = await ProfileRepository(db, runner_id).get()
    summary, history = await _roll_summary(db, runner_id, ai_client)
    facts = await ProfileFactRepository(db, runner_id).list_all()
    declined = await ChatMessageRepository(db, runner_id).recent_declined_facts(DECLINED_LIMIT)
    activities = await _recent_activities(db, runner_id, strava_client)
    edits_block = recent_edits_block(await PlanEditRepository(db, runner_id).list_recent(RECENT_EDITS))
    await db.commit()

    try:
        response = await ai_client.generate(
            build_messages(
                profile, goal, plan, history, facts=facts, declined=declined, summary=summary, activities=activities,
                edits=edits_block, today=today,
            )
        )
        content, proposed_fact = split_proposal(response.content)
        content, edit_request = split_edit_request(content)
        if not content:
            raise ValueError("empty reply")
    except Exception:
        logger.exception("Plan chat AI call failed")
        raise HTTPException(status_code=502, detail="The coach could not answer. Try again.")

    edit = None
    if edit_request and plan and goal:
        runner_message = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        edit = await propose_edit(db, runner_id, edit_ai, plan, goal, edit_request, runner_message, today)

    messages = ChatMessageRepository(db, runner_id)
    last = await messages.last()
    if last is None or last["id"] != answering or last["role"] != "user":
        await db.rollback()
        raise HTTPException(status_code=409, detail="Nothing to answer")
    reply = await messages.add("assistant", content, proposed_fact, edit["id"] if edit else None)
    await db.commit()
    return reply


@router.get("/messages")
async def list_messages(
    db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)
) -> dict:
    return {"messages": await _outs(db, runner_id, await ChatMessageRepository(db, runner_id).list_all())}


@router.post("/messages")
async def send_message(
    req: SendMessageRequest,
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
    ai_client: AIClient = Depends(get_chat_ai_client_dep),
    strava_client: StravaClient = Depends(get_strava_client),
    edit_ai: AIClient = Depends(get_plan_edit_ai_client_dep),
    today: date = Depends(runner_today),
) -> dict:
    # The runner's message is stored before the model is called, so a failure loses nothing.
    async with _turn_lock(db, runner_id):
        stored = await ChatMessageRepository(db, runner_id).add("user", req.message)
        await db.commit()
        reply = await _reply(db, runner_id, ai_client, stored["id"], strava_client, edit_ai, today)
        out = await _outs(db, runner_id, [stored, reply])
    return {"messages": out}


@router.post("/retry")
async def retry(
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
    ai_client: AIClient = Depends(get_chat_ai_client_dep),
    strava_client: StravaClient = Depends(get_strava_client),
    edit_ai: AIClient = Depends(get_plan_edit_ai_client_dep),
    today: date = Depends(runner_today),
) -> dict:
    """Answer the last message again after a failed call (it is still stored, unanswered)."""
    async with _turn_lock(db, runner_id):
        last = await ChatMessageRepository(db, runner_id).last()
        await db.commit()
        if last is None or last["role"] != "user":
            raise HTTPException(status_code=409, detail="Nothing to answer")
        reply = await _reply(db, runner_id, ai_client, last["id"], strava_client, edit_ai, today)
        out = await _outs(db, runner_id, [reply])
    return {"messages": out}


DECLINED_LIMIT = 5
RECENT_EDITS = 5  # latest Plan edit proposals shown to the coach


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


async def _decide(db: AsyncConnection, runner_id: UUID, message_id: UUID, status: str) -> dict:
    """Settle a pending proposal; saving the fact and closing the proposal commit together."""
    messages = ChatMessageRepository(db, runner_id)
    message = await messages.decide_proposal(message_id, status)
    if message is None:
        found = await messages.get(message_id)
        await db.rollback()
        if found is None:
            raise HTTPException(status_code=404, detail="No such message")
        raise HTTPException(status_code=409, detail="No pending proposal")
    fact = None
    if status == "saved":
        facts = ProfileFactRepository(db, runner_id)
        wanted = _normalized(message["proposed_fact"])
        fact = next((f for f in await facts.list_all() if _normalized(f["text"]) == wanted), None)
        fact = fact or await facts.add(message["proposed_fact"])
    await db.commit()
    return {"message": (await _outs(db, runner_id, [message]))[0], "fact": fact_out(fact) if fact else None}


@router.post("/messages/{message_id}/proposal/confirm")
async def confirm_proposal(
    message_id: UUID, db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)
) -> dict:
    return await _decide(db, runner_id, message_id, "saved")


@router.post("/messages/{message_id}/proposal/decline")
async def decline_proposal(
    message_id: UUID, db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)
) -> dict:
    return await _decide(db, runner_id, message_id, "declined")


async def _message_edit_id(db: AsyncConnection, runner_id: UUID, message_id: UUID) -> UUID:
    message = await ChatMessageRepository(db, runner_id).get(message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="No such message")
    if message["plan_edit_id"] is None:
        raise HTTPException(status_code=409, detail="No pending edit")
    return message["plan_edit_id"]


@router.post("/messages/{message_id}/edit/confirm")
async def confirm_edit(
    message_id: UUID,
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
    today: date = Depends(runner_today),
) -> dict:
    """Apply the proposed Plan edit, checked again against the Plan as it is now, and log it."""
    async with _turn_lock(db, runner_id):
        edit_id = await _message_edit_id(db, runner_id, message_id)
        try:
            applied = await apply_edit(db, runner_id, edit_id, today)
        except EditConflict as conflict:
            raise HTTPException(status_code=409, detail=conflict.detail)
        except LookupError:
            await db.rollback()
            raise HTTPException(status_code=404, detail="No such edit")
    return {"edit": edit_out(applied)}


@router.post("/messages/{message_id}/edit/decline")
async def decline_edit(
    message_id: UUID, db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)
) -> dict:
    edit_id = await _message_edit_id(db, runner_id, message_id)
    row = await PlanEditRepository(db, runner_id).decide(edit_id, "declined")
    if row is None:
        await db.rollback()
        raise HTTPException(status_code=409, detail="No pending edit")
    await db.commit()
    return {"edit": edit_out(row)}
