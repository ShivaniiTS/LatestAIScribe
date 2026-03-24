"""
orchestrator/nodes/note_node.py — LLM clinical note generation.

Assembles the prompt from transcript + context + provider preferences,
calls Ollama (qwen2.5:14b), and parses the structured clinical note.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from orchestrator.state import EncounterState

logger = logging.getLogger(__name__)


def note_node(state: EncounterState) -> dict[str, Any]:
    """Generate a clinical note from the transcript using the LLM."""
    start = time.time()
    encounter_id = state.get("encounter_id", "unknown")
    note_type = state.get("note_type", "soap")

    logger.info("note_node: generating %s note for %s", note_type, encounter_id)

    transcript = state.get("transcript")
    if not transcript or not transcript.get("full_text", "").strip():
        return {
            "status": "failed",
            "error": "No transcript available for note generation",
            "error_stage": "note",
        }

    # Assemble the prompt
    context = state.get("context") or {}
    provider_profile = state.get("provider_profile") or {}
    recording_mode = state.get("recording_mode", "conversation")

    system_prompt = _build_system_prompt(
        note_type=note_type,
        context=context,
        provider_profile=provider_profile,
        recording_mode=recording_mode,
    )

    transcript_text = transcript["full_text"]
    user_message = f"Generate a {note_type.upper()} note from the following transcript:\n\n{transcript_text}"

    # Call LLM
    try:
        from mcp_servers.registry import get_registry
        from mcp_servers.llm.base import LLMConfig, LLMMessage

        registry = get_registry()
        llm = registry.get_llm()

        config = LLMConfig(
            model="qwen2.5:14b",
            temperature=0.1,
            max_tokens=4096,
        )

        messages = [LLMMessage(role="user", content=user_message)]

        if hasattr(llm, "generate_sync"):
            response = llm.generate_sync(system_prompt, messages, config, task="note_generation")
        else:
            import asyncio
            response = asyncio.get_event_loop().run_until_complete(
                llm.generate(system_prompt, messages, config)
            )

        raw_note = response.content

        # Check for LLM refusal
        if _is_refusal(raw_note):
            logger.warning("note_node: LLM refused to generate note for %s", encounter_id)
            return {
                "status": "failed",
                "error": "LLM refused to generate clinical note (safety filter triggered)",
                "error_stage": "note",
            }

        # Parse sections
        sections = _parse_note_sections(raw_note, note_type)

        # Strip PHI headers if present
        cleaned_note = _strip_phi_headers(raw_note)

        note_dict = {
            "note_type": note_type,
            "full_text": cleaned_note,
            "sections": [s for s in sections],
            "llm_model": response.model,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "confidence": _estimate_confidence(sections, transcript),
            "version": 1,
            "is_approved": False,
        }

    except Exception as e:
        logger.error("note_node: LLM failed for %s: %s", encounter_id, e)
        return {
            "status": "failed",
            "error": f"Note generation failed: {e}",
            "error_stage": "note",
        }

    elapsed = int((time.time() - start) * 1000)
    metrics = state.get("metrics") or {}
    metrics["note_generation_ms"] = elapsed

    logger.info(
        "note_node: done — %d sections, %d tokens, %dms",
        len(sections), (note_dict.get("prompt_tokens", 0) + note_dict.get("completion_tokens", 0)),
        elapsed,
    )

    return {
        "status": "reviewing",
        "note": note_dict,
        "metrics": metrics,
    }


def _build_system_prompt(
    note_type: str,
    context: dict,
    provider_profile: dict,
    recording_mode: str,
) -> str:
    """Build the system prompt from templates and context."""
    # Try to load YAML prompt template
    try:
        from config.loader import load_prompt
        prompt_data = load_prompt("note_generation")
        template = prompt_data.get("templates", {}).get(note_type, {})
        base_prompt = template.get("system_prompt", "")
    except Exception:
        base_prompt = ""

    if not base_prompt:
        base_prompt = _default_system_prompt(note_type)

    # Assemble context block
    context_block = _assemble_context_block(context)
    vocab_block = _assemble_vocab_block(provider_profile)
    style_block = _assemble_style_block(provider_profile, note_type)

    parts = [base_prompt]
    if context_block:
        parts.append(f"\n\n## Patient Context\n{context_block}")
    if vocab_block:
        parts.append(f"\n\n## Medical Vocabulary\n{vocab_block}")
    if style_block:
        parts.append(f"\n\n## Style Preferences\n{style_block}")

    if recording_mode == "dictation":
        parts.append(
            "\n\nNote: This transcript is from physician dictation (single speaker). "
            "There is no patient dialogue to extract — use only the dictated content."
        )

    return "\n".join(parts)


def _default_system_prompt(note_type: str) -> str:
    """Fallback system prompt if YAML template is not found."""
    section_map = {
        "soap": "SUBJECTIVE, OBJECTIVE, ASSESSMENT, PLAN",
        "h_and_p": "CHIEF COMPLAINT, HPI, ROS, PAST MEDICAL HISTORY, MEDICATIONS, ALLERGIES, PHYSICAL EXAM, ASSESSMENT, PLAN",
        "progress": "SUBJECTIVE, OBJECTIVE, ASSESSMENT, PLAN",
        "consult": "REASON FOR CONSULT, HPI, EXAMINATION, IMPRESSION, RECOMMENDATIONS",
    }
    sections = section_map.get(note_type, "SUBJECTIVE, OBJECTIVE, ASSESSMENT, PLAN")

    return (
        f"You are a medical documentation specialist. Generate a structured "
        f"{note_type.upper()} clinical note from the provided transcript.\n\n"
        f"Required sections: {sections}\n\n"
        f"Rules:\n"
        f"- Use only information present in the transcript\n"
        f"- Do NOT hallucinate or infer findings not mentioned\n"
        f"- Use standard medical terminology\n"
        f"- Be concise but thorough\n"
        f"- Format each section with a header like: **SUBJECTIVE:**\n"
        f"- If information for a section is not available, write 'Not documented'"
    )


def _assemble_context_block(context: dict) -> str:
    """Build context string from patient data."""
    parts = []
    demo = context.get("demographics", {})
    if demo.get("name"):
        parts.append(f"Patient: {demo['name']}")
    if demo.get("age"):
        parts.append(f"Age: {demo['age']}")
    if demo.get("sex"):
        parts.append(f"Sex: {demo['sex']}")

    encounter = context.get("encounter", {})
    if encounter.get("chief_complaint"):
        parts.append(f"Chief Complaint: {encounter['chief_complaint']}")
    if encounter.get("visit_type"):
        parts.append(f"Visit Type: {encounter['visit_type']}")

    history = context.get("history", {})
    if history.get("conditions"):
        parts.append(f"Medical History: {', '.join(history['conditions'])}")
    if history.get("medications"):
        parts.append(f"Current Medications: {', '.join(history['medications'])}")
    if history.get("allergies"):
        parts.append(f"Allergies: {', '.join(history['allergies'])}")

    return "\n".join(parts)


def _assemble_vocab_block(provider_profile: dict) -> str:
    """Build vocabulary hint from provider's custom terms."""
    vocab = provider_profile.get("custom_vocabulary", [])
    if not vocab:
        return ""
    return "Provider's custom vocabulary (use these exact terms when applicable):\n" + ", ".join(vocab[:50])


