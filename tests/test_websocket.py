"""
tests/test_websocket.py — Tests for WebSocket connection manager.
"""
import asyncio
import pytest
from api.ws.session_events import ConnectionManager


@pytest.mark.asyncio
async def test_connection_manager():
    mgr = ConnectionManager()
    # Just verify the manager initializes
    assert mgr._connections == {}


@pytest.mark.asyncio
async def test_send_no_connections():
    mgr = ConnectionManager()
    # Should not raise even with no connections
    await mgr.send("test-encounter", {"type": "progress", "pct": 50})


@pytest.mark.asyncio
async def test_send_progress():
    mgr = ConnectionManager()
    await mgr.send_progress("test-id", "transcribe", 50, "Half done")


@pytest.mark.asyncio
async def test_send_complete():
    mgr = ConnectionManager()
    await mgr.send_complete("test-id", "note-123")


@pytest.mark.asyncio
async def test_send_error():
    mgr = ConnectionManager()
    await mgr.send_error("test-id", "Something went wrong")
