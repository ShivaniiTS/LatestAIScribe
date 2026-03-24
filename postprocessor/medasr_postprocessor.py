"""
postprocessor/medasr_postprocessor.py — MedASR 12-stage rule-based transcript cleaner.

Fixes mechanical CTC decoder artifacts before LLM processing.
No external dependencies (stdlib only for core stages).

Stages:
  0.  Offensive ASR misrecognition filter
  0a. "Scratch that" dictation correction removal
  0b. Spelled-out word expansion
  1.  Format command doubles
  2.  Punctuation doubles
  3.  CTC stutter pair merging
  4.  Internal character stutter fix
  5.  Filler word normalization
  6.  Broken word merging
  7.  Section header cleanup
  8.  Whitespace normalization
  9.  Trailing artifact removal
  9a. Medical phrase corrections
  9b. Unit & abbreviation normalization
  10. Dictionary matching
  11. Medical spell check (optional, requires symspellpy)
  12. MedASR artifact removal
"""
from __future__ import annotations

import difflib
import itertools
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("postprocessor")


@dataclass
class CleanupMetrics:
    format_cmd_doubles: int = 0
    punctuation_doubles: int = 0
    stutter_pairs_merged: int = 0
    char_stutters_fixed: int = 0
    fillers_normalized: int = 0
    broken_words_merged: int = 0
    headers_cleaned: int = 0
    whitespace_fixes: int = 0
    trailing_artifacts: int = 0
    dictionary_corrections: int = 0
    medical_corrections: int = 0
    medasr_artifacts_removed: int = 0
    format_commands_resolved: int = 0
    offensive_misrecognitions_removed: int = 0
    scratch_that_removed: int = 0
    spelled_words_expanded: int = 0
    phrase_corrections: int = 0
    unit_abbreviations: int = 0
    words_before: int = 0
    words_after: int = 0

    def summary(self) -> str:
        lines = [
            "=== POST-PROCESSING METRICS ===",
            f"  Format command doubles:      {self.format_cmd_doubles}",
            f"  Punctuation doubles:         {self.punctuation_doubles}",
            f"  Stutter pairs merged:        {self.stutter_pairs_merged}",
            f"  Char stutters fixed:         {self.char_stutters_fixed}",
            f"  Fillers normalized:          {self.fillers_normalized}",
            f"  Broken words merged:         {self.broken_words_merged}",
            f"  Headers cleaned:             {self.headers_cleaned}",
            f"  Whitespace fixes:            {self.whitespace_fixes}",
            f"  Trailing artifacts:          {self.trailing_artifacts}",
            f"  Dictionary corrections:      {self.dictionary_corrections}",
            f"  Medical corrections:         {self.medical_corrections}",
            f"  Offensive removed:           {self.offensive_misrecognitions_removed}",
            f"  Scratch-that removed:        {self.scratch_that_removed}",
            f"  Spelled words expanded:      {self.spelled_words_expanded}",
            f"  Phrase corrections:          {self.phrase_corrections}",
            f"  Unit abbreviations:          {self.unit_abbreviations}",
            f"  Words: {self.words_before} → {self.words_after}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "format_cmd_doubles": self.format_cmd_doubles,
            "punctuation_doubles": self.punctuation_doubles,
            "stutter_pairs_merged": self.stutter_pairs_merged,
            "char_stutters_fixed": self.char_stutters_fixed,
            "fillers_normalized": self.fillers_normalized,
            "broken_words_merged": self.broken_words_merged,
            "headers_cleaned": self.headers_cleaned,
            "whitespace_fixes": self.whitespace_fixes,
            "trailing_artifacts": self.trailing_artifacts,
            "dictionary_corrections": self.dictionary_corrections,
            "medical_corrections": self.medical_corrections,
            "offensive_misrecognitions_removed": self.offensive_misrecognitions_removed,
            "scratch_that_removed": self.scratch_that_removed,
            "spelled_words_expanded": self.spelled_words_expanded,
            "phrase_corrections": self.phrase_corrections,
            "unit_abbreviations": self.unit_abbreviations,
            "words_before": self.words_before,
            "words_after": self.words_after,
        }


