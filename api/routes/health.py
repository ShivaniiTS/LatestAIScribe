"""
api/routes/health.py — Health and readiness endpoints.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter

router = APIRouter(tags=["health"])
log = logging.getLogger("api.health")


@router.get("/api")
def root():
    return {
        "service": "AI Scribe Enterprise API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@router.get("/health")
async def health():
    """Basic liveness probe."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    """
    Readiness probe — checks that core services are reachable.
    Returns 503 if any critical dependency is down.
    """
    checks: dict[str, str] = {}

    # Check Ollama
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else "degraded"
    except Exception:
        checks["ollama"] = "unavailable"

    # Check database
    try:
        from db.models import get_engine
        engine = get_engine()
        if engine:
            checks["database"] = "ok"
        else:
            checks["database"] = "not_configured"
    except Exception:
        checks["database"] = "unavailable"

    all_ok = all(v in ("ok", "not_configured") for v in checks.values())

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
    )
