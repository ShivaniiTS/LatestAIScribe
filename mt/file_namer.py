"""
mt/file_namer.py — Flat file naming utilities for the MT workflow.

Generates standardized filenames for audio files, AI SOAP notes,
MD Checkout files, and extracts encounter IDs from final SOAP note filenames.

Ported from MDCO-AI-Scribe backend/ai_scribe/mt_file_namer.py.
"""

import re
from typing import Optional


class MTFileNamer:
    """Generates standardized filenames for MT workflow files."""

    @staticmethod
    def audio_filename(encounter_id: str, audio_type: str) -> str:
        """Return: <encounter_id>_<audio_type>.mp3"""
        return f"{encounter_id}_{audio_type}.mp3"

    @staticmethod
    def ai_soap_filename(encounter_id: str) -> str:
        """Return: <encounter_id>_ai_soap_note.docx"""
        return f"{encounter_id}_ai_soap_note.docx"

    @staticmethod
    def mdcheckout_filename(encounter_id: str, extension: str = "pdf") -> str:
        """Return: <encounter_id>_mdcheckout_data.<ext>"""
        return f"{encounter_id}_mdcheckout_data.{extension}"

    @staticmethod
    def extract_encounter_id(filename: str) -> Optional[str]:
        """Extract encounter_id from a filename.

        Supports patterns (case-insensitive, .doc or .docx):
          - <id>_final_soap.docx           (e.g. 113256_final_soap.docx)
          - final_soap_<id>.docx           (e.g. final_soap_113256.docx)
          - Final_<id>_ai_soap_note.docx   (e.g. Final_164108_ai_soap_note.docx)
          - <id>_ai_soap_note.docx         (e.g. 164108_ai_soap_note.docx)
          - Fallback: first numeric sequence of 4+ digits in the filename

        Returns None if no encounter_id can be extracted.
        """
        basename = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

        match = re.match(r"^(\d+)_final_soap\.docx?$", basename, re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.match(r"^final_soap_(\d+)\.docx?$", basename, re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.match(r"^[A-Za-z]+_(\d+)_.*\.docx?$", basename)
        if match:
            return match.group(1)

        match = re.match(r"^(\d+)_ai_soap_note\.docx?$", basename, re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.search(r"(\d{4,})", basename)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def is_accepted_upload_file(filename: str) -> bool:
        """Check if a filename is an accepted upload file type (.doc or .docx)."""
        lower = filename.lower()
        return lower.endswith(".doc") or lower.endswith(".docx")
