"""
orchestrator/graph.py — LangGraph pipeline builder.

6-node pipeline: CONTEXT → CAPTURE → TRANSCRIBE → NOTE → REVIEW → DELIVERY

Uses conditional edges (asr_router, llm_router) for future multi-engine support.
Currently single-path: whisperx → qwen2.5:14b.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from orchestrator.state import EncounterState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build the 6-node LangGraph encounter pipeline."""
    from orchestrator.nodes.context_node import context_node
    from orchestrator.nodes.capture_node import capture_node
    from orchestrator.nodes.transcribe_node import transcribe_node
    from orchestrator.nodes.note_node import note_node
    from orchestrator.nodes.review_node import review_node
    from orchestrator.nodes.delivery_node import delivery_node
    from orchestrator.edges.asr_router import asr_router
    from orchestrator.edges.llm_router import llm_router

    graph = StateGraph(EncounterState)

    # Add nodes
    graph.add_node("context", context_node)
    graph.add_node("capture", capture_node)
    graph.add_node("transcribe", transcribe_node)
    graph.add_node("note", note_node)
    graph.add_node("review", review_node)
    graph.add_node("delivery", delivery_node)

    # Set entry point
    graph.set_entry_point("context")

    # Linear edges with conditional routing points
    graph.add_edge("context", "capture")
    graph.add_edge("capture", "transcribe")
    graph.add_conditional_edges("transcribe", asr_router, {"note": "note", "end": END})
    graph.add_conditional_edges("note", llm_router, {"review": "review", "end": END})
    graph.add_edge("review", "delivery")
    graph.add_edge("delivery", END)

    return graph


_compiled_graph = None


def get_compiled_graph():
    """Get or compile the pipeline graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph


def run_encounter(
    graph_or_id=None,
    initial_state_or_provider: str | dict | None = None,
    audio_file_path: str | None = None,
    note_type: str = "soap",
    recording_mode: str = "conversation",
    context: dict[str, Any] | None = None,
    **kwargs,
) -> EncounterState:
    """
    Run the full pipeline synchronously.

    Can be called two ways:
      1. run_encounter(compiled_graph, state_dict)  — pre-built state
      2. run_encounter(encounter_id=..., provider_id=..., audio_file_path=...)
    """
    # Detect if called with (graph, state) pattern
    if graph_or_id is not None and isinstance(initial_state_or_provider, dict):
        compiled = graph_or_id
        initial_state = initial_state_or_provider
        encounter_id = initial_state.get("encounter_id", str(uuid.uuid4()))
    else:
        compiled = get_compiled_graph()
        encounter_id = graph_or_id if isinstance(graph_or_id, str) else str(uuid.uuid4())
        provider_id = initial_state_or_provider if isinstance(initial_state_or_provider, str) else "default"
        initial_state = {
            "encounter_id": encounter_id,
            "provider_id": provider_id,
            "audio_file_path": audio_file_path,
            "note_type": note_type,
            "recording_mode": recording_mode,
            "status": "created",
            "context": context,
            "audio_segments": [],
            "transcript": None,
            "note": None,
            "clinical_note": None,
            "corrections": [],
            "is_approved": False,
            "delivered": False,
            "delivery_target": "database",
            "mt_job_id": None,
            "mt_status": None,
            "metrics": {},
            "errors": [],
            "error": None,
            "error_stage": None,
        }

    start = time.time()

    try:
        result = compiled.invoke(initial_state)
        elapsed = int((time.time() - start) * 1000)
        if result.get("metrics"):
            result["metrics"]["total_duration_ms"] = elapsed
        logger.info(
            "pipeline: encounter %s completed in %dms",
            encounter_id, elapsed,
        )
        return result
    except Exception as e:
        logger.error("pipeline: encounter %s failed: %s", encounter_id, e)
        initial_state["status"] = "failed"
        initial_state["error"] = str(e)
        return initial_state


async def arun_encounter(
    graph_or_id=None,
    initial_state_or_provider: str | dict | None = None,
    audio_file_path: str | None = None,
    note_type: str = "soap",
    recording_mode: str = "conversation",
    context: dict[str, Any] | None = None,
    **kwargs,
) -> EncounterState:
    """
    Run the full pipeline asynchronously.

    Can be called two ways:
      1. arun_encounter(compiled_graph, state_dict)  — pre-built state
      2. arun_encounter(encounter_id=..., provider_id=..., audio_file_path=...)
    """
    if graph_or_id is not None and isinstance(initial_state_or_provider, dict):
        compiled = graph_or_id
        initial_state = initial_state_or_provider
        encounter_id = initial_state.get("encounter_id", str(uuid.uuid4()))
    else:
        compiled = get_compiled_graph()
        encounter_id = graph_or_id if isinstance(graph_or_id, str) else str(uuid.uuid4())
        provider_id = initial_state_or_provider if isinstance(initial_state_or_provider, str) else "default"
        initial_state = {
            "encounter_id": encounter_id,
            "provider_id": provider_id,
            "audio_file_path": audio_file_path,
            "note_type": note_type,
            "recording_mode": recording_mode,
            "status": "created",
            "context": context,
            "audio_segments": [],
            "transcript": None,
            "note": None,
            "clinical_note": None,
            "corrections": [],
            "is_approved": False,
            "delivered": False,
            "delivery_target": "database",
            "mt_job_id": None,
            "mt_status": None,
            "metrics": {},
            "errors": [],
            "error": None,
            "error_stage": None,
        }

    start = time.time()

    try:
        result = await compiled.ainvoke(initial_state)
        elapsed = int((time.time() - start) * 1000)
        if result.get("metrics"):
            result["metrics"]["total_duration_ms"] = elapsed
        logger.info(
            "pipeline: encounter %s completed in %dms",
            encounter_id, elapsed,
        )
        return result
    except Exception as e:
        logger.error("pipeline: encounter %s failed: %s", encounter_id, e)
        initial_state["status"] = "failed"
        initial_state["error"] = str(e)
        return initial_state
