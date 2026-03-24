"""
api/ws/session_events.py — WebSocket endpoint for real-time pipeline progress.

Clients subscribe by encounter_id; server broadcasts stage events.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])
log = logging.getLogger("ws")


class ConnectionManager:
    """Manages per-encounter WebSocket connections."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, encounter_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(encounter_id, []).append(ws)

    def disconnect(self, encounter_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(encounter_id, [])
        if ws in conns:
            conns.remove(ws)

    async def send(self, encounter_id: str, data: dict[str, Any]) -> None:
        """Broadcast event to all subscribers of an encounter."""
        message = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in self._connections.get(encounter_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(encounter_id, ws)

    async def send_progress(
        self,
        encounter_id: str,
        stage: str,
        pct: int,
        message: str = "",
    ) -> None:
        await self.send(encounter_id, {
            "type": "progress",
            "stage": stage,
            "pct": pct,
            "message": message,
        })

    async def send_complete(self, encounter_id: str, note_id: str = "") -> None:
        await self.send(encounter_id, {
            "type": "complete",
            "note_id": note_id,
        })

    async def send_error(self, encounter_id: str, error: str) -> None:
        await self.send(encounter_id, {
            "type": "error",
            "error": error,
        })


manager = ConnectionManager()


@router.websocket("/ws/encounters/{encounter_id}")
async def encounter_ws(encounter_id: str, websocket: WebSocket) -> None:
    """
    WebSocket for real-time pipeline progress.

    Event shapes::

        {"type": "progress", "stage": "transcribe", "pct": 40, "message": "…"}
        {"type": "complete", "note_id": "…"}
        {"type": "error",    "error": "…"}
    """
    await manager.connect(encounter_id, websocket)
    try:
        await websocket.send_text(
            json.dumps({"type": "connected", "encounter_id": encounter_id})
        )
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(encounter_id, websocket)
