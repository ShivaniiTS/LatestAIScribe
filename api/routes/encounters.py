"""
api/routes/encounters.py — Encounter CRUD + audio upload + pipeline trigger.

Single-server architecture: all routes run locally, no proxy needed.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from api.store import (
    audio_dir,
    create_encounter,
    get_encounter,
    list_encounters,
    output_dir,
    update_encounter,
)

router = APIRouter(prefix="/encounters", tags=["encounters"])
log = logging.getLogger("api.encounters")

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/ogg", "audio/flac", "audio/webm",
}
MAX_AUDIO_SIZE = int(os.getenv("MAX_AUDIO_SIZE_MB", "200")) * 1024 * 1024


# ── Request / Response models ────────────────────────────────────────────

class EncounterCreateRequest(BaseModel):
    provider_id: str
    patient_id: str = ""
    visit_type: str = "follow_up"
    mode: str = "dictation"  # "dictation" | "ambient"


class EncounterResponse(BaseModel):
    encounter_id: str
    status: str
    message: str


# ── List / Get ───────────────────────────────────────────────────────────

@router.get("")
def list_encounters_route(
    status: str | None = Query(None),
    mode: str | None = Query(None),
):
    """List all encounters, optionally filtered."""
    results = list_encounters()
    if status:
        results = [e for e in results if e.get("status") == status]
    if mode:
        results = [e for e in results if e.get("mode") == mode]
    return results


@router.get("/{encounter_id}")
def get_encounter_route(encounter_id: str):
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")
    return enc


@router.get("/{encounter_id}/status")
def get_status(encounter_id: str):
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")
    return {"encounter_id": encounter_id, "status": enc["status"], "message": enc.get("message", "")}


# ── Create ───────────────────────────────────────────────────────────────

@router.post("", response_model=EncounterResponse, status_code=201)
def create_encounter_route(req: EncounterCreateRequest):
    eid = str(uuid.uuid4())[:12]
    enc = create_encounter(eid, req.provider_id, req.patient_id, req.visit_type, req.mode)
    return EncounterResponse(encounter_id=eid, status=enc["status"], message=enc["message"])


# ── Upload audio + trigger pipeline ──────────────────────────────────────

@router.post("/{encounter_id}/upload")
async def upload_audio(
    encounter_id: str,
    audio: UploadFile = File(...),
):
    """Upload audio file and trigger the pipeline asynchronously."""
    enc = get_encounter(encounter_id)
    if not enc:
        raise HTTPException(404, f"Encounter '{encounter_id}' not found")

    # Validate content type
    ct = audio.content_type or ""
    if ct and ct not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            400,
            f"Unsupported audio type '{ct}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO_TYPES))}",
        )

    # Read and validate size
    content = await audio.read()
    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(400, f"Audio file too large. Max: {MAX_AUDIO_SIZE // (1024*1024)} MB")
    if len(content) < 1024:
        raise HTTPException(400, "Audio file too small — probably empty or corrupt")

    # Save to filesystem
    ad = audio_dir(encounter_id)
    ext = Path(audio.filename or "audio.mp3").suffix or ".mp3"
    audio_path = ad / f"recording{ext}"
    audio_path.write_bytes(content)

    update_encounter(encounter_id, status="processing", message="Audio received — pipeline running")

    # Launch pipeline in background
    asyncio.create_task(
        _run_pipeline(
            encounter_id=encounter_id,
            audio_path=str(audio_path),
            provider_id=enc["provider_id"],
            mode=enc["mode"],
            visit_type=enc["visit_type"],
        )
    )

    return {
        "encounter_id": encounter_id,
        "status": "processing",
        "message": "Audio received — pipeline running",
    }


# ── Audio playback ───────────────────────────────────────────────────────

@router.get("/{encounter_id}/audio")
def stream_audio(encounter_id: str):
    """Stream the recorded audio file."""
    from fastapi.responses import FileResponse

    ad = audio_dir(encounter_id)
    for ext in [".mp3", ".wav", ".ogg", ".flac", ".webm"]:
        p = ad / f"recording{ext}"
        if p.exists():
            mime = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg",
                    "flac": "audio/flac", "webm": "audio/webm"}.get(ext.lstrip("."), "audio/mpeg")
            return FileResponse(p, media_type=mime, filename=f"{encounter_id}{ext}")
    raise HTTPException(404, "Audio file not found")


# ── Results (note, transcript) ───────────────────────────────────────────

@router.get("/{encounter_id}/note")
def get_note(encounter_id: str):
    """Get the generated clinical note."""
    od = output_dir(encounter_id)
    note_path = od / "clinical_note.md"
    if not note_path.exists():
        raise HTTPException(404, "Clinical note not yet available")
    return {"encounter_id": encounter_id, "content": note_path.read_text()}


@router.get("/{encounter_id}/transcript")
def get_transcript(encounter_id: str):
    """Get the postprocessed transcript."""
    od = output_dir(encounter_id)
    tx_path = od / "transcript.txt"
    if not tx_path.exists():
        raise HTTPException(404, "Transcript not yet available")
    return {"encounter_id": encounter_id, "content": tx_path.read_text()}


# ── Pipeline runner ──────────────────────────────────────────────────────

async def _run_pipeline(
    encounter_id: str,
    audio_path: str,
    provider_id: str,
    mode: str,
    visit_type: str,
) -> None:
    """Run encounter pipeline in the background with WebSocket progress."""
    from api.ws.session_events import manager

    try:
        await asyncio.sleep(0.5)  # Let client connect WebSocket
        await manager.send_progress(encounter_id, "init", 5, "Loading provider profile…")

        from config.provider_manager import load_provider
        profile_obj = load_provider(provider_id)
        profile = profile_obj.model_dump(mode="json") if profile_obj else {}

        await manager.send_progress(encounter_id, "init", 10, "Building pipeline…")

        from orchestrator.graph import get_compiled_graph, arun_encounter

        state = {
            "encounter_id": encounter_id,
            "provider_id": provider_id,
            "recording_mode": mode,
            "visit_type": visit_type,
            "audio_file_path": audio_path,
            "provider_profile": profile,
            "errors": [],
        }

        graph = get_compiled_graph()

        await manager.send_progress(encounter_id, "transcribe", 20, "Starting transcription…")

        final = await arun_encounter(graph, state)

        await manager.send_progress(encounter_id, "transcribe", 60, "Transcription complete")

        # Free GPU memory
        try:
            from mcp_servers.registry import get_registry
            get_registry().unload_engine("asr")
        except Exception:
            pass

        # Save outputs
        od = output_dir(encounter_id)

        transcript_text = ""
        if final.get("transcript"):
            tx = final["transcript"]
            transcript_text = tx.get("full_text") or tx.get("postprocessed_text") or tx.get("raw_text", "")
            if transcript_text:
                (od / "transcript.txt").write_text(transcript_text)
                await manager.send_progress(encounter_id, "note", 70, "Transcript saved")

        note_data = final.get("note") or final.get("clinical_note")
        if note_data:
            note_text = note_data.get("full_text", "")
            if note_text:
                (od / "clinical_note.md").write_text(note_text)
                await manager.send_progress(encounter_id, "note", 85, "Clinical note generated")

        await manager.send_progress(encounter_id, "delivery", 95, "Finalizing…")

        update_encounter(encounter_id, status="complete", message="Pipeline complete")
        await manager.send_complete(encounter_id, encounter_id)
        log.info("Pipeline complete for encounter %s", encounter_id)

    except Exception as e:
        log.error("Pipeline error for encounter %s: %s", encounter_id, e)
        update_encounter(encounter_id, status="error", message=f"Pipeline error: {e}")
        await manager.send_error(encounter_id, str(e))