@dataclass
class PostprocessResult:
    cleaned_text: str
    metrics: CleanupMetrics

    def metrics_dict(self) -> dict:
        return self.metrics.to_dict()


# ── Stage 0: Offensive misrecognition filter ──────────────────────────────

_OFFENSIVE_RE = re.compile(
    r"\b(?:"
    r"pedophil(?:e|ia|ic|es)?"
    r"|pederast(?:s|y)?"
    r"|neo-?nazi(?:s)?"
    r"|pornograph(?:y|ic)?"
    r")\b",
    re.IGNORECASE,
)


def _stage0_offensive(text: str, m: CleanupMetrics) -> str:
    def _rep(match):
        m.offensive_misrecognitions_removed += 1
        return " "
    return _OFFENSIVE_RE.sub(_rep, text)


# ── Stage 0a: "Scratch that" removal ─────────────────────────────────────

_SCRATCH_RE = re.compile(
    r'[^.!?\n]*\bscratche?d?\s+(?:all\s+)?that\b[,.]?\s*',
    re.IGNORECASE,
)


def _stage0a_scratch(text: str, m: CleanupMetrics) -> str:
    count = 0
    def _rep(match):
        nonlocal count
        count += 1
        return ' '
    text = _SCRATCH_RE.sub(_rep, text)
    m.scratch_that_removed += count
    return text


# ── Stage 0b: Spelled-out word expansion ─────────────────────────────────

_SPELL_RE = re.compile(
    r'(?<![A-Za-z])[A-Za-z](?:(?:[ \t]+|[ \t]*[-\u2013][ \t]*)[A-Za-z]){2,}(?![A-Za-z])',
)


def _stage0b_spell(text: str, m: CleanupMetrics) -> str:
    count = 0
    def _rep(match):
        nonlocal count
        letters = re.findall(r'[A-Za-z]', match.group(0))
        if len(letters) < 3:
            return match.group(0)
        count += 1
        return ''.join(letters).upper()
    text = _SPELL_RE.sub(_rep, text)
    m.spelled_words_expanded += count
    return text


# ── Stage 1: Format command doubles ──────────────────────────────────────

def _stage1_format_cmds(text: str, m: CleanupMetrics) -> str:
    patterns = [
        (r'\{period\s*period\}', '{period}'),
        (r'\{comma\s*comma\}', '{comma}'),
        (r'\{colon\s*colon\}', '{colon}'),
        (r'\{new\s*new\s*line\}', '{new line}'),
        (r'\{new\s*new\s*paragraph\}', '{new paragraph}'),
        (r'\{\s*\{', '{'),
        (r'\}\s*\}', '}'),
    ]
    for pat, rep in patterns:
        count = len(re.findall(pat, text, re.IGNORECASE))
        if count:
            text = re.sub(pat, rep, text, flags=re.IGNORECASE)
            m.format_cmd_doubles += count
    return text


# ── Stage 2: Punctuation doubles ─────────────────────────────────────────

def _stage2_punctuation(text: str, m: CleanupMetrics) -> str:
    original = text
    for p in ['.', ',', ':', ';', '?', '!']:
        esc = re.escape(p)
        text = re.sub(rf'{esc}\s+{esc}', p, text)
        text = re.sub(rf'{esc}{{2,}}', p, text)
    if text != original:
        m.punctuation_doubles += abs(len(original) - len(text))
    return text


# ── Stage 3: CTC stutter pair merging ────────────────────────────────────