def _assemble_style_block(provider_profile: dict, note_type: str) -> str:
    """Build style preferences from provider profile."""
    prefs = provider_profile.get("style_preferences", {})
    if not prefs:
        return ""
    parts = []
    for key, value in prefs.items():
        parts.append(f"- {key}: {value}")
    return "Style preferences:\n" + "\n".join(parts)


def _parse_note_sections(raw_text: str, note_type: str) -> list[dict]:
    """Parse the LLM output into structured sections."""
    sections = []

    # Look for section headers like **SUBJECTIVE:** or ## SUBJECTIVE
    pattern = r"(?:\*\*|##?\s*)([\w\s/&]+?)(?:\*\*|:)\s*\n?(.*?)(?=(?:\*\*|##?\s*)[\w\s/&]+?(?:\*\*|:)|\Z)"
    matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)

    if matches:
        for label, content in matches:
            label = label.strip().upper()
            content = content.strip()
            if content:
                sections.append({
                    "label": label,
                    "content": content,
                    "confidence": 1.0,
                })
    else:
        # Fallback: treat entire text as single section
        sections.append({
            "label": note_type.upper(),
            "content": raw_text.strip(),
            "confidence": 0.5,
        })

    return sections


def _strip_phi_headers(text: str) -> str:
    """Remove any PHI-like headers the LLM might have generated."""
    # Remove lines like "Patient Name: ..." or "DOB: ..." at the start
    lines = text.split("\n")
    cleaned = []
    phi_patterns = [
        r"^patient\s*name\s*:", r"^date\s*of\s*birth\s*:", r"^dob\s*:",
        r"^mrn\s*:", r"^medical\s*record\s*:", r"^ssn\s*:",
        r"^date\s*of\s*(?:service|visit)\s*:",
    ]
    for line in lines:
        is_phi = False
        for pat in phi_patterns:
            if re.match(pat, line.strip(), re.IGNORECASE):
                is_phi = True
                break
        if not is_phi:
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def _is_refusal(text: str) -> bool:
    """Detect if the LLM refused to generate a note."""
    refusal_patterns = [
        r"i cannot",
        r"i can't",
        r"i'm unable to",
        r"i am unable to",
        r"as an ai",
        r"i don't have access",
        r"not appropriate for me",
        r"i must decline",
        r"cannot generate.*medical",
    ]
    text_lower = text.lower()[:500]
    for pattern in refusal_patterns:
        if re.search(pattern, text_lower):
            return True
    return False


def _estimate_confidence(sections: list[dict], transcript: dict) -> float:
    """Estimate note confidence based on section coverage and transcript quality."""
    if not sections:
        return 0.0
    section_score = min(len(sections) / 4.0, 1.0)  # 4 sections = full confidence
    transcript_confidence = transcript.get("avg_confidence", 0.5)
    return round((section_score * 0.6 + transcript_confidence * 0.4), 3)
