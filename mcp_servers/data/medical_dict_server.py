"""
mcp_servers/data/medical_dict_server.py — Medical dictionary and hotword service.

Provides specialty-specific medical vocabulary for ASR hotword boosting
and LLM prompt enrichment.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DICT_DIR = Path(__file__).parent.parent.parent / "config" / "dictionaries"

# Specialty-specific hotword lists
SPECIALTY_HOTWORDS: dict[str, list[str]] = {
    "orthopedic": [
        "meniscus", "meniscal", "ligament", "ligamentous", "tendon", "tendinitis",
        "bursitis", "arthritis", "arthroplasty", "arthroscopy", "flexion", "extension",
        "abduction", "adduction", "pronation", "supination", "subluxation",
        "cervical", "thoracic", "lumbar", "sacral", "paraspinal", "radicular",
        "spurling", "lachman", "mcmurray", "phalen", "tinel",
    ],
    "neurology": [
        "neuropathy", "paresthesia", "radiculopathy", "myelopathy", "stenosis",
        "migraine", "cephalgia", "holocranial", "photophobia", "phonophobia",
        "aura", "scotoma", "vertigo", "nystagmus", "ataxia", "tremor",
        "seizure", "epilepsy", "electroencephalogram", "electromyography",
    ],
    "cardiology": [
        "tachycardia", "bradycardia", "arrhythmia", "fibrillation", "flutter",
        "murmur", "gallop", "stenosis", "regurgitation", "cardiomyopathy",
        "echocardiogram", "electrocardiogram", "angiography", "catheterization",
        "stent", "bypass", "pacemaker", "defibrillator",
    ],
    "pain_management": [
        "epidural", "facet", "radiofrequency", "ablation", "neurotomy",
        "injection", "corticosteroid", "anesthetic", "trigger point",
        "spinal cord stimulator", "intrathecal", "opioid", "analgesic",
        "nociceptive", "neuropathic", "allodynia", "hyperalgesia",
    ],
    "general": [
        "hypertension", "diabetes", "hyperlipidemia", "asthma", "COPD",
        "depression", "anxiety", "hypothyroidism", "anemia", "obesity",
    ],
}


class MedicalDictServer:
    """Medical dictionary and hotword provider."""

    def __init__(self, dict_dir: str | Path | None = None):
        self._dir = Path(dict_dir) if dict_dir else _DICT_DIR
        self._custom_words: set[str] = set()
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        # Load custom dictionary files
        if self._dir.exists():
            for path in self._dir.glob("*.txt"):
                with open(path, "r") as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith("#"):
                            self._custom_words.add(word.lower())
        self._loaded = True

    def get_hotwords(self, specialty: str = "general", max_terms: int = 200) -> list[str]:
        """Get hotwords for a specialty."""
        self._load()
        words = list(SPECIALTY_HOTWORDS.get(specialty, []))
        words.extend(SPECIALTY_HOTWORDS.get("general", []))
        words.extend(list(self._custom_words)[:50])

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for w in words:
            if w.lower() not in seen:
                seen.add(w.lower())
                unique.append(w)
            if len(unique) >= max_terms:
                break
        return unique

    def is_medical_term(self, word: str) -> bool:
        """Check if a word is a known medical term."""
        self._load()
        word_lower = word.lower()
        if word_lower in self._custom_words:
            return True
        for terms in SPECIALTY_HOTWORDS.values():
            if word_lower in [t.lower() for t in terms]:
                return True
        return False


_server: Optional[MedicalDictServer] = None


def get_dict_server() -> MedicalDictServer:
    global _server
    if _server is None:
        _server = MedicalDictServer()
    return _server
