"""
mcp_servers/asr/whisperx_server.py — WhisperX batch ASR engine.

Stack: faster-whisper + pyannote 3.1 + wav2vec2 alignment.
Lazy-loads models on first call to conserve GPU memory.
"""
from __future__ import annotations

import gc
import logging
import os
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from mcp_servers.asr.base import (
    ASRCapabilities,
    ASRConfig,
    ASREngine,
    PartialTranscript,
    RawSegment,
    RawTranscript,
    WordAlignment,
)

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = ["mp3", "wav", "m4a", "flac", "ogg", "webm", "mp4"]


class WhisperXServer(ASREngine):
    """Batch ASR engine backed by WhisperX (faster-whisper + pyannote diarization)."""

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        diarization: bool = True,
        hf_token: Optional[str] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        language: str = "en",
        batch_size: int = 16,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.diarization = diarization
        self.hf_token = hf_token
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.language = language
        self.batch_size = batch_size

        self._model: Any = None
        self._diarize_pipeline: Any = None
        self._align_models: dict[str, tuple[Any, Any]] = {}
        self._transcribe_lock = threading.Lock()

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "WhisperXServer":
        hf_token_env = cfg.get("hf_token_env", "HF_TOKEN")
        hf_token = os.environ.get(hf_token_env)
        return cls(
            model_size=cfg.get("model", "large-v3"),
            device=cfg.get("device", "cuda"),
            compute_type=cfg.get("compute_type", "float16"),
            diarization=cfg.get("diarization", True),
            hf_token=hf_token,
            min_speakers=cfg.get("min_speakers"),
            max_speakers=cfg.get("max_speakers"),
            language=cfg.get("language", "en"),
        )

    # ── Model loading ─────────────────────────────────────────────────────

    def _load_model(self) -> None:
        if self._model is not None:
            return
        import whisperx

        logger.info(
            "whisperx: loading model %s on %s (%s)",
            self.model_size, self.device, self.compute_type,
        )
        self._model = whisperx.load_model(
            self.model_size,
            self.device,
            compute_type=self.compute_type,
            language=self.language,
        )
        logger.info("whisperx: model loaded")

    def unload_model(self) -> None:
        """Unload model from GPU to free VRAM."""
        freed = False
        if self._model is not None:
            del self._model
            self._model = None
            freed = True
        if self._align_models:
            self._align_models.clear()
            freed = True
        if self._diarize_pipeline is not None:
            del self._diarize_pipeline
            self._diarize_pipeline = None
            freed = True
        if freed:
            gc.collect()
            if self.device == "cuda":
                import torch
                torch.cuda.empty_cache()
            logger.info("whisperx: model unloaded, GPU memory freed")

    def _load_diarize_pipeline(self) -> None:
        if self._diarize_pipeline is not None:
            return
        if not self.hf_token:
            logger.warning("whisperx: HF_TOKEN not set — diarization disabled")
            self.diarization = False
            return
        try:
            from whisperx.diarize import DiarizationPipeline
        except ImportError:
            import whisperx as _wx
            DiarizationPipeline = _wx.DiarizationPipeline

        logger.info("whisperx: loading diarization pipeline (pyannote 3.1)")
        self._diarize_pipeline = DiarizationPipeline(
            token=self.hf_token,
            device=self.device,
        )

    # ── Core transcription ────────────────────────────────────────────────

    async def transcribe_batch(
        self,
        audio_path: str,
        config: ASRConfig,
    ) -> RawTranscript:
        """Transcribe audio: load → transcribe → align → diarize → convert."""
        import whisperx

        self._load_model()
        path = str(Path(audio_path).resolve())

        logger.info("whisperx: loading audio %s", path)
        audio = whisperx.load_audio(path)

        # Step 1: Transcribe
        with self._transcribe_lock:
            orig_options = self._model.options
            orig_vad = self._model._vad_params.get("vad_onset", 0.5)

            self._model.options = replace(
                orig_options,
                beam_size=config.beam_size,
                condition_on_previous_text=config.condition_on_previous_text,
                compression_ratio_threshold=config.compression_ratio_threshold,
                no_speech_threshold=config.no_speech_threshold,
                initial_prompt=config.initial_prompt or orig_options.initial_prompt,
                hotwords=", ".join(config.hotwords) if config.hotwords else orig_options.hotwords,
            )
            if config.vad_threshold != orig_vad:
                self._model._vad_params["vad_onset"] = config.vad_threshold

            try:
                raw_result = self._model.transcribe(
                    audio,
                    batch_size=self.batch_size,
                    language=config.language or self.language,
                )
            finally:
                self._model.options = orig_options
                self._model._vad_params["vad_onset"] = orig_vad

        # Step 2: Align timestamps
        lang_code = raw_result.get("language", self.language)
        if lang_code not in self._align_models:
            self._align_models[lang_code] = whisperx.load_align_model(
                language_code=lang_code,
                device=self.device,
            )
        align_model, align_metadata = self._align_models[lang_code]
        aligned = whisperx.align(
            raw_result["segments"],
            align_model,
            align_metadata,
            audio,
            self.device,
            return_char_alignments=False,
        )

        # Step 3: Diarize (optional)
        diarization_used = False
        if config.diarize and self.diarization:
            self._load_diarize_pipeline()
            if self._diarize_pipeline is not None:
                diarize_segments = self._diarize_pipeline(
                    audio,
                    min_speakers=config.min_speakers or self.min_speakers,
                    max_speakers=config.max_speakers or self.max_speakers,
                )
                aligned = whisperx.assign_word_speakers(diarize_segments, aligned)
                diarization_used = True

        # Step 4: Convert
        segments = _convert_segments(aligned["segments"])
        audio_duration_ms = int(len(audio) / 16000 * 1000)

        if self.device == "cuda":
            import torch
            torch.cuda.empty_cache()

        return RawTranscript(
            segments=segments,
            engine="whisperx",
            model=self.model_size,
            language=raw_result.get("language", self.language),
            audio_duration_ms=audio_duration_ms,
            diarization_applied=diarization_used,
        )

    def transcribe_batch_sync(self, audio_path: str, config: ASRConfig) -> RawTranscript:
        """Blocking wrapper for sync LangGraph nodes."""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.transcribe_batch(audio_path, config))
        finally:
            loop.close()

    async def transcribe_stream(self, audio_chunk, session_id, config) -> AsyncIterator[PartialTranscript]:
        raise NotImplementedError("WhisperX is batch-only")

    async def get_capabilities(self) -> ASRCapabilities:
        return ASRCapabilities(
            streaming=False,
            batch=True,
            diarization=self.diarization,
            word_alignment=True,
            medical_vocab=False,
            max_speakers=self.max_speakers or 5,
            supported_formats=_SUPPORTED_FORMATS,
        )

    def _build_initial_prompt(self, provider_profile=None) -> Optional[str]:
        """Build initial prompt for Whisper priming with provider vocabulary."""
        if provider_profile is None:
            return None
        terms: list[str] = []
        if getattr(provider_profile, "name", None):
            terms.append(provider_profile.name)
        if getattr(provider_profile, "credentials", None):
            terms.append(provider_profile.credentials)
        custom = getattr(provider_profile, "custom_vocabulary", []) or []
        terms.extend(custom[:50])
        specialty = getattr(provider_profile, "specialty", None)
        if specialty and specialty != "general":
            try:
                from mcp_servers.data.medical_dict_server import get_dict_server
                hotwords = get_dict_server().get_hotwords(specialty, max_terms=150)
                terms.extend(hotwords)
            except Exception:
                pass
        if not terms:
            return None
        seen: set[str] = set()
        unique: list[str] = []
        for t in terms:
            if t and t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)
            if len(unique) >= 200:
                break
        return ", ".join(unique)


def _convert_segments(raw_segments: list[dict]) -> list[RawSegment]:
    segments: list[RawSegment] = []
    for seg in raw_segments:
        words = [
            WordAlignment(
                text=w.get("word", "").strip(),
                start_ms=int(w.get("start", 0) * 1000),
                end_ms=int(w.get("end", 0) * 1000),
                confidence=w.get("score", 1.0),
            )
            for w in seg.get("words", [])
        ]
        segments.append(
            RawSegment(
                text=seg.get("text", "").strip(),
                start_ms=int(seg.get("start", 0) * 1000),
                end_ms=int(seg.get("end", 0) * 1000),
                speaker=seg.get("speaker"),
                confidence=_avg_confidence(words),
                words=words,
            )
        )
    return segments


def _avg_confidence(words: list[WordAlignment]) -> float:
    if not words:
        return 1.0
    scores = [w.confidence for w in words if w.confidence is not None]
    return round(sum(scores) / len(scores), 3) if scores else 1.0
