"""
mt/sorting.py — MT job assignment and prioritization.

Jobs are sorted by:
  1. Priority (urgent > normal > low)
  2. Age (oldest first)
  3. Provider preference (some providers always require MT)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from api.store import get_encounter, list_encounters, update_encounter

log = logging.getLogger("mt.sorting")

PRIORITY_MAP = {
    "urgent": 0,
    "normal": 1,
    "low": 2,
}


def get_mt_queue() -> list[dict]:
    """Get the sorted MT review queue."""
    pending = [
        e for e in list_encounters()
        if e.get("status") in ("mt_review", "mt_assigned")
    ]
    return sorted(pending, key=_sort_key)


def _sort_key(enc: dict) -> tuple:
    priority = PRIORITY_MAP.get(enc.get("mt_priority", "normal"), 1)
    created = enc.get("created_at", "")
    return (priority, created)


def assign_next(reviewer_id: str) -> Optional[dict]:
    """Assign the highest-priority unassigned job to a reviewer."""
    queue = get_mt_queue()
    unassigned = [e for e in queue if e.get("status") == "mt_review"]
    if not unassigned:
        return None

    enc = unassigned[0]
    update_encounter(
        enc["encounter_id"],
        status="mt_assigned",
        mt_reviewer=reviewer_id,
        mt_assigned_at=datetime.utcnow().isoformat(),
    )
    log.info("Assigned %s to reviewer %s", enc["encounter_id"], reviewer_id)
    return get_encounter(enc["encounter_id"])


def get_reviewer_workload(reviewer_id: str) -> list[dict]:
    """Get all encounters assigned to a specific reviewer."""
    return [
        e for e in list_encounters()
        if e.get("mt_reviewer") == reviewer_id
        and e.get("status") in ("mt_assigned", "mt_corrected")
    ]
