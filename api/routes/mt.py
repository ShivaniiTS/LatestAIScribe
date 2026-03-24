"""
api/routes/mt.py — Medical Transcription (MT) review workflow routes.

MT reviewers get flagged encounters, correct notes, and submit.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.store import get_encounter, list_encounters, output_dir, update_encounter

router = APIRouter(prefix="/mt", tags=["mt"])
log = logging.getLogger("api.mt")


class MTAssignRequest(BaseModel):
    reviewer_id: str


class MTSubmitRequest(BaseModel):
    reviewer_id: str
    corrected_content: str
    comments: str = ""


@router.get("/queue")
def mt_queue():
    """List encounters pending MT review."""
    return [
        e for e in list_encounters()
        if e.get("status") in ("mt_review", "mt_assigned")
    ]


@router.post("/{encounter_id}/assign")
def assign_mt(encounter_id: str, req: MTAssignRequest):
    """Assign an encounter to an MT reviewer."""
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")
    if enc.get("status") not in ("mt_review", "mt_assigned"):
        raise HTTPException(400, f"Encounter is not in MT review (status={enc['status']})")
    update_encounter(
        encounter_id,
        status="mt_assigned",
        mt_reviewer=req.reviewer_id,
        mt_assigned_at=datetime.utcnow().isoformat(),
        message=f"Assigned to {req.reviewer_id}",
    )
    return {"encounter_id": encounter_id, "status": "mt_assigned", "reviewer": req.reviewer_id}


@router.post("/{encounter_id}/submit")
def submit_mt(encounter_id: str, req: MTSubmitRequest):
    """Submit MT corrections — replaces the note and marks as corrected."""
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")
    if enc.get("status") not in ("mt_review", "mt_assigned"):
        raise HTTPException(400, f"Encounter is not in MT review (status={enc['status']})")
    if not req.corrected_content.strip():
        raise HTTPException(400, "Corrected content cannot be empty")

    od = output_dir(encounter_id)
    current = od / "clinical_note.md"
    original = od / "clinical_note_original.md"
    # Save original before overwriting (if not already backed up)
    if not original.exists() and current.exists():
        original.write_text(current.read_text())
    # Save corrected note
    current.write_text(req.corrected_content)

    update_encounter(
        encounter_id,
        status="mt_corrected",
        mt_reviewer=req.reviewer_id,
        mt_completed_at=datetime.utcnow().isoformat(),
        mt_comments=req.comments,
        message=f"Corrected by {req.reviewer_id}",
    )
    log.info("MT correction submitted for %s by %s", encounter_id, req.reviewer_id)
    return {"encounter_id": encounter_id, "status": "mt_corrected"}


@router.get("/{encounter_id}")
def get_mt_detail(encounter_id: str):
    """Get MT review detail for an encounter."""
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")

    od = output_dir(encounter_id)
    note_path = od / "clinical_note.md"
    transcript_path = od / "transcript.txt"

    return {
        "encounter_id": encounter_id,
        "status": enc.get("status"),
        "reviewer": enc.get("mt_reviewer"),
        "note_content": note_path.read_text() if note_path.exists() else "",
        "transcript": transcript_path.read_text() if transcript_path.exists() else "",
        "provider_id": enc.get("provider_id"),
        "mode": enc.get("mode"),
    }
