"""
api/routes/scribe.py – MDCO-compatible AI Scribe endpoints.

Matches the request/response shapes expected by the MDCO-AI-Scribe-V2 frontend:
  POST /api/upload-audio          multipart audio + demographics
  POST /api/upload-demographics-v2  JSON demographics only
  GET  /api/soap-history          list of encounters for the history page
  GET  /api/soap-notes/poll       poll for completed SOAP notes
  POST /patients/provider-date    search patients by provider + date (stub)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.store import (
    audio_dir,
    create_encounter,
    get_encounter,
    list_encounters,
    update_encounter,
)

router = APIRouter(tags=["scribe"])
log = logging.getLogger("api.scribe")

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/webm", "audio/ogg", "audio/flac", "application/octet-stream",
}

# ---------------------------------------------------------------------------
# Stub patient data (4 patients returned for any search)
# ---------------------------------------------------------------------------
_STUB_PATIENTS = [
    {
        "guarantor_id": "G100001",
        "appointment_id": "A200001",
        "account_number": "100001",
        "patient_name": "Smith, John",
        "case_name": "MVA 2025",
        "case_number": "C300001",
        "location_name": "COLUMBIA",
        "encounter_id": "ENC-001",
        "injury_date": "2025-01-15",
        "d_o_b": "1978-04-22",
    },
    {
        "guarantor_id": "G100002",
        "appointment_id": "A200002",
        "account_number": "100002",
        "patient_name": "Johnson, Mary",
        "case_name": "WC 2024",
        "case_number": "C300002",
        "location_name": "BETHESDA",
        "encounter_id": "ENC-002",
        "injury_date": "2024-11-03",
        "d_o_b": "1990-08-17",
    },
    {
        "guarantor_id": "G100003",
        "appointment_id": "A200003",
        "account_number": "100003",
        "patient_name": "Williams, Robert",
        "case_name": "MVA 2025",
        "case_number": "C300003",
        "location_name": "ROCKVILLE",
        "encounter_id": "ENC-003",
        "injury_date": "2025-02-28",
        "d_o_b": "1965-12-05",
    },
    {
        "guarantor_id": "G100004",
        "appointment_id": "A200004",
        "account_number": "100004",
        "patient_name": "Brown, Patricia",
        "case_name": "Slip & Fall 2025",
        "case_number": "C300004",
        "location_name": "SILVER SPRING",
        "encounter_id": "ENC-004",
        "injury_date": "2025-03-10",
        "d_o_b": "1982-06-30",
    },
]


# ---------------------------------------------------------------------------
# POST /patients/provider-date  – stub patient search
# ---------------------------------------------------------------------------
class PatientSearchRequest(BaseModel):
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    appointment_date: Optional[str] = None
    date: Optional[str] = None


@router.get("/patients/appointment/{appointment_id}")
async def get_patient_by_appointment(appointment_id: str):
    """Return stub patient data for a given appointment_id."""
    # Look for a matching stub patient first
    for p in _STUB_PATIENTS:
        if p["appointment_id"] == appointment_id:
            return {**p, "patient_full_name": p["patient_name"]}
    # Fall back to a generic record so the frontend doesn't break
    raise HTTPException(404, f"Appointment '{appointment_id}' not found")


@router.post("/patients/provider-date")
async def search_patients(req: PatientSearchRequest):
    """Return stub patients for any provider/date combination."""
    provider = req.provider_name or req.provider_id or "Unknown"
    date_val = req.appointment_date or req.date or datetime.now(UTC).strftime("%Y-%m-%d")
    patients = []
    for p in _STUB_PATIENTS:
        row = dict(p)
        row["provider_name"] = provider
        row["appointment_date"] = date_val
        patients.append(row)
    return patients


# ---------------------------------------------------------------------------
# POST /api/upload-audio  – multipart audio upload + pipeline trigger
# ---------------------------------------------------------------------------
@router.post("/api/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    guarantor_id: str = Form(""),
    appointment_id: str = Form(""),
    case_id: str = Form(""),
    encounter_id: str = Form(""),
    audio_type: str = Form("conversation"),
    demographics: str = Form("{}"),
):
    # Generate encounter_id if not provided
    if not encounter_id:
        encounter_id = str(uuid.uuid4())

    # Basic content-type guard (allow octet-stream for binary uploads)
    ct = (file.content_type or "").lower()
    if ct and ct not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(415, f"Unsupported audio type: {ct}")

    # Parse demographics JSON safely
    try:
        demo_data = json.loads(demographics) if demographics else {}
    except json.JSONDecodeError:
        demo_data = {}

    # Save audio file
    enc_audio_dir = audio_dir(encounter_id)
    audio_filename = f"{audio_type}_{encounter_id}.mp3"
    audio_path = enc_audio_dir / audio_filename
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty audio file received")
    audio_path.write_bytes(content)
    log.info("Audio saved: %s (%d bytes)", audio_path, len(content))

    # Create or update encounter in store
    enc = get_encounter(encounter_id)
    if enc is None:
        patient_name = demo_data.get("patient_name", "")
        provider_name = demo_data.get("provider_name", demo_data.get("rendering_provider", ""))
        enc = create_encounter(
            encounter_id=encounter_id,
            provider_id=provider_name,
            patient_id=patient_name,
            visit_type=audio_type,
            mode="scribe",
        )
        update_encounter(
            encounter_id,
            guarantor_id=guarantor_id,
            appointment_id=appointment_id,
            case_id=case_id,
            patient_name=patient_name,
            provider_name=provider_name,
            demographics=demo_data,
            audio_path=str(audio_path),
            audio_type=audio_type,
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
        )
    else:
        update_encounter(
            encounter_id,
            audio_path=str(audio_path),
            audio_type=audio_type,
            has_audio=True,
        )

    # Fire-and-forget pipeline run
    asyncio.create_task(_run_pipeline(encounter_id, str(audio_path), demo_data))

    return {
        "success": True,
        "data": {
            "encounter_id": encounter_id,
            "status": "processing",
            "message": "Audio received. Processing has started.",
        },
    }


async def _run_pipeline(encounter_id: str, audio_path: str, demographics: dict):
    """Trigger the AI pipeline asynchronously."""
    update_encounter(encounter_id, status="processing", has_audio=True)
    try:
        from orchestrator.graph import run_pipeline
        result = await run_pipeline(
            audio_path=audio_path,
            encounter_id=encounter_id,
            provider_id=demographics.get("provider_id", "default"),
            patient_id=demographics.get("patient_name", "unknown"),
            visit_type=demographics.get("audio_type", "conversation"),
            mode="scribe",
        )
        update_encounter(
            encounter_id,
            status="completed",
            soap_note=result.get("soap_note"),
            transcript=result.get("transcript"),
        )
        log.info("Pipeline completed for %s", encounter_id)
    except Exception as exc:
        log.exception("Pipeline failed for %s: %s", encounter_id, exc)
        update_encounter(encounter_id, status="error", message=str(exc))


# ---------------------------------------------------------------------------
# POST /api/upload-demographics-v2  – save demographics without audio
# ---------------------------------------------------------------------------
class DemographicsV2(BaseModel):
    guarantor_id: Optional[str] = None
    appointment_id: Optional[str] = None
    case_id: Optional[str] = None
    encounter_id: Optional[str] = None
    demographics: Optional[dict] = None
    patient_name: Optional[str] = None
    provider_name: Optional[str] = None
    rendering_provider: Optional[str] = None


@router.post("/api/upload-demographics-v2")
async def upload_demographics_v2(req: DemographicsV2):
    encounter_id = req.encounter_id or str(uuid.uuid4())
    enc = get_encounter(encounter_id)
    if enc is None:
        create_encounter(
            encounter_id=encounter_id,
            provider_id=req.provider_name or req.rendering_provider or "",
            patient_id=req.patient_name or "",
            visit_type="conversation",
            mode="scribe",
        )
    update_encounter(
        encounter_id,
        guarantor_id=req.guarantor_id,
        appointment_id=req.appointment_id,
        case_id=req.case_id,
        patient_name=req.patient_name,
        provider_name=req.provider_name or req.rendering_provider,
        demographics=req.demographics or {},
        date=datetime.now(UTC).strftime("%Y-%m-%d"),
    )
    return {"success": True, "encounter_id": encounter_id}


# ---------------------------------------------------------------------------
# GET /api/soap-history  – all encounters formatted for SoapHistoryPage
# ---------------------------------------------------------------------------
@router.get("/api/soap-history")
async def soap_history():
    encounters = list_encounters()
    result = []
    for enc in encounters:
        result.append({
            "encounter_id": enc.get("encounter_id"),
            "patient_name": enc.get("patient_name") or enc.get("patient_id") or "Unknown",
            "appointment_date": enc.get("date") or enc.get("created_at", "")[:10],
            "account_number": enc.get("guarantor_id", ""),
            "case_name": enc.get("case_id", ""),
            "provider_name": enc.get("provider_name") or enc.get("provider_id") or "",
            "location_name": enc.get("location_name", ""),
            "has_audio": bool(enc.get("audio_path") or enc.get("has_audio")),
            "soap_note": enc.get("soap_note"),
            "status": enc.get("status", "processing"),
            "created_at": enc.get("created_at", ""),
        })
    # Most recent first
    result.sort(key=lambda e: e["created_at"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# GET /api/soap-notes/poll  – poll for new/updated soap notes
# ---------------------------------------------------------------------------
@router.get("/api/soap-notes/poll")
async def poll_soap_notes(since: Optional[str] = Query(None)):
    encounters = list_encounters()
    completed = [
        {
            "encounter_id": e["encounter_id"],
            "status": e.get("status"),
            "soap_note": e.get("soap_note"),
            "patient_name": e.get("patient_name") or e.get("patient_id"),
        }
        for e in encounters
        if e.get("status") in ("completed", "error")
    ]
    return {"notes": completed, "timestamp": datetime.now(UTC).isoformat()}
