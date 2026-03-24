"""
orchestrator/edges/asr_router.py — Route after transcription.

Currently single-path: always routes to "note".
Returns "end" if transcription failed.
"""
from orchestrator.state import EncounterState


def asr_router(state: EncounterState) -> str:
    """Route after transcription: 'note' on success, 'end' on failure."""
    if state.get("status") == "failed":
        return "end"
    if not state.get("transcript"):
        return "end"
    return "note"
