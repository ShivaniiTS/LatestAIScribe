"""
orchestrator/nodes/review_node.py — Human-in-the-loop review.

Auto-approves notes by default. When MT review is needed (low confidence,
provider preference), flags the encounter for MT workflow.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from orchestrator.state import EncounterState

logger = logging.getLogger(__name__)

# Confidence threshold below which notes are flagged for MT review
MT_REVIEW_THRESHOLD = 0.7


def review_node(state: EncounterState) -> dict[str, Any]:
    """Review the generated note; auto-approve or flag for MT."""
    start = time.time()
    encounter_id = state.get("encounter_id", "unknown")

    logger.info("review_node: reviewing note for %s", encounter_id)

    note = state.get("note")
    if not note:
        return {
            "status": "failed",
            "error": "No note available for review",
            "error_stage": "review",
        }

    confidence = note.get("confidence", 0.0)
    provider_profile = state.get("provider_profile") or {}
    mt_required = provider_profile.get("style_preferences", {}).get("mt_review_required", False)

    # Decide: auto-approve or send to MT
    if confidence >= MT_REVIEW_THRESHOLD and not mt_required:
        note["is_approved"] = True
        logger.info(
            "review_node: auto-approved (confidence=%.2f >= %.2f)",
            confidence, MT_REVIEW_THRESHOLD,
        )
        status = "completed"
        mt_status = None
    else:
        reason = "low confidence" if confidence < MT_REVIEW_THRESHOLD else "provider preference"
        logger.info(
            "review_node: flagged for MT review (%s, confidence=%.2f)",
            reason, confidence,
        )
        status = "mt_review"
        mt_status = "pending"

    elapsed = int((time.time() - start) * 1000)
    metrics = state.get("metrics") or {}
    metrics["review_ms"] = elapsed

    return {
        "status": status,
        "note": note,
        "is_approved": note.get("is_approved", False),
        "mt_status": mt_status,
        "metrics": metrics,
    }