REAL_SHORT_WORDS = {
    'a', 'an', 'as', 'at', 'be', 'by', 'do', 'go', 'he', 'if', 'in',
    'is', 'it', 'me', 'my', 'no', 'of', 'on', 'or', 'so', 'to', 'up',
    'us', 'we', 'am', 'are', 'and', 'but', 'can', 'did', 'for',
    'had', 'has', 'her', 'him', 'his', 'how', 'its', 'let', 'may',
    'new', 'not', 'now', 'old', 'one', 'our', 'out', 'own', 'per',
    'put', 'ran', 'say', 'she', 'the', 'too', 'two', 'use', 'was',
    'who', 'why', 'yet', 'you', 'all', 'any', 'day', 'get', 'got',
    'see', 'set', 'sit', 'six', 'ten', 'try', 'via', 'also', 'back',
    'been', 'both', 'come', 'does', 'down', 'each', 'even', 'from',
    'give', 'good', 'have', 'here', 'high', 'into', 'just', 'keep',
    'last', 'left', 'long', 'look', 'made', 'make', 'many', 'more',
    'much', 'must', 'next', 'only', 'over', 'part', 'past', 'same',
    'seem', 'show', 'side', 'some', 'such', 'take', 'tell', 'than',
    'that', 'them', 'then', 'they', 'this', 'time', 'turn', 'very',
    'want', 'well', 'went', 'were', 'what', 'when', 'will', 'with',
    'work', 'year', 'your', 'four', 'five',
    'pain', 'hand', 'head', 'knee', 'back', 'neck', 'left', 'right',
    'full', 'bone', 'drug', 'dose', 'test', 'mild', 'skin', 'oral',
}


def _has_internal_stutter(word: str) -> bool:
    w = word.lower()
    if len(w) < 5:
        return False
    for i in range(len(w) - 3):
        if w[i:i+2] == w[i+2:i+4] and w[i:i+2].isalpha():
            return True
    for i in range(len(w) - 5):
        if w[i:i+3] == w[i+3:i+6] and w[i:i+3].isalpha():
            return True
    return False


def _stage3_stutter_pairs(text: str, m: CleanupMetrics) -> str:
    words = text.split()
    result = []
    i = 0
    while i < len(words):
        if i < len(words) - 1:
            w1_raw = words[i]
            w2_raw = words[i + 1]
            w1 = re.sub(r'^[\[\({]*', '', w1_raw)
            w1 = re.sub(r'[\]\)},.:;!?]*$', '', w1).lower()
            w2 = re.sub(r'^[\[\({]*', '', w2_raw)
            w2_clean = re.sub(r'[\]\)},.:;!?]*$', '', w2).lower()
            basic_match = (1 <= len(w1) <= 6 and len(w2_clean) >= 3
                           and w2_clean.startswith(w1) and len(w2_clean) > len(w1))
            if basic_match:
                if w1 not in REAL_SHORT_WORDS:
                    result.append(w2_raw)
                    m.stutter_pairs_merged += 1
                    i += 2
                    continue
                if _has_internal_stutter(w2_clean):
                    result.append(w2_raw)
                    m.stutter_pairs_merged += 1
                    i += 2
                    continue
        result.append(words[i])
        i += 1
    return ' '.join(result)


# ── Stage 4: Internal character stutter ──────────────────────────────────

_STUTTER_SKIP = REAL_SHORT_WORDS | {
    'three', 'free', 'tree', 'agree', 'see', 'fee', 'bee', 'knee',
    'needed', 'seeded', 'headed', 'added', 'aided', 'ended', 'sided',
    'daily', 'weekly', 'monthly', 'yearly',
}


def _fix_word_once(word: str) -> str:
    match = re.match(r'^([^a-zA-Z]*)(.*?)([^a-zA-Z]*)$', word)
    if not match:
        return word
    prefix, core, suffix = match.groups()
    if len(core) < 4:
        return word
    core_lower = core.lower()
    # Repeated suffix
    for suf_len in range(5, 1, -1):
        if len(core_lower) >= suf_len * 2:
            ending = core_lower[-suf_len:]
            before = core_lower[-suf_len*2:-suf_len]
            if ending == before:
                return prefix + core[:-suf_len] + suffix
    # Repeated internal syllable
    for chunk_len in range(4, 1, -1):
        for pos in range(0, len(core_lower) - chunk_len * 2 + 1):
            chunk = core_lower[pos:pos + chunk_len]
            next_chunk = core_lower[pos + chunk_len:pos + chunk_len * 2]
            if chunk == next_chunk and chunk.isalpha():
                return prefix + core[:pos] + core[pos + chunk_len:] + suffix
    return word


