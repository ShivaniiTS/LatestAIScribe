"""
mcp_servers/asr/base.py — ASR Engine base interface.

All ASR backends implement ASREngine. The transcribe node
calls only this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class ASRConfig:
    """Per-request ASR parameters."""
    language: str = "en"
    diarize: bool = True
    max_speakers: Optional[int] = None
    min_speakers: Optional[int] = None
    hotwords: list[str] = field(default_factory=list)
    initial_prompt: Optional[str] = None
    beam_size: int = 5
    condition_on_previous_text: bool = True
    compression_ratio_threshold: float = 2.4
    no_speech_threshold: float = 0.6
    vad_threshold: float = 0.5


@dataclass
class WordAlignment:
    text: str
    start_ms: int
    end_ms: int
    confidence: float = 1.0


@dataclass
class RawSegment:
    text: str
    start_ms: int
    end_ms: int
    speaker: Optional[str] = None
    confidence: float = 1.0
    words: list[WordAlignment] = field(default_factory=list)


@dataclass
class RawTranscript:
    segments: list[RawSegment]
    engine: str = ""
    model: str = ""
    language: str = "en"
    audio_duration_ms: int = 0
    diarization_applied: bool = False


@dataclass
class PartialTranscript:
    """Streaming partial result."""
    text: str
    is_final: bool = False
    confidence: float = 1.0


@dataclass
class ASRCapabilities:
    streaming: bool = False
    batch: bool = True
    diarization: bool = True
    word_alignment: bool = True
    medical_vocab: bool = False
    max_speakers: int = 5
    supported_formats: list[str] = field(default_factory=lambda: ["wav", "mp3", "m4a", "flac", "webm"])
    max_audio_duration_s: Optional[int] = None


class ASREngine(ABC):
    """Abstract base class for all ASR engines."""

    @abstractmethod
    async def transcribe_batch(
        self,
        audio_path: str,
        config: ASRConfig,
    ) -> RawTranscript:
        """Transcribe an audio file (batch mode)."""
        ...

    async def transcribe_stream(
        self,
        audio_chunk: bytes,
        session_id: str,
        config: ASRConfig,
    ) -> AsyncIterator[PartialTranscript]:
        """Streaming transcription (not all engines support this)."""
        raise NotImplementedError("Streaming not supported by this engine")

    @abstractmethod
    async def get_capabilities(self) -> ASRCapabilities:
        """Return engine capabilities."""
        ...

    async def health_check(self) -> bool:
        """Check if the engine is healthy."""
        try:
            await self.get_capabilities()
            return True
        except Exception:
            return False

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace("Server", "").lower()
