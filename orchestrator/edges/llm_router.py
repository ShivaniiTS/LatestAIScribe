"""
orchestrator/edges/llm_router.py — Route after note generation.

Currently single-path: always routes to "review".
Returns "end" if note generation failed.
"""
from orchestrator.state import EncounterState


def llm_router(state: EncounterState) -> str:
    """Route after note generation: 'review' on success, 'end' on failure."""
    if state.get("status") == "failed":
        return "end"
    if not state.get("note"):
        return "end"
    return "review"
