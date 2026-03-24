"""
orchestrator/nodes/context_node.py — Load patient context from EHR or manual input.

Populates state["context"] with patient demographics, medical history,
and encounter context for use in note generation prompts.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from orchestrator.state import EncounterState

logger = logging.getLogger(__name__)


def context_node(state: EncounterState) -> dict[str, Any]:
    """Load patient context into the pipeline state."""
    start = time.time()
    encounter_id = state.get("encounter_id", "unknown")
    provider_id = state.get("provider_id", "default")

    logger.info("context_node: loading context for encounter %s", encounter_id)

    # Load provider profile
    provider_profile = None
    try:
        from config.provider_manager import load_provider
        profile = load_provider(provider_id)
        if profile:
            provider_profile = profile.model_dump()
            logger.info("context_node: loaded provider profile for %s", provider_id)
    except Exception as e:
        logger.warning("context_node: could not load provider profile: %s", e)

    # Use pre-loaded context if available, otherwise build minimal context
    context = state.get("context") or {}

    if not context:
        context = {
            "demographics": {
                "patient_id": "",
                "name": "",
                "age": None,
                "sex": "",
            },
            "encounter": {
                "visit_type": "",
                "chief_complaint": "",
            },
            "history": {
                "conditions": [],
                "medications": [],
                "allergies": [],
            },
        }

    # Try loading from EHR adapter if patient_id is available
    patient_id = context.get("demographics", {}).get("patient_id", "")
    if patient_id:
        try:
            from mcp_servers.registry import get_registry
            ehr = get_registry().get_ehr()
            ehr_data = ehr.get_patient_context(patient_id)
            if ehr_data:
                context.update(ehr_data)
                logger.info("context_node: loaded EHR data for patient %s", patient_id)
        except Exception as e:
            logger.debug("context_node: EHR not available: %s", e)

    elapsed = int((time.time() - start) * 1000)
    metrics = state.get("metrics") or {}
    metrics["context_load_ms"] = elapsed

    return {
        "status": "recording",
        "context": context,
        "provider_profile": provider_profile,
        "metrics": metrics,
    }
