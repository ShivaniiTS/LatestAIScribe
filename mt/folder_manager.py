"""
mt/folder_manager.py — SFTP folder management for MT workflow.

Creates and manages the folder structure on the SFTP server:
  /mt_inbox/         — New jobs ready for pickup
  /mt_in_progress/   — Currently being worked on
  /mt_completed/     — Finished corrections
"""
from __future__ import annotations

import io
import json
import logging
import os
from pathlib import PurePosixPath
from typing import Optional

log = logging.getLogger("mt.sftp")


def _get_sftp_config() -> dict:
    return {
        "host": os.getenv("MT_SFTP_HOST", "localhost"),
        "port": int(os.getenv("MT_SFTP_PORT", "22")),
        "username": os.getenv("MT_SFTP_USER", "mt_user"),
        "password": os.getenv("MT_SFTP_PASSWORD", ""),
        "key_path": os.getenv("MT_SFTP_KEY_PATH", ""),
        "base_dir": os.getenv("MT_SFTP_BASE_DIR", "/mt"),
    }


def _connect():
    """Create an SFTP connection. Returns (transport, sftp) tuple."""
    import paramiko

    cfg = _get_sftp_config()
    transport = paramiko.Transport((cfg["host"], cfg["port"]))

    if cfg["key_path"] and os.path.exists(cfg["key_path"]):
        pkey = paramiko.RSAKey.from_private_key_file(cfg["key_path"])
        transport.connect(username=cfg["username"], pkey=pkey)
    else:
        transport.connect(username=cfg["username"], password=cfg["password"])

    sftp = paramiko.SFTPClient.from_transport(transport)
    return transport, sftp


def _ensure_dirs(sftp, base_dir: str) -> None:
    """Ensure the base folder structure exists."""
    for d in ["inbox", "in_progress", "completed"]:
        path = f"{base_dir}/{d}"
        try:
            sftp.stat(path)
        except FileNotFoundError:
            sftp.mkdir(path)
            log.info("Created SFTP directory: %s", path)


def upload_job(encounter_id: str, note_content: str, transcript: str, metadata: dict) -> str:
    """
    Upload a new MT job to the SFTP inbox.
    Returns the job folder path.
    """
    cfg = _get_sftp_config()
    base = cfg["base_dir"]
    transport, sftp = _connect()
    try:
        _ensure_dirs(sftp, base)
        job_dir = f"{base}/inbox/{encounter_id}"
        try:
            sftp.mkdir(job_dir)
        except IOError:
            pass  # Already exists

        # Upload note
        with sftp.open(f"{job_dir}/clinical_note.md", "w") as f:
            f.write(note_content)

        # Upload transcript
        with sftp.open(f"{job_dir}/transcript.txt", "w") as f:
            f.write(transcript)

        # Upload metadata
        meta_bytes = json.dumps(metadata, indent=2).encode()
        with sftp.open(f"{job_dir}/metadata.json", "wb") as f:
            f.write(meta_bytes)

        log.info("Uploaded MT job %s to inbox", encounter_id)
        return job_dir
    finally:
        sftp.close()
        transport.close()


def download_completed(encounter_id: str) -> Optional[dict]:
    """
    Download a completed MT job. Returns dict with corrected_content and comments,
    or None if not found.
    """
    cfg = _get_sftp_config()
    base = cfg["base_dir"]
    transport, sftp = _connect()
    try:
        job_dir = f"{base}/completed/{encounter_id}"
        try:
            sftp.stat(job_dir)
        except FileNotFoundError:
            return None

        result = {}
        try:
            with sftp.open(f"{job_dir}/clinical_note.md", "r") as f:
                result["corrected_content"] = f.read()
        except FileNotFoundError:
            return None

        try:
            with sftp.open(f"{job_dir}/corrections.json", "r") as f:
                corrections = json.loads(f.read())
                result["comments"] = corrections.get("comments", "")
                result["reviewer_id"] = corrections.get("reviewer_id", "")
        except FileNotFoundError:
            result["comments"] = ""
            result["reviewer_id"] = ""

        return result
    finally:
        sftp.close()
        transport.close()


def list_inbox() -> list[str]:
    """List encounter IDs in the MT inbox."""
    cfg = _get_sftp_config()
    base = cfg["base_dir"]
    transport, sftp = _connect()
    try:
        inbox_path = f"{base}/inbox"
        try:
            return [
                entry for entry in sftp.listdir(inbox_path)
                if not entry.startswith(".")
            ]
        except FileNotFoundError:
            return []
    finally:
        sftp.close()
        transport.close()


def move_to_in_progress(encounter_id: str) -> None:
    """Move a job from inbox to in_progress."""
    cfg = _get_sftp_config()
    base = cfg["base_dir"]
    transport, sftp = _connect()
    try:
        src = f"{base}/inbox/{encounter_id}"
        dst = f"{base}/in_progress/{encounter_id}"
        sftp.rename(src, dst)
        log.info("MT job %s moved to in_progress", encounter_id)
    finally:
        sftp.close()
        transport.close()