def _stage4_char_stutters(text: str, m: CleanupMetrics) -> str:
    words = text.split()
    result = []
    for w in words:
        bare = re.sub(r'^[^a-zA-Z]*|[^a-zA-Z]*$', '', w).lower()
        if bare in _STUTTER_SKIP:
            result.append(w)
            continue
        prev = w
        for _ in range(3):
            fixed = _fix_word_once(prev)
            if fixed == prev:
                break
            prev = fixed
        if prev != w:
            m.char_stutters_fixed += 1
        result.append(prev)
    return ' '.join(result)


# ── Stage 5: Filler normalization ────────────────────────────────────────

def _stage5_fillers(text: str, m: CleanupMetrics) -> str:
    uhm_pat = r'\b[Uu]\s*[Uu]?\s*[Hh]+\s*[Mm]+\b'
    count = len(re.findall(uhm_pat, text))
    text = re.sub(uhm_pat, '[um]', text)
    uh_pats = [r'\b[Uu]\s+[Hh]+\b', r'\b[Uu][Uu]+\s*[Hh]+\b', r'\b[Uu][Hh][Hh]+\b']
    for p in uh_pats:
        n = len(re.findall(p, text))
        count += n
        text = re.sub(p, '[uh]', text)
    text = re.sub(r'(?<![a-zA-Z])[Uu][Hh](?![a-zA-Z])', '[uh]', text)
    text = re.sub(r'\[uh\]\s*\[uh\]', '[uh]', text)
    text = re.sub(r'\[um\]\s*\[um\]', '[um]', text)
    m.fillers_normalized += count
    return text


# ── Stage 6: Broken word merging ─────────────────────────────────────────

def _stage6_broken_words(text: str, m: CleanupMetrics) -> str:
    words = text.split()
    result = []
    i = 0
    while i < len(words):
        if i < len(words) - 1:
            w1 = words[i].lower().strip('.,;:{}[]()-')
            w2 = words[i + 1].lower().strip('.,;:{}[]()-')
            if (len(w1) == 1 and w1.isalpha() and w1 not in {'a', 'i'}
                    and len(w2) >= 3 and w2.startswith(w1)):
                result.append(words[i + 1])
                m.broken_words_merged += 1
                i += 2
                continue
        result.append(words[i])
        i += 1
    return ' '.join(result)


# ── Stage 7: Section header cleanup ──────────────────────────────────────

KNOWN_HEADERS = {
    'PAST MEDICAL HISTORY', 'PAST SURGICAL HISTORY', 'FAMILY HISTORY',
    'SOCIAL HISTORY', 'ALLERGIES', 'MEDICATIONS', 'REVIEW OF SYSTEMS',
    'PHYSICAL EXAM', 'PHYSICAL EXAMINATION', 'ASSESSMENT', 'PLAN',
    'IMPRESSION', 'HPI', 'HISTORY OF PRESENT ILLNESS', 'CHIEF COMPLAINT',
    'SUBJECTIVE', 'OBJECTIVE',
}


def _stage7_headers(text: str, m: CleanupMetrics) -> str:
    def _clean(match):
        inner = match.group(1)
        cleaned = re.sub(r'([A-Z])\1+', r'\1', inner.strip().upper())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        best, score = None, 0
        for known in KNOWN_HEADERS:
            c1, c2 = cleaned.replace(' ', ''), known.replace(' ', '')
            s = sum(1 for a, b in zip(c1, c2) if a == b) / max(len(c1), len(c2), 1)
            if s > score and s > 0.6:
                best, score = known, s
        if best and best != inner.strip():
            m.headers_cleaned += 1
            return f'[{best}]'
        return match.group(0)

    return re.sub(r'\[\s*\[?\s*([A-Z][A-Z\s.,]+?)\s*\]?\s*\]', _clean, text)


# ── Stage 8: Whitespace normalization ────────────────────────────────────

