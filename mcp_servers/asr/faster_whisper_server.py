"""
mcp_servers/asr/faster_whisper_server.py – CPU-compatible ASR using faster-whisper.

Uses CTranslate2 under the hood; works on CPU (int8) or GPU (float16).
Default config: model=base, device=cpu, compute_type=int8 — no CUDA required.

Model is downloaded on first call and cached in WHISPER_CACHE_DIR
(defaults to /tmp/whisper_models inside Docker).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from mcp_servers.asr.base import (
    ASRCapabilities,
    ASRConfig,
    ASREngine,
    RawSegment,
    RawTranscript,
    WordAlignment,
)

log = logging.getLogger(__name__)

# Single dedicated thread keeps the model loaded between requests
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="faster-whisper")


class FasterWhisperServer(ASREngine):
    """
    ASR engine backed by faster-whisper (CTranslate2).

    Works on CPU with int8 quantisation — no GPU required.
    The Whisper model is downloaded from HuggingFace Hub on first use
    and cached in ``download_root`` (set WHISPER_CACHE_DIR env var to persist
    it across container restarts by mounting that path as a Docker volume).
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        cache_dir: str | None = None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cache_dir = cache_dir or os.getenv("WHISPER_CACHE_DIR", "/tmp/whisper_models")
        self._model = None

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "FasterWhisperServer":
        return cls(
            model_size=cfg.get("model", "base"),
            device=cfg.get("device", "cpu"),
            compute_type=cfg.get("compute_type", "int8"),
            cache_dir=cfg.get("cache_dir"),
        )

    # ── Model lifecycle ────────────────────────────────────────────────────

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            log.info(
                "faster_whisper: loading model=%s device=%s compute_type=%s cache=%s",
                self.model_size, self.device, self.compute_type, self.cache_dir,
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=self.cache_dir,
            )
            log.info("faster_whisper: model loaded successfully")
        return self._model

    def unload_model(self) -> None:
        self._model = None
        log.info("faster_whisper: model unloaded")

    # ── Transcription ──────────────────────────────────────────────────────

    def _transcribe_sync(self, audio_path: str, config: ASRConfig) -> RawTranscript:
        model = self._load_model()
        t0 = time.time()

        segments_gen, info = model.transcribe(
            audio_path,
            language=config.language or "en",
            beam_size=min(config.beam_size, 5),
            initial_prompt=config.initial_prompt,
            word_timestamps=True,
            condition_on_previous_text=config.condition_on_previous_text,
            no_speech_threshold=config.no_speech_threshold,
            compression_ratio_threshold=config.compression_ratio_threshold,
        )

        raw_segments: list[RawSegment] = []
        for seg in segments_gen:
            words = [
                WordAlignment(
                    text=w.word,
                    start_ms=int(w.start * 1000),
                    end_ms=int(w.end * 1000),
                    confidence=float(w.probability),
                )
                for w in (seg.words or [])
            ]
            raw_segments.append(
                RawSegment(
                    text=seg.text.strip(),
                    start_ms=int(seg.start * 1000),
                    end_ms=int(seg.end * 1000),
                    confidence=float(seg.avg_logprob),
                    words=words,
                )
            )

        elapsed_s = time.time() - t0
        audio_duration_ms = int((info.duration or 0) * 1000)
        log.info(
            "faster_whisper: transcribed %d segments in %.1fs (audio=%.1fs, rtf=%.2fx)",
            len(raw_segments),
            elapsed_s,
            info.duration or 0,
            elapsed_s / max(info.duration or 1, 0.001),
        )

        return RawTranscript(
            segments=raw_segments,
            engine="faster-whisper",
            model=self.model_size,
            language=info.language or config.language,
            audio_duration_ms=audio_duration_ms,
            diarization_applied=False,
        )

    async def transcribe_batch(self, audio_path: str, config: ASRConfig) -> RawTranscript:
        """Async transcription — runs in dedicated thread pool to avoid blocking."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, self._transcribe_sync, audio_path, config
        )

    def transcribe_batch_sync(self, audio_path: str, config: ASRConfig) -> RawTranscript:
        """Sync transcription — called by transcribe_node when no event loop."""
        return self._transcribe_sync(audio_path, config)

    async def get_capabilities(self) -> ASRCapabilities:
        return ASRCapabilities(
            streaming=False,
            batch=True,
            diarization=False,
            word_alignment=True,
            medical_vocab=False,
            max_speakers=1,
            supported_formats=["wav", "mp3", "m4a", "flac", "webm", "ogg"],
        )
