import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import activities, goals, plans, summaries
from app.api import strava, ui
from app.config import validate_config
from app.db.connection import close_pool, init_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

FRONTEND_DIST = pathlib.Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    await init_pool()
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(title="Running Coach", version="0.2.0", lifespan=lifespan)

app.include_router(goals.router)
app.include_router(plans.router)
app.include_router(strava.router)
app.include_router(ui.router)
app.include_router(activities.router)
app.include_router(summaries.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Serve the React SPA — only wired up after `npm run build`
if FRONTEND_DIST.exists():
    _assets = FRONTEND_DIST / "assets"
    if _assets.exists():
        app.mount("/app/assets", StaticFiles(directory=str(_assets)), name="static-assets")

    @app.get("/app/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        file = FRONTEND_DIST / full_path
        if file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(FRONTEND_DIST / "index.html"))

    @app.get("/app")
    async def serve_spa_root() -> FileResponse:
        return FileResponse(str(FRONTEND_DIST / "index.html"))
