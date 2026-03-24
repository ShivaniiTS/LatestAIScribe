"""
api/routes/notes.py — Clinical note retrieval, editing, and approval.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.store import get_encounter, output_dir, update_encounter

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteEditRequest(BaseModel):
    content: str


class NoteApproveRequest(BaseModel):
    approved_by: str = ""
    comments: str = ""


@router.get("/{encounter_id}")
def get_note(encounter_id: str):
    """Get the clinical note for an encounter."""
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")
    od = output_dir(encounter_id)
    note_path = od / "clinical_note.md"
    if not note_path.exists():
        raise HTTPException(404, "Clinical note not yet available")
    return {
        "encounter_id": encounter_id,
        "content": note_path.read_text(),
        "status": enc.get("status"),
    }


@router.put("/{encounter_id}")
def edit_note(encounter_id: str, req: NoteEditRequest):
    """Edit / replace the clinical note content."""
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")
    if not req.content.strip():
        raise HTTPException(400, "Note content cannot be empty")
    od = output_dir(encounter_id)
    note_path = od / "clinical_note.md"
    note_path.write_text(req.content)
    update_encounter(encounter_id, status="edited", message="Note manually edited")
    return {"encounter_id": encounter_id, "status": "edited"}


@router.post("/{encounter_id}/approve")
def approve_note(encounter_id: str, req: NoteApproveRequest):
    """Mark a note as approved (by provider or MT)."""
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")
    od = output_dir(encounter_id)
    note_path = od / "clinical_note.md"
    if not note_path.exists():
        raise HTTPException(404, "No note to approve")
    update_encounter(
        encounter_id,
        status="approved",
        message=f"Approved by {req.approved_by}" if req.approved_by else "Approved",
        approved_by=req.approved_by,
        approval_comments=req.comments,
    )
    return {"encounter_id": encounter_id, "status": "approved"}
