from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import goals, plans
from app.config import validate_config
from app.db.connection import close_pool, init_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    await init_pool()
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(title="Running Coach", version="0.1.0", lifespan=lifespan)

app.include_router(goals.router)
app.include_router(plans.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
