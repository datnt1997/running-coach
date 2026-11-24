import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from pydantic import BaseModel, field_validator

from app.agent.plan_chat import HISTORY_LIMIT, build_messages, split_proposal
from app.ai.client import AIClient
from app.ai.factory import get_chat_ai_client_dep
from app.api.profile_facts import fact_out
from app.auth import require_runner
from app.db.connection import get_db
from app.db.repositories import (
    ChatMessageRepository, GoalRepository, PlanRepository, ProfileFactRepository, ProfileRepository,
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


async def _reply(db: AsyncConnection, runner_id: UUID, ai_client: AIClient, answering: UUID) -> dict:
    """Ask the model to answer the stored conversation and store its reply.

    Profile and Plan are read fresh; only the last HISTORY_LIMIT messages go verbatim.
    Call with the turn lock held. The reads are committed before the model call so
    no transaction stays open while it runs.
    """
    plans = PlanRepository(db, runner_id)
    plan_id = await plans.get_latest_plan_id()
    plan = await plans.get_plan(plan_id) if plan_id else None
    goal = await GoalRepository(db, runner_id).get(plan["goal_id"]) if plan else None
    profile = await ProfileRepository(db, runner_id).get()
    history = await ChatMessageRepository(db, runner_id).list_recent(HISTORY_LIMIT)
    facts = await ProfileFactRepository(db, runner_id).list_all()
    await db.commit()

    try:
        response = await ai_client.generate(build_messages(profile, goal, plan, history, facts=facts))
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
    fact = await ProfileFactRepository(db, runner_id).add(message["proposed_fact"]) if status == "saved" else None
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
