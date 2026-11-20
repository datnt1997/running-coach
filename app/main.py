import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import activities, auth as auth_api, fitness_chat, goals, plans, profile, summaries
from app.api import strava, ui
from app import config
from app.auth import require_session
from app.config import FRONTEND_DIST, validate_config
from app.db.connection import close_pool, init_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    await init_pool()
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(title="Running Coach", version="0.2.0", lifespan=lifespan)

# Every data and chat router needs a session. The Strava router mixes open routes
# (the webhook) with protected ones, so it protects itself per endpoint.
_session_required = [Depends(require_session)]
app.include_router(auth_api.router)
app.include_router(goals.router, dependencies=_session_required)
app.include_router(fitness_chat.router, dependencies=_session_required)
app.include_router(plans.router, dependencies=_session_required)
app.include_router(profile.router, dependencies=_session_required)
app.include_router(strava.router)
app.include_router(ui.router)
app.include_router(activities.router, dependencies=_session_required)
app.include_router(summaries.router, dependencies=_session_required)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Serve the React SPA — only wired up after `npm run build`
if FRONTEND_DIST.exists():
    _assets = FRONTEND_DIST / "assets"
    if _assets.exists():
        app.mount("/app/assets", StaticFiles(directory=str(_assets)), name="static-assets")

    def _index_html() -> HTMLResponse:
        # The SPA reads <html lang> to pick its dictionary; keep it in sync with APP_LANGUAGE.
        html = (FRONTEND_DIST / "index.html").read_text()
        return HTMLResponse(html.replace('<html lang="vi">', f'<html lang="{config.APP_LANGUAGE}">', 1))

    @app.get("/app/{full_path:path}")
    async def serve_spa(full_path: str) -> Response:
        file = FRONTEND_DIST / full_path
        if file.is_file():
            return FileResponse(str(file))
        return _index_html()

    @app.get("/app")
    async def serve_spa_root() -> HTMLResponse:
        return _index_html()
