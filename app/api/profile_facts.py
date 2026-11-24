"""Profile facts page: list, edit and delete. New facts only arrive through a confirmed Plan chat proposal."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from pydantic import BaseModel, field_validator

from app.agent.plan_chat import MAX_FACT_CHARS
from app.auth import require_runner
from app.db.connection import get_db
from app.db.repositories import ProfileFactRepository

router = APIRouter(prefix="/profile-facts")


class FactRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _valid(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("text cannot be blank")
        if len(value) > MAX_FACT_CHARS:
            raise ValueError(f"text is longer than {MAX_FACT_CHARS} characters")
        return value


def fact_out(row: dict) -> dict:
    return {"id": str(row["id"]), "text": row["text"], "updatedAt": row["updated_at"].isoformat()}


@router.get("")
async def list_facts(
    db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)
) -> dict:
    return {"facts": [fact_out(f) for f in await ProfileFactRepository(db, runner_id).list_all()]}


@router.put("/{fact_id}")
async def edit_fact(
    fact_id: UUID,
    req: FactRequest,
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
) -> dict:
    row = await ProfileFactRepository(db, runner_id).update(fact_id, req.text)
    if row is None:
        raise HTTPException(status_code=404, detail="No such fact")
    await db.commit()
    return fact_out(row)


@router.delete("/{fact_id}")
async def delete_fact(
    fact_id: UUID, db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)
) -> dict:
    if not await ProfileFactRepository(db, runner_id).delete(fact_id):
        raise HTTPException(status_code=404, detail="No such fact")
    await db.commit()
    return {"deleted": True}
