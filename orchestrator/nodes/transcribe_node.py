"""
orchestrator/nodes/transcribe_node.py — ASR transcription with postprocessing.

Calls WhisperX via the MCP registry, applies MedASR postprocessor,
and stores the unified transcript in state.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from orchestrator.state import EncounterState

logger = logging.getLogger(__name__)


def transcribe_node(state: EncounterState) -> dict[str, Any]:
    """Transcribe audio using WhisperX and apply postprocessing."""
    start = time.time()
    encounter_id = state.get("encounter_id", "unknown")

    logger.info("transcribe_node: starting transcription for %s", encounter_id)

    # Get audio path
    audio_path = state.get("audio_file_path")
    segments = state.get("audio_segments", [])
    if segments and not audio_path:
        audio_path = segments[0].get("audio_file_path")

    if not audio_path:
        return {
            "status": "failed",
            "error": "No audio path available for transcription",
            "error_stage": "transcribe",
        }

    # Get ASR engine from registry
    try:
        from mcp_servers.registry import get_registry
        from mcp_servers.asr.base import ASRConfig

        registry = get_registry()
        asr = registry.get_asr()

        # Build ASR config with provider-specific hotwords
        provider_profile = state.get("provider_profile")
        hotwords = []
        initial_prompt = None

        if provider_profile:
            hotwords = provider_profile.get("custom_vocabulary", [])
            specialty = provider_profile.get("specialty", "general")

            # Try to get specialty-specific hotwords
            try:
                from mcp_servers.data.medical_dict_server import get_dict_server
                dict_server = get_dict_server()
                specialty_hotwords = dict_server.get_hotwords(specialty, max_terms=150)
                hotwords.extend(specialty_hotwords)
            except Exception:
                pass

            # Build initial prompt for Whisper priming
            if hasattr(asr, "_build_initial_prompt"):
                from orchestrator.state import ProviderProfile
                profile_obj = ProviderProfile(**provider_profile)
                initial_prompt = asr._build_initial_prompt(profile_obj)

        config = ASRConfig(
            language="en",
            diarize=state.get("recording_mode") in ("conversation", "ambient"),
            hotwords=hotwords,
            initial_prompt=initial_prompt,
        )

        # Transcribe
        logger.info("transcribe_node: calling ASR engine for %s", audio_path)
        if hasattr(asr, "transcribe_batch_sync"):
            raw_transcript = asr.transcribe_batch_sync(audio_path, config)
        else:
            import asyncio
            raw_transcript = asyncio.get_event_loop().run_until_complete(
                asr.transcribe_batch(audio_path, config)
            )

        # Convert to dict
        raw_text = " ".join(seg.text for seg in raw_transcript.segments)
        transcript_dict = {
            "segments": [
                {
                    "text": seg.text,
                    "start_ms": seg.start_ms,
                    "end_ms": seg.end_ms,
                    "speaker": seg.speaker,
                    "confidence": seg.confidence,
                    "words": [
                        {
                            "text": w.text,
                            "start_ms": w.start_ms,
                            "end_ms": w.end_ms,
                            "confidence": w.confidence,
                        }
                        for w in (seg.words or [])
                    ],
                }
                for seg in raw_transcript.segments
            ],
            "full_text": raw_text,
            "engine": raw_transcript.engine,
            "model": raw_transcript.model,
            "language": raw_transcript.language,
            "audio_duration_ms": raw_transcript.audio_duration_ms,
            "word_count": len(raw_text.split()),
            "avg_confidence": _avg_confidence(raw_transcript.segments),
            "diarization_applied": raw_transcript.diarization_applied,
            "postprocessor_applied": False,
            "postprocessor_metrics": {},
        }

    except Exception as e:
        logger.error("transcribe_node: ASR failed for %s: %s", encounter_id, e)
        return {
            "status": "failed",
            "error": f"Transcription failed: {e}",
            "error_stage": "transcribe",
        }

    # Apply postprocessor
    try:
        transcript_dict = _apply_postprocessor(transcript_dict)
    except Exception as e:
        logger.warning("transcribe_node: postprocessor failed: %s", e)

    # Unload ASR model to free GPU for LLM
    try:
        registry.unload_engine("asr")
        logger.info("transcribe_node: ASR model unloaded to free GPU")
    except Exception:
        pass

    elapsed = int((time.time() - start) * 1000)
    metrics = state.get("metrics") or {}
    metrics["transcription_ms"] = elapsed

    logger.info(
        "transcribe_node: done — %d words, confidence=%.2f, %dms",
        transcript_dict.get("word_count", 0),
        transcript_dict.get("avg_confidence", 0),
        elapsed,
    )

    return {
        "status": "generating",
        "transcript": transcript_dict,
        "metrics": metrics,
    }


def _apply_postprocessor(transcript: dict) -> dict:
    """Apply the MedASR rule-based postprocessor to the transcript."""
    from postprocessor.medasr_postprocessor import MedASRPostprocessor

    raw_text = transcript.get("full_text", "")
    if not raw_text.strip():
        return transcript

    processor = MedASRPostprocessor()
    result = processor.process(raw_text)

    transcript["full_text"] = result.cleaned_text
    transcript["postprocessor_applied"] = True
    transcript["postprocessor_metrics"] = result.metrics_dict()

    # Also update individual segments if postprocessed text changed
    if result.cleaned_text != raw_text:
        # For now, keep segment-level text as-is; full_text is authoritative
        pass

    return transcript


def _avg_confidence(segments) -> float:
    """Calculate average confidence across all segments."""
    if not segments:
        return 0.0
    confidences = [s.confidence for s in segments if s.confidence is not None]
    return round(sum(confidences) / len(confidences), 3) if confidences else 0.0
