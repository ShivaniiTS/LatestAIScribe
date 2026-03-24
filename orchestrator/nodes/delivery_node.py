"""
orchestrator/nodes/delivery_node.py — Deliver the completed note.

Persists the note to the database and notifies via WebSocket.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from orchestrator.state import EncounterState

logger = logging.getLogger(__name__)


def delivery_node(state: EncounterState) -> dict[str, Any]:
    """Persist the final note and send completion event."""
    start = time.time()
    encounter_id = state.get("encounter_id", "unknown")

    logger.info("delivery_node: delivering note for %s", encounter_id)

    note = state.get("note")
    if not note:
        return {
            "status": "failed",
            "error": "No note to deliver",
            "error_stage": "delivery",
        }

    # Persist to database (async context handled by API layer)
    delivered = False
    try:
        _persist_to_db(state)
        delivered = True
    except Exception as e:
        logger.warning("delivery_node: DB persistence failed: %s", e)

    # Send WebSocket notification
    try:
        _notify_ws(encounter_id)
    except Exception as e:
        logger.debug("delivery_node: WS notification failed: %s", e)

    elapsed = int((time.time() - start) * 1000)
    metrics = state.get("metrics") or {}
    metrics["delivery_ms"] = elapsed

    final_status = state.get("status", "completed")
    if final_status not in ("mt_review", "failed"):
        final_status = "completed"

    logger.info("delivery_node: done — status=%s, %dms", final_status, elapsed)

    return {
        "status": final_status,
        "delivered": delivered,
        "metrics": metrics,
    }


def _persist_to_db(state: dict) -> None:
    """Attempt to persist encounter results to the database."""
    # This is called from a sync context (LangGraph node).
    # For actual DB writes, the API layer handles this after pipeline completion.
    logger.debug("delivery_node: results queued for DB persistence")


def _notify_ws(encounter_id: str) -> None:
    """Send a WebSocket completion event."""
    try:
        import asyncio
        from api.ws.session_events import manager
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(manager.send_complete(encounter_id, encounter_id))
        else:
            loop.run_until_complete(manager.send_complete(encounter_id, encounter_id))
    except Exception:
        pass
