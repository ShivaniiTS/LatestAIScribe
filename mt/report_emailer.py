"""
mt/report_emailer.py — Daily summary emails for MT workflow.

Generates and sends daily MT activity reports via email to configured
admin recipients. Reports aggregate encounters by provider, showing
audio file counts and total minutes.

Ported from MDCO-AI-Scribe backend/ai_scribe/mt_report_emailer.py.
"""

import datetime
import logging
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MTReportEmailer:
    """Generates and sends daily MT activity reports via email."""

    def __init__(
        self,
        recipients: List[str],
        schedule_times: List[str],
        smtp_host: str = "localhost",
        smtp_port: int = 25,
        smtp_username: str = "",
        smtp_password: str = "",
        smtp_from: str = "mt-reports@aiscribe.local",
        store: Any = None,
    ):
        self.recipients = recipients
        self.schedule_times = schedule_times
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_from = smtp_from
        self.store = store
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_sent: Optional[str] = None

    def start(self) -> None:
        """Start the scheduler thread for report emails."""
        if self._thread and self._thread.is_alive():
            logger.warning("MTReportEmailer scheduler is already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        logger.info(
            "MTReportEmailer started — schedule: %s, recipients: %s",
            self.schedule_times, self.recipients,
        )

    def stop(self) -> None:
        """Stop the scheduler thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("MTReportEmailer stopped")

    def _scheduler_loop(self) -> None:
        """Background loop that checks every 30 seconds if it's time to send."""
        while not self._stop_event.is_set():
            try:
                now = datetime.datetime.now()
                current_time = now.strftime("%H:%M")

                if current_time in self.schedule_times and self._last_sent != current_time:
                    logger.info("Scheduled report time reached: %s", current_time)
                    self.send_report(now.date())
                    self._last_sent = current_time
                elif current_time not in self.schedule_times:
                    self._last_sent = None
            except Exception:
                logger.exception("Error in MT report scheduler loop")

            self._stop_event.wait(timeout=30)

    @staticmethod
    def aggregate_encounters(encounters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate a list of encounter dicts by provider.

        Pure function — no store access.

        Args:
            encounters: List of dicts with 'provider_id' and optionally
                        'audio_duration_minutes'.

        Returns:
            {
                "providers": [{"name": str, "audio_count": int, "total_minutes": int}, ...],
                "totals": {"audio_count": int, "total_minutes": int}
            }
        """
        if not encounters:
            return {
                "providers": [],
                "totals": {"audio_count": 0, "total_minutes": 0},
            }

        provider_map: Dict[str, Dict[str, Any]] = {}
        for enc in encounters:
            name = enc.get("provider_id", "Unknown")
            if name not in provider_map:
                provider_map[name] = {"name": name, "audio_count": 0, "total_minutes": 0}
            provider_map[name]["audio_count"] += 1
            provider_map[name]["total_minutes"] += enc.get("audio_duration_minutes", 0)

        providers = sorted(provider_map.values(), key=lambda p: p["name"])
        total_audio = sum(p["audio_count"] for p in providers)
        total_minutes = sum(p["total_minutes"] for p in providers)

        return {
            "providers": providers,
            "totals": {"audio_count": total_audio, "total_minutes": total_minutes},
        }

    def generate_report(self, date: datetime.date) -> Dict[str, Any]:
        """Query store for encounters on the given date and aggregate by provider."""
        if self.store is None:
            return {"providers": [], "totals": {"audio_count": 0, "total_minutes": 0}}

        date_str = date.isoformat()
        all_encounters = list(self.store._encounters.values()) if hasattr(self.store, "_encounters") else []
        # Filter to encounters created on the given date
        day_encounters = [
            e for e in all_encounters
            if e.get("created_at", "").startswith(date_str)
        ]
        return self.aggregate_encounters(day_encounters)

    def format_email_html(self, report: Dict[str, Any], date: datetime.date) -> str:
        """Format the report as an HTML email with a provider summary table."""
        date_str = date.isoformat()

        if not report["providers"]:
            return (
                f"<html><body>"
                f"<h2>MT Daily Report — {date_str}</h2>"
                f"<p>No encounters recorded for today.</p>"
                f"</body></html>"
            )

        rows = ""
        for p in report["providers"]:
            rows += (
                f"<tr>"
                f"<td>{p['name']}</td>"
                f"<td>{p['audio_count']}</td>"
                f"<td>{p['total_minutes']}</td>"
                f"</tr>"
            )

        totals = report["totals"]
        summary_row = (
            f"<tr style=\"font-weight:bold;\">"
            f"<td>Total</td>"
            f"<td>{totals['audio_count']}</td>"
            f"<td>{totals['total_minutes']}</td>"
            f"</tr>"
        )

        return (
            f"<html><body>"
            f"<h2>MT Daily Report — {date_str}</h2>"
            f"<table border=\"1\" cellpadding=\"5\" cellspacing=\"0\">"
            f"<tr><th>Provider</th><th>Audio Files</th><th>Total Minutes</th></tr>"
            f"{rows}"
            f"{summary_row}"
            f"</table>"
            f"</body></html>"
        )

    def send_report(self, date: datetime.date) -> bool:
        """Generate report, format HTML, and send via SMTP."""
        try:
            report = self.generate_report(date)
            html = self.format_email_html(report, date)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"MT Daily Report — {date.isoformat()}"
            msg["From"] = self.smtp_from
            msg["To"] = ", ".join(self.recipients)
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                if self.smtp_port == 587:
                    server.starttls()
                    server.ehlo()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.sendmail(msg["From"], self.recipients, msg.as_string())

            logger.info("MT report sent for %s to %s", date.isoformat(), self.recipients)
            return True
        except Exception:
            logger.exception("Failed to send MT report for %s", date.isoformat())
            return False

    def send_now(self) -> bool:
        """Trigger an immediate report for today (admin endpoint helper)."""
        return self.send_report(datetime.date.today())