def _stage8_whitespace(text: str, m: CleanupMetrics) -> str:
    orig_len = len(text)
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    text = re.sub(r'\[\s+', '[', text)
    text = re.sub(r'\s+\]', ']', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    m.whitespace_fixes += abs(len(text) - orig_len)
    return text


# ── Stage 9: Trailing artifacts ──────────────────────────────────────────

def _stage9_trailing(text: str, m: CleanupMetrics) -> str:
    if text.rstrip().endswith('-e'):
        text = text.rstrip()[:-2].rstrip()
        m.trailing_artifacts += 1
    text = re.sub(r'\s+[.\-,]+\s*$', '', text)
    return text


# ── Stage 9a: Medical phrase corrections ─────────────────────────────────

_PHRASE_CORRECTIONS = [
    (re.compile(
        r'\b(?:normal\s*,?\s*scalp\s+(?:can\s+)?(?:be\s+)?(?:and\s+)?a?traumatic'
        r'|normocephalic\s+atraumatic'
        r'|normo\s*cephalic\s+and\s+a?traumatic)\b', re.IGNORECASE),
     'normocephalic and atraumatic'),
    (re.compile(r'\b(?:regular\s+rate\s+in\s+rhythm|regular\s+rate\s+an\s+rhythm)\b', re.IGNORECASE),
     'regular rate and rhythm'),
    (re.compile(r'\b(?:clear\s+to\s+osculation\s+bilaterally)\b', re.IGNORECASE),
     'clear to auscultation bilaterally'),
    (re.compile(r'\b(?:with\s+in\s+normal\s+limits|within\s+normal\s+limit)\b', re.IGNORECASE),
     'within normal limits'),
    (re.compile(r'\bhistory\s+of\s+(?:pregnancy|presidents?|presence)\s+illness\b', re.IGNORECASE),
     'history of present illness'),
    (re.compile(r'\bwhole\s+cranial\b', re.IGNORECASE), 'holocranial'),
    (re.compile(r'\bfollow(?:\s*-?\s*up)?\s+evacuation\b', re.IGNORECASE), 'followup evaluation'),
    (re.compile(r'\b(?:Q[-\s]?Lifta|Klifta|Q[-\s]?lifter)\b', re.IGNORECASE), 'Qulipta'),
    (re.compile(r'\b(?:galxo|galxon|skelaxen)\b', re.IGNORECASE), 'Skelaxin'),
    (re.compile(r'\b(?:NERTEC|nertec|ner\s*tech|nur\s*tec)\b', re.IGNORECASE), 'Nurtec'),
]


def _stage9a_phrases(text: str, m: CleanupMetrics) -> str:
    count = 0
    for pat, rep in _PHRASE_CORRECTIONS:
        new_text, n = pat.subn(rep, text)
        count += n
        text = new_text
    m.phrase_corrections += count
    return text


# ── Stage 9b: Unit abbreviation normalization ────────────────────────────

_UNIT_REPLACEMENTS = [
    (re.compile(r'\bmicrograms?\b', re.IGNORECASE), 'mcg'),
    (re.compile(r'\bmilligrams?\b', re.IGNORECASE), 'mg'),
    (re.compile(r'\bkilograms?\b', re.IGNORECASE), 'kg'),
    (re.compile(r'\bmilli\s*liters?\b', re.IGNORECASE), 'mL'),
    (re.compile(r'\bby\s+mouth\b', re.IGNORECASE), 'PO'),
    (re.compile(r'\bonce\s+(?:a\s+)?daily\b', re.IGNORECASE), 'QD'),
    (re.compile(r'\btwice\s+(?:a\s+)?daily\b', re.IGNORECASE), 'BID'),
    (re.compile(r'\bthree\s+times\s+(?:a\s+)?(?:daily|day)\b', re.IGNORECASE), 'TID'),
    (re.compile(r'\bfour\s+times\s+(?:a\s+)?(?:daily|day)\b', re.IGNORECASE), 'QID'),
    (re.compile(r'\bas\s+needed\b', re.IGNORECASE), 'PRN'),
    (re.compile(r'\bevery\s+(\d+)\s+hours?\b', re.IGNORECASE), lambda m_: f'q {m_.group(1)}h'),
]


def _stage9b_units(text: str, m: CleanupMetrics) -> str:
    count = 0
    for pat, rep in _UNIT_REPLACEMENTS:
        if callable(rep):
            new_text, n = pat.subn(rep, text)
        else:
            new_text, n = pat.subn(rep, text)
        count += n
        text = new_text
    m.unit_abbreviations += count
    return text


# ── Stage 10: Dictionary matching ────────────────────────────────────────

MEDICAL_DICTIONARY = {
    'cervical', 'thoracic', 'lumbar', 'sacral', 'paraspinal', 'flexion',
    'extension', 'abduction', 'adduction', 'pronation', 'supination',
    'meniscus', 'meniscal', 'ligament', 'tendon', 'tendinitis', 'bursitis',
    'arthritis', 'arthroplasty', 'arthroscopy', 'palpation', 'tenderness',
    'radicular', 'paresthesias', 'bilateral', 'unilateral', 'contralateral',
    'naproxen', 'meloxicam', 'cyclobenzaprine', 'ibuprofen', 'acetaminophen',
    'gabapentin', 'pregabalin', 'prednisone', 'methylprednisolone',
    'cholecystectomy', 'appendectomy', 'laminectomy', 'discectomy',
    'hypertension', 'hypotension', 'tachycardia', 'bradycardia',
    'noncontributory', 'unremarkable', 'followup', 'normocephalic',
    'atraumatic', 'neuropathy', 'radiculopathy', 'myelopathy',
}


def _load_dictionary(extra_path: Optional[str] = None) -> set:
    words = set()
    for p in ['/usr/share/dict/words', '/usr/share/dict/american-english']:
        if os.path.exists(p):
            with open(p, 'r') as f:
                words.update(line.strip().lower() for line in f if len(line.strip()) >= 2)
            break
    words.update(w.lower() for w in MEDICAL_DICTIONARY)
    if extra_path and os.path.exists(extra_path):
        with open(extra_path, 'r') as f:
            words.update(line.strip().lower() for line in f if len(line.strip()) >= 2)
    return words


def _deduplicate_chars(word: str) -> set:
    w = word.lower()
    doubles = []
    i = 0
    while i < len(w) - 1:
        if w[i] == w[i + 1]:
            doubles.append(i)
            i += 2
        else:
            i += 1
    if not doubles:
        return {w}
    doubles = doubles[:6]
    results = set()
    for combo in itertools.product([True, False], repeat=len(doubles)):
        chars = list(w)
        for keep, pos in sorted(zip(combo, doubles), reverse=True):
            if not keep and pos < len(chars):
                del chars[pos]
        results.add(''.join(chars))
    return results


def _find_best_match(word: str, dictionary: set, min_sim: float = 0.80) -> Optional[str]:
    w = word.lower()
    if w in dictionary:
        return None
    variants = _deduplicate_chars(w)
    dedup = [v for v in variants if v in dictionary and v != w]
    if dedup:
        return min(dedup, key=len)
    if len(w) >= 6:
        candidates = [d for d in dictionary if abs(len(d) - len(w)) <= 2
                       and d[0] == w[0] and len(d) >= 5]
        matches = difflib.get_close_matches(w, candidates, n=3, cutoff=min_sim)
        if matches:
            return min(matches, key=lambda x: abs(len(x) - len(w)))
    return None


_DICT_SKIP = [
    re.compile(r'^\['), re.compile(r'^\{'), re.compile(r'^[A-Z]{2,}$'),
    re.compile(r'^\d'), re.compile(r'^[a-z]{1,3}$'),
]


def _stage10_dictionary(text: str, m: CleanupMetrics, dictionary: Optional[set] = None) -> str:
    if dictionary is None:
        dictionary = _load_dictionary()
    words = text.split()
    result = []
    cache: dict[str, Optional[str]] = {}
    for w in words:
        match = re.match(r'^([^a-zA-Z]*)(.*?)([^a-zA-Z]*)$', w)
        if not match:
            result.append(w)
            continue
        prefix, core, suffix = match.groups()
        skip = any(p.match(w) for p in _DICT_SKIP) or len(core) < 3
        if skip:
            result.append(w)
            continue
        cl = core.lower()
        if cl not in cache:
            cache[cl] = _find_best_match(cl, dictionary)
        rep = cache[cl]
        if rep and rep != cl:
            if core[0].isupper() and not core.isupper():
                rep = rep.capitalize()
            elif core.isupper():
                rep = rep.upper()
            result.append(prefix + rep + suffix)
            m.dictionary_corrections += 1
        else:
            result.append(w)
    return ' '.join(result)


# ── Stage 12: MedASR artifact removal ────────────────────────────────────

def _stage12_medasr_artifacts(text: str, m: CleanupMetrics) -> str:
    # Remove [unintelligible] markers
    count = len(re.findall(r'\[unintelligible\]', text, re.IGNORECASE))
    text = re.sub(r'\[unintelligible\]\s*', '', text, flags=re.IGNORECASE)

    # Remove filler markers
    count += len(re.findall(r'\[(?:uh|um)\]', text))
    text = re.sub(r'\[(?:uh|um)\]\s*', '', text)

    # Resolve format commands
    fmt_count = 0
    fmt_map = {
        '{period}': '.', '{comma}': ',', '{colon}': ':',
        '{new line}': '\n', '{new paragraph}': '\n\n',
        '{slash}': '/', '{exclamation}': '!', '{question mark}': '?',
    }
    for cmd, char in fmt_map.items():
        n = text.lower().count(cmd.lower())
        if n:
            text = re.sub(re.escape(cmd), char, text, flags=re.IGNORECASE)
            fmt_count += n

    m.medasr_artifacts_removed += count
    m.format_commands_resolved += fmt_count
    return text


# ── Main processor class ─────────────────────────────────────────────────

class MedASRPostprocessor:
    """12-stage rule-based transcript postprocessor."""

    def __init__(self, extra_dict_path: Optional[str] = None):
        self._dictionary: Optional[set] = None
        self._extra_dict_path = extra_dict_path

    def process(self, text: str) -> PostprocessResult:
        """Run all 12 stages on the input text."""
        m = CleanupMetrics()
        m.words_before = len(text.split())

        # Stage 0: Offensive filter
        text = _stage0_offensive(text, m)
        # Stage 0a: Scratch that
        text = _stage0a_scratch(text, m)
        # Stage 0b: Spelled words
        text = _stage0b_spell(text, m)
        # Stage 1: Format command doubles
        text = _stage1_format_cmds(text, m)
        # Stage 2: Punctuation doubles
        text = _stage2_punctuation(text, m)
        # Stage 3: Stutter pairs
        text = _stage3_stutter_pairs(text, m)
        # Stage 4: Char stutters
        text = _stage4_char_stutters(text, m)
        # Stage 5: Fillers
        text = _stage5_fillers(text, m)
        # Stage 6: Broken words
        text = _stage6_broken_words(text, m)
        # Stage 7: Headers
        text = _stage7_headers(text, m)
        # Stage 8: Whitespace
        text = _stage8_whitespace(text, m)
        # Stage 9: Trailing artifacts
        text = _stage9_trailing(text, m)
        # Stage 9a: Phrase corrections
        text = _stage9a_phrases(text, m)
        # Stage 9b: Unit abbreviations
        text = _stage9b_units(text, m)
        # Stage 10: Dictionary matching
        if self._dictionary is None:
            self._dictionary = _load_dictionary(self._extra_dict_path)
        text = _stage10_dictionary(text, m, self._dictionary)
        # Stage 12: MedASR artifact removal
        text = _stage12_medasr_artifacts(text, m)
        # Final whitespace cleanup
        text = re.sub(r'  +', ' ', text).strip()

        m.words_after = len(text.split())
        return PostprocessResult(cleaned_text=text, metrics=m)
