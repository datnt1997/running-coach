import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from pydantic import BaseModel, field_validator

from app.agent.plan_chat import (
    HISTORY_LIMIT, MAX_SUMMARY_CHARS, SUMMARY_BATCH, build_messages, build_summary_messages, split_proposal,
)
from app.ai.client import AIClient
from app.ai.factory import get_chat_ai_client_dep
from app.api.profile_facts import fact_out
from app.auth import require_runner
from app.db.connection import get_db
from app.db.repositories import (
    ChatMessageRepository, GoalRepository, PlanRepository, ProfileFactRepository, ProfileRepository,
    RollingSummaryRepository,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plan-chat")

MAX_MESSAGE_CHARS = 4000


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


def _out(row: dict) -> dict:
    proposal = (
        {"text": row["proposed_fact"], "status": row["proposal_status"]} if row["proposed_fact"] else None
    )
    return {
        "proposal": proposal,
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
    of them wait; raw messages stay stored. If the model cannot summarize, the turn goes
    on without it and the fold is retried next turn; the prompt stays bounded either way.
    """
    summaries = RollingSummaryRepository(db, runner_id)
    current = await summaries.get()
    covered = current["covered_seq"] if current else 0
    summary = current["content"] if current else None
    pending = await ChatMessageRepository(db, runner_id).list_after(covered)
    older = pending[:-HISTORY_LIMIT]
    if len(older) >= SUMMARY_BATCH:
        await db.commit()
        try:
            response = await ai_client.generate(build_summary_messages(summary, older))
            text = response.content.strip()[:MAX_SUMMARY_CHARS]
            if not text:
                raise ValueError("empty summary")
            await summaries.save(text, older[-1]["seq"])
            await db.commit()
            summary, pending = text, pending[-HISTORY_LIMIT:]
        except Exception:
            logger.exception("Rolling summary failed; continuing without folding")
            await db.rollback()
    return summary, pending[-(HISTORY_LIMIT + SUMMARY_BATCH):]


async def _reply(db: AsyncConnection, runner_id: UUID, ai_client: AIClient, answering: UUID) -> dict:
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
    await db.commit()

    try:
        response = await ai_client.generate(build_messages(profile, goal, plan, history, facts=facts, declined=declined, summary=summary))
        content, proposed_fact = split_proposal(response.content)
        if not content:
            raise ValueError("empty reply")
    except Exception:
        logger.exception("Plan chat AI call failed")
        raise HTTPException(status_code=502, detail="The coach could not answer. Try again.")

    messages = ChatMessageRepository(db, runner_id)
    last = await messages.last()
    if last is None or last["id"] != answering or last["role"] != "user":
        await db.rollback()
        raise HTTPException(status_code=409, detail="Nothing to answer")
    reply = await messages.add("assistant", content, proposed_fact)
    await db.commit()
    return reply


@router.get("/messages")
async def list_messages(
    db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)
) -> dict:
    return {"messages": [_out(m) for m in await ChatMessageRepository(db, runner_id).list_all()]}


@router.post("/messages")
async def send_message(
    req: SendMessageRequest,
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
    ai_client: AIClient = Depends(get_chat_ai_client_dep),
) -> dict:
    # The runner's message is stored before the model is called, so a failure loses nothing.
    async with _turn_lock(db, runner_id):
        stored = await ChatMessageRepository(db, runner_id).add("user", req.message)
        await db.commit()
        reply = await _reply(db, runner_id, ai_client, stored["id"])
    return {"messages": [_out(stored), _out(reply)]}


@router.post("/retry")
async def retry(
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
    ai_client: AIClient = Depends(get_chat_ai_client_dep),
) -> dict:
    """Answer the last message again after a failed call (it is still stored, unanswered)."""
    async with _turn_lock(db, runner_id):
        last = await ChatMessageRepository(db, runner_id).last()
        await db.commit()
        if last is None or last["role"] != "user":
            raise HTTPException(status_code=409, detail="Nothing to answer")
        reply = await _reply(db, runner_id, ai_client, last["id"])
    return {"messages": [_out(reply)]}


DECLINED_LIMIT = 5


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
    return {"message": _out(message), "fact": fact_out(fact) if fact else None}


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
