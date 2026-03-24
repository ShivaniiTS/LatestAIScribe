"""
tests/test_orchestrator.py — Tests for orchestrator state and graph.
"""
import pytest


def test_encounter_state_type():
    from orchestrator.state import EncounterState
    # EncounterState is a TypedDict — check keys exist
    assert "encounter_id" in EncounterState.__annotations__
    assert "provider_id" in EncounterState.__annotations__
    assert "errors" in EncounterState.__annotations__


langgraph = pytest.importorskip("langgraph", reason="langgraph not installed")


def test_graph_builds():
    from orchestrator.graph import build_graph
    graph = build_graph()
    assert graph is not None


def test_compiled_graph_singleton():
    from orchestrator.graph import get_compiled_graph
    g1 = get_compiled_graph()
    g2 = get_compiled_graph()
    assert g1 is g2


def test_asr_router():
    from orchestrator.edges.asr_router import asr_router
    # Success case — transcript is present and status is not failed
    state = {"transcript": {"full_text": "some text"}, "status": "generating"}
    assert asr_router(state) == "note"

    # Failure case — no transcript
    state2 = {"transcript": None, "status": "transcribing"}
    assert asr_router(state2) == "end"

    # Failure case — status is failed
    state3 = {"transcript": {"full_text": "text"}, "status": "failed"}
    assert asr_router(state3) == "end"


def test_llm_router():
    from orchestrator.edges.llm_router import llm_router
    # Success case — note is present
    state = {"note": {"full_text": "some note"}, "status": "reviewing"}
    assert llm_router(state) == "review"

    # Failure case — no note
    state2 = {"note": None, "status": "generating"}
    assert llm_router(state2) == "end"

    # Failure case — status is failed
    state3 = {"note": {"full_text": "text"}, "status": "failed"}
    assert llm_router(state3) == "end"
