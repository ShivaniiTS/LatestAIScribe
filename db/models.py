"""
db/models.py — SQLAlchemy async models for PostgreSQL.

Tables:
  encounters    — Core encounter records with status tracking
  audio_files   — Audio file metadata (paths stored on local filesystem)
  transcripts   — ASR transcripts with confidence scores
  clinical_notes — Generated clinical notes with versioning
  providers     — Provider profiles (synced from YAML)
  mt_jobs       — Medical transcriptionist review jobs
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


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


class NoteType(str, enum.Enum):
    SOAP = "soap"
    HP = "h_and_p"
    PROGRESS = "progress"
    CONSULT = "consult"


class MTJobStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


class RecordingMode(str, enum.Enum):
    CONVERSATION = "conversation"
    DICTATION = "dictation"


# ── Encounters ────────────────────────────────────────────────────────────

class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[str] = mapped_column(String(100), ForeignKey("providers.id"), nullable=False)
    patient_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    patient_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[EncounterStatus] = mapped_column(
        Enum(EncounterStatus), default=EncounterStatus.CREATED, nullable=False
    )
    recording_mode: Mapped[RecordingMode] = mapped_column(
        Enum(RecordingMode), default=RecordingMode.CONVERSATION, nullable=False
    )
    note_type: Mapped[NoteType] = mapped_column(
        Enum(NoteType), default=NoteType.SOAP, nullable=False
    )
    specialty: Mapped[str] = mapped_column(String(100), default="general")
    context_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    audio_files: Mapped[list["AudioFile"]] = relationship(back_populates="encounter", cascade="all, delete-orphan")
    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="encounter", cascade="all, delete-orphan")
    clinical_notes: Mapped[list["ClinicalNote"]] = relationship(back_populates="encounter", cascade="all, delete-orphan")
    mt_jobs: Mapped[list["MTJob"]] = relationship(back_populates="encounter", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_encounters_provider_id", "provider_id"),
        Index("ix_encounters_status", "status"),
        Index("ix_encounters_created_at", "created_at"),
    )


# ── Audio Files ───────────────────────────────────────────────────────────

class AudioFile(Base):
    __tablename__ = "audio_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), default="mixed")  # mixed, provider, patient
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), default="audio/wav")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    encounter: Mapped["Encounter"] = relationship(back_populates="audio_files")


# ── Transcripts ───────────────────────────────────────────────────────────

class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False
    )
    engine: Mapped[str] = mapped_column(String(50), default="whisperx")
    model: Mapped[str] = mapped_column(String(100), default="large-v3")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    postprocessed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diarization_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    postprocessor_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    encounter: Mapped["Encounter"] = relationship(back_populates="transcripts")

    __table_args__ = (
        Index("ix_transcripts_encounter_id", "encounter_id"),
    )


# ── Clinical Notes ────────────────────────────────────────────────────────

class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    note_type: Mapped[NoteType] = mapped_column(Enum(NoteType), nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    sections_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_model: Mapped[str] = mapped_column(String(100), default="qwen2.5:14b")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mt_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    encounter: Mapped["Encounter"] = relationship(back_populates="clinical_notes")

    __table_args__ = (
        Index("ix_clinical_notes_encounter_id", "encounter_id"),
    )


# ── Providers ─────────────────────────────────────────────────────────────

class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credentials: Mapped[str | None] = mapped_column(String(100), nullable=True)
    specialty: Mapped[str] = mapped_column(String(100), default="general")
    default_note_type: Mapped[NoteType] = mapped_column(Enum(NoteType), default=NoteType.SOAP)
    custom_vocabulary: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── MT Jobs ───────────────────────────────────────────────────────────────

class MTJob(Base):
    __tablename__ = "mt_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False
    )
    note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_notes.id"), nullable=True
    )
    status: Mapped[MTJobStatus] = mapped_column(
        Enum(MTJobStatus), default=MTJobStatus.PENDING, nullable=False
    )
    assigned_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrections_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sftp_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    encounter: Mapped["Encounter"] = relationship(back_populates="mt_jobs")

    __table_args__ = (
        Index("ix_mt_jobs_status", "status"),
        Index("ix_mt_jobs_encounter_id", "encounter_id"),
    )


# ── Database Session ──────────────────────────────────────────────────────

_engine = None
_session_factory = None


def get_engine(database_url: str | None = None):
    """Get or create the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        import os
        url = database_url or os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://aiscribe:aiscribe@localhost:5432/aiscribe"
        )
        _engine = create_async_engine(url, echo=False, pool_size=10, max_overflow=20)
    return _engine


def get_session_factory(database_url: str | None = None):
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine(database_url)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def init_db(database_url: str | None = None):
    """Create all tables."""
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close the engine connection pool."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
