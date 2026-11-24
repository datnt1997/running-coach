import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from pydantic import BaseModel, field_validator

from app.agent.plan_chat import HISTORY_LIMIT, build_messages
from app.ai.client import AIClient
from app.ai.factory import get_chat_ai_client_dep
from app.auth import require_runner
from app.db.connection import get_db
from app.db.repositories import ChatMessageRepository, GoalRepository, PlanRepository, ProfileRepository

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
    return {
        "id": str(row["id"]),
        "role": row["role"],
        "content": row["content"],
        "createdAt": row["created_at"].isoformat(),
    }


async def _reply(db: AsyncConnection, runner_id: UUID, ai_client: AIClient) -> dict:
    """Ask the model to answer the stored conversation and store its reply.

    Profile and Plan are read fresh; only the last HISTORY_LIMIT messages go verbatim.
    """
    plans = PlanRepository(db, runner_id)
    plan_id = await plans.get_latest_plan_id()
    plan = await plans.get_plan(plan_id) if plan_id else None
    goal = await GoalRepository(db, runner_id).get(plan["goal_id"]) if plan else None
    profile = await ProfileRepository(db, runner_id).get()
    history = await ChatMessageRepository(db, runner_id).list_recent(HISTORY_LIMIT)

    try:
        response = await ai_client.generate(build_messages(profile, goal, plan, history))
        content = response.content.strip()
        if not content:
            raise ValueError("empty reply")
    except Exception:
        logger.exception("Plan chat AI call failed")
        raise HTTPException(status_code=502, detail="The coach could not answer. Try again.")

    reply = await ChatMessageRepository(db, runner_id).add("assistant", content)
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
    stored = await ChatMessageRepository(db, runner_id).add("user", req.message)
    await db.commit()
    reply = await _reply(db, runner_id, ai_client)
    return {"messages": [_out(stored), _out(reply)]}


@router.post("/retry")
async def retry(
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
    ai_client: AIClient = Depends(get_chat_ai_client_dep),
) -> dict:
    """Answer the last message again after a failed call (it is still stored, unanswered)."""
    last = await ChatMessageRepository(db, runner_id).last()
    if last is None or last["role"] != "user":
        raise HTTPException(status_code=409, detail="Nothing to answer")
    return {"messages": [_out(await _reply(db, runner_id, ai_client))]}
