"""
api/store.py — In-memory encounter store + filesystem helpers.

Backed by local filesystem at STORAGE_ROOT (default: data/).
Will be replaced by PostgreSQL queries once db is wired in.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Optional

_STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", "data"))


def audio_dir(encounter_id: str) -> Path:
    """Return (and create) the audio directory for an encounter."""
    d = _STORAGE_ROOT / "audio" / encounter_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def output_dir(encounter_id: str) -> Path:
    """Return (and create) the output directory for an encounter."""
    d = _STORAGE_ROOT / "output" / encounter_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── In-memory encounter tracking ─────────────────────────────────────────

_encounters: dict[str, dict] = {}


def create_encounter(
    encounter_id: str,
    provider_id: str,
    patient_id: str,
    visit_type: str,
    mode: str,
) -> dict:
    enc = {
        "encounter_id": encounter_id,
        "status": "pending",
        "provider_id": provider_id,
        "patient_id": patient_id,
        "visit_type": visit_type,
        "mode": mode,
        "created_at": datetime.now(UTC).isoformat(),
        "message": "Waiting for audio upload",
    }
    _encounters[encounter_id] = enc
    return enc


def get_encounter(encounter_id: str) -> Optional[dict]:
    return _encounters.get(encounter_id)


def update_encounter(encounter_id: str, **kwargs) -> Optional[dict]:
    enc = _encounters.get(encounter_id)
    if enc:
        enc.update(kwargs)
    return enc


def list_encounters() -> list[dict]:
    return list(_encounters.values())
