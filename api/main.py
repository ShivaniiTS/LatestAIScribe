"""
api/main.py — FastAPI application entry point (single-server).

Start with:
    uvicorn api.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-20s %(levelname)-7s %(message)s",
)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("AI Scribe Enterprise API starting")

    # Initialize database (create tables if needed)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            from db.models import init_db
            await init_db()
            log.info("Database initialized")
        except Exception as e:
            log.warning("Database init skipped: %s", e)

    yield

    # Shutdown: close DB connections + unload GPU models
    try:
        from db.models import close_db
        await close_db()
    except Exception:
        pass

    try:
        from mcp_servers.registry import get_registry
        registry = get_registry()
        for name in ["asr", "llm"]:
            try:
                registry.unload_engine(name)
            except Exception:
                pass
    except Exception:
        pass

    log.info("AI Scribe Enterprise API shutdown")


app = FastAPI(
    title="AI Scribe Enterprise API",
    description="REST + WebSocket API for the AI medical scribe pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS ─────────────────────────────────────────────────────────────────

_origins = os.getenv("CORS_ORIGINS", "http://localhost:9000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────────

from api.routes.health import router as health_router        # noqa: E402
from api.routes.encounters import router as encounters_router  # noqa: E402
from api.routes.providers import router as providers_router    # noqa: E402
from api.routes.notes import router as notes_router            # noqa: E402
from api.routes.mt import router as mt_router                  # noqa: E402
from api.routes.scribe import router as scribe_router          # noqa: E402
from api.ws.session_events import router as ws_router          # noqa: E402

app.include_router(health_router)
app.include_router(encounters_router)
app.include_router(providers_router)
app.include_router(notes_router)
app.include_router(mt_router)
app.include_router(scribe_router)
app.include_router(ws_router)

# ── Static frontend (served in Docker / production) ───────────────────────
import os as _os  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_static_dir = _Path(__file__).parent.parent / "static"
if _static_dir.is_dir():
    from fastapi.staticfiles import StaticFiles  # noqa: E402
    # Serve the built Quasar SPA — must be mounted LAST so API routes take priority
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="spa")
    log.info("Serving frontend from %s", _static_dir)
