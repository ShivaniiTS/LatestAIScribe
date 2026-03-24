"""
tests/test_registry.py — Tests for the MCP server registry.
"""
import pytest


def test_registry_singleton():
    from mcp_servers.registry import get_registry
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


@pytest.mark.asyncio
async def test_health_check_all():
    from mcp_servers.registry import get_registry
    registry = get_registry()
    result = await registry.health_check_all()
    assert hasattr(result, "engines")
