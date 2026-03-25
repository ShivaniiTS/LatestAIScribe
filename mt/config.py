"""
mt/config.py — Configuration loading for MT workflow environment variables.

Reads all MT-specific settings from the environment and returns them
as a single dictionary. Missing required variables are logged as
warnings so the corresponding features can be disabled gracefully.

Ported from MDCO-AI-Scribe backend/ai_scribe/mt_config.py.
"""

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def parse_comma_separated(value: str) -> List[str]:
    """Parse a comma-separated string into a list of trimmed, non-empty elements."""
    return [item.strip() for item in value.split(",") if item.strip()]


def load_mt_config() -> Dict[str, Any]:
    """Load all MT workflow configuration from environment variables.

    Returns a dict with keys:
        master_upload_path      – str or None (SFTP path to master upload folder)
        report_recipients       – List[str] or empty list
        sort_polling_interval   – int (seconds between SFTP polls)
        report_schedule         – List[str] (HH:MM times to send daily report)
        dual_write_enabled      – bool
        smtp_host               – str
        smtp_port               – int
        smtp_username           – str
        smtp_password           – str
        smtp_from               – str
    """
    config: Dict[str, Any] = {}

    # --- Required (warn if missing) ---
    master_upload_path = os.environ.get("MT_MASTER_UPLOAD_PATH")
    if not master_upload_path:
        logger.warning(
            "MT_MASTER_UPLOAD_PATH is not set — MT sorting script will be disabled"
        )
    config["master_upload_path"] = master_upload_path or None

    recipients_raw = os.environ.get("MT_REPORT_RECIPIENTS", "")
    if not recipients_raw.strip():
        logger.warning(
            "MT_REPORT_RECIPIENTS is not set — email reports will be disabled"
        )
        config["report_recipients"] = []
    else:
        config["report_recipients"] = parse_comma_separated(recipients_raw)

    # --- Optional with defaults ---
    default_polling = 60
    polling_raw = os.environ.get("MT_SORT_POLLING_INTERVAL", str(default_polling))
    try:
        config["sort_polling_interval"] = int(polling_raw)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid MT_SORT_POLLING_INTERVAL '%s' — falling back to %s",
            polling_raw,
            default_polling,
        )
        config["sort_polling_interval"] = default_polling

    schedule_raw = os.environ.get("MT_REPORT_SCHEDULE", "06:00,10:00")
    config["report_schedule"] = parse_comma_separated(schedule_raw)

    dual_write_raw = os.environ.get("MT_DUAL_WRITE_ENABLED", "true").lower()
    config["dual_write_enabled"] = dual_write_raw in ("true", "1", "yes")

    config["smtp_host"] = os.environ.get("MT_SMTP_HOST", "localhost")

    default_smtp_port = 25
    smtp_port_raw = os.environ.get("MT_SMTP_PORT", str(default_smtp_port))
    try:
        config["smtp_port"] = int(smtp_port_raw)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid MT_SMTP_PORT '%s' — falling back to %s",
            smtp_port_raw,
            default_smtp_port,
        )
        config["smtp_port"] = default_smtp_port

    config["smtp_username"] = os.environ.get("MT_SMTP_USERNAME", "")
    config["smtp_password"] = os.environ.get("MT_SMTP_PASSWORD", "")
    config["smtp_from"] = os.environ.get("MT_SMTP_FROM", "mt-reports@aiscribe.local")

    return config
