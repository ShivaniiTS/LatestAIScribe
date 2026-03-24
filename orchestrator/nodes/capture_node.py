"""
orchestrator/nodes/capture_node.py — Audio capture stub.

Wraps the audio_file_path from state into an AudioSegment record.
In production, this would handle real-time recording; for now it
just validates the audio file exists and records its metadata.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from orchestrator.state import EncounterState

logger = logging.getLogger(__name__)


def capture_node(state: EncounterState) -> dict[str, Any]:
    """Validate audio file and create AudioSegment metadata."""
    start = time.time()
    encounter_id = state.get("encounter_id", "unknown")
    audio_path = state.get("audio_file_path")

    logger.info("capture_node: processing audio for encounter %s", encounter_id)

    if not audio_path:
        return {
            "status": "failed",
            "error": "No audio file path provided",
            "error_stage": "capture",
        }

    if not os.path.exists(audio_path):
        return {
            "status": "failed",
            "error": f"Audio file not found: {audio_path}",
            "error_stage": "capture",
        }

    file_size = os.path.getsize(audio_path)
    ext = os.path.splitext(audio_path)[1].lower().lstrip(".")

    audio_segment = {
        "audio_file_path": audio_path,
        "channel": "mixed",
        "duration_ms": 0,  # Will be set by ASR
        "sample_rate": 16000,
        "format": ext or "wav",
    }

    elapsed = int((time.time() - start) * 1000)
    metrics = state.get("metrics") or {}
    metrics["capture_ms"] = elapsed

    logger.info(
        "capture_node: audio ready — %s (%d bytes)",
        os.path.basename(audio_path), file_size,
    )

    return {
        "status": "transcribing",
        "audio_segments": [audio_segment],
        "metrics": metrics,
    }
