"""
orchestrator/state.py — Pydantic models for the LangGraph pipeline state.

The EncounterState TypedDict is the single state object passed through
every node in the 6-node pipeline: CONTEXT → CAPTURE → TRANSCRIBE → NOTE → REVIEW → DELIVERY.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────

class EncounterStatus(str, enum.Enum):
    CREATED = "created"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    MT_REVIEW = "mt_review"
    COMPLETED = "completed"
    FAILED = "failed"


class RecordingMode(str, enum.Enum):
    CONVERSATION = "conversation"
    DICTATION = "dictation"


class NoteType(str, enum.Enum):
    SOAP = "soap"
    HP = "h_and_p"
    PROGRESS = "progress"
    CONSULT = "consult"


# ── Provider Profile ──────────────────────────────────────────────────────

class ProviderProfile(BaseModel):
    model_config = {"use_enum_values": True}

    provider_id: str
    name: str
    credentials: str = ""
    specialty: str = "general"
    default_note_type: NoteType = NoteType.SOAP
    default_recording_mode: RecordingMode = RecordingMode.CONVERSATION
    custom_vocabulary: list[str] = Field(default_factory=list)
    preferred_template: str = "soap_default"
    style_preferences: dict[str, Any] = Field(default_factory=dict)
    quality_scores: dict[str, float] = Field(default_factory=dict)
    asr_lora_enabled: bool = False


# ── Patient / Context ─────────────────────────────────────────────────────

class PatientDemographics(BaseModel):
    patient_id: str = ""
    name: str = ""
    age: Optional[int] = None
    sex: str = ""
    dob: str = ""
    mrn: str = ""


class EncounterContext(BaseModel):
    visit_type: str = ""
    chief_complaint: str = ""
    referring_provider: str = ""
    appointment_time: str = ""
    location: str = ""


class MedicalHistory(BaseModel):
    conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    surgeries: list[str] = Field(default_factory=list)
    family_history: list[str] = Field(default_factory=list)
    social_history: dict[str, str] = Field(default_factory=dict)


class ContextPacket(BaseModel):
    demographics: PatientDemographics = Field(default_factory=PatientDemographics)
    encounter: EncounterContext = Field(default_factory=EncounterContext)
    history: MedicalHistory = Field(default_factory=MedicalHistory)
    previous_notes: list[str] = Field(default_factory=list)
    raw_context: dict[str, Any] = Field(default_factory=dict)


# ── Audio ─────────────────────────────────────────────────────────────────

class AudioSegment(BaseModel):
    audio_file_path: str
    channel: str = "mixed"  # mixed | provider | patient
    duration_ms: int = 0
    sample_rate: int = 16000
    format: str = "wav"


# ── Transcript ────────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    text: str
    start_ms: int = 0
    end_ms: int = 0
    speaker: Optional[str] = None
    confidence: float = 1.0
    words: list[dict[str, Any]] = Field(default_factory=list)


class UnifiedTranscript(BaseModel):
    segments: list[TranscriptSegment] = Field(default_factory=list)
    full_text: str = ""
    engine: str = "whisperx"
    model: str = "large-v3"
    language: str = "en"
    audio_duration_ms: int = 0
    word_count: int = 0
    avg_confidence: float = 0.0
    diarization_applied: bool = False
    postprocessor_applied: bool = False
    postprocessor_metrics: dict[str, Any] = Field(default_factory=dict)


# ── Clinical Note ─────────────────────────────────────────────────────────

class NoteSection(BaseModel):
    label: str
    content: str
    confidence: float = 1.0


class CodingSuggestion(BaseModel):
    code: str
    system: str = "ICD-10"
    description: str = ""
    confidence: float = 0.0


class ClinicalNote(BaseModel):
    note_type: NoteType = NoteType.SOAP
    full_text: str = ""
    sections: list[NoteSection] = Field(default_factory=list)
    llm_model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    confidence: float = 0.0
    coding_suggestions: list[CodingSuggestion] = Field(default_factory=list)
    version: int = 1
    is_approved: bool = False


# ── Corrections ───────────────────────────────────────────────────────────

class Correction(BaseModel):
    field: str
    original: str
    corrected: str
    source: str = "mt"  # mt | provider | auto
    timestamp: str = ""


# ── Metrics ───────────────────────────────────────────────────────────────

class EncounterMetrics(BaseModel):
    total_duration_ms: int = 0
    context_load_ms: int = 0
    capture_ms: int = 0
    transcription_ms: int = 0
    note_generation_ms: int = 0
    review_ms: int = 0
    delivery_ms: int = 0


# ── Pipeline State (TypedDict for LangGraph) ─────────────────────────────

from typing import TypedDict


class EncounterState(TypedDict, total=False):
    # Identity
    encounter_id: str
    provider_id: str
    provider_profile: Optional[dict]

    # Status
    status: str
    recording_mode: str
    note_type: str

    # Context
    context: Optional[dict]

    # Audio
    audio_segments: list[dict]
    audio_file_path: Optional[str]

    # Transcript
    transcript: Optional[dict]

    # Note
    note: Optional[dict]
    clinical_note: Optional[dict]
    visit_type: str

    # Review
    corrections: list[dict]
    is_approved: bool

    # Delivery
    delivered: bool
    delivery_target: str

    # MT
    mt_job_id: Optional[str]
    mt_status: Optional[str]

    # Metrics
    metrics: Optional[dict]

    # Error handling
    errors: list[str]
    error: Optional[str]
    error_stage: Optional[str]
