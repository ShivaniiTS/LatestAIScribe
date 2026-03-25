"""
mt/sorting_script.py — Background sorting of MT-reviewed SOAP notes.

Scans the MT master upload folder on SFTP for final SOAP note files
(.doc/.docx), extracts encounter IDs from filenames, looks up encounters
in the in-memory store, and moves files to the correct provider subfolder.
Also stores the final SOAP note locally and updates encounter status to
"MT Reviewed".

Ported from MDCO-AI-Scribe backend/ai_scribe/mt_sorting_script.py.
Adapted to use New-ai-scribe's SFTP connection from mt/folder_manager.py.
"""

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import paramiko

from mt.file_namer import MTFileNamer

logger = logging.getLogger(__name__)

# Local storage path for MT-reviewed SOAP notes
MT_SOAP_STORAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mt_reviewed")


def _create_sftp_connection():
    """
    Create an SFTP connection using New-ai-scribe's SFTP config.
    Returns (transport, sftp_client) tuple, or (None, None) on failure.
    """
    from mt.folder_manager import _connect
    try:
        transport, sftp = _connect()
        return transport, sftp
    except Exception as exc:
        logger.error("MT sorting: SFTP connection failed: %s", exc)
        return None, None


class MTSortingScript:
    """Scans master upload folder on SFTP and distributes files to provider folders."""

    def __init__(
        self,
        master_upload_path: str,
        polling_interval: int,
        store: Any,
        sftp_date_folder_manager: Any = None,
    ):
        """
        Args:
            master_upload_path:     SFTP path to the master upload folder.
            polling_interval:       Seconds between each poll.
            store:                  api.store module (or object) with get/update encounter methods.
            sftp_date_folder_manager: Optional MTFolderManager for date/provider folder routing.
                                     If None, files are moved to a flat 'completed/' folder.
        """
        self.master_upload_path = master_upload_path.rstrip("/") + "/"
        self.polling_interval = polling_interval
        self.store = store
        self.sftp_date_folder_manager = sftp_date_folder_manager
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread (daemon)."""
        if self._thread is not None and self._thread.is_alive():
            logger.info("MT sorting script already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(
            "Started MT sorting script (interval: %ds, master: %s)",
            self.polling_interval,
            self.master_upload_path,
        )

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._running = False
        self._thread = None
        logger.info("MT sorting script stopped")

    def _run(self) -> None:
        """Internal loop executed by the background thread."""
        while self._running:
            try:
                self.poll_once()
            except Exception as exc:
                logger.error("Error in MT sorting poll loop: %s", exc)
            time.sleep(self.polling_interval)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def poll_once(self) -> List[Dict[str, Any]]:
        """Single poll iteration: open SFTP, scan, extract, lookup, move."""
        results: List[Dict[str, Any]] = []
        transport = None
        sftp = None

        try:
            transport, sftp = _create_sftp_connection()
            if sftp is None:
                return results

            files = self._scan_master_folder(sftp)
            if not files:
                return results

            for filename in files:
                result = self._process_file(sftp, filename)
                results.append(result)

        except Exception as exc:
            logger.error("MT sorting poll_once error: %s", exc)
        finally:
            if sftp:
                try:
                    sftp.close()
                except Exception:
                    pass
            if transport:
                try:
                    transport.close()
                except Exception:
                    pass

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _process_file(self, sftp: paramiko.SFTPClient, filename: str) -> Dict[str, Any]:
        """Process a single file from the master upload folder."""
        source_path = self.master_upload_path + filename

        # 1. Extract encounter ID
        encounter_id = MTFileNamer.extract_encounter_id(filename)
        if not encounter_id:
            logger.error(
                "MT sorting: cannot extract encounter ID from '%s', leaving in place", filename,
            )
            return {
                "filename": filename,
                "encounter_id": None,
                "success": False,
                "error": "Cannot extract encounter ID",
                "destination_path": None,
            }

        # 2. Look up encounter in store
        encounter = self.store.get_encounter(encounter_id)
        if not encounter:
            logger.error(
                "MT sorting: encounter '%s' not found, leaving '%s' in place",
                encounter_id, filename,
            )
            return {
                "filename": filename,
                "encounter_id": encounter_id,
                "success": False,
                "error": "Encounter not found in store",
                "destination_path": None,
            }

        provider_name = encounter.get("provider_id", "unknown_provider")

        # 3. Determine destination folder
        if self.sftp_date_folder_manager is not None:
            import datetime
            dest_folder = self.sftp_date_folder_manager.ensure_provider_folder(
                sftp, datetime.date.today(), provider_name, 0
            )
        else:
            # Fall back to flat completed/ folder beside the master upload path
            base = self.master_upload_path.rstrip("/").rsplit("/", 1)[0]
            dest_folder = f"{base}/completed/"
            try:
                sftp.stat(dest_folder.rstrip("/"))
            except FileNotFoundError:
                sftp.mkdir(dest_folder.rstrip("/"))

        dest_path = dest_folder.rstrip("/") + "/" + filename

        # 4. Move file on SFTP
        if not self._move_file(sftp, source_path, dest_path):
            return {
                "filename": filename,
                "encounter_id": encounter_id,
                "success": False,
                "error": "Failed to move file on SFTP",
                "destination_path": dest_path,
            }

        # 5. Store locally for UI access
        local_path = None
        try:
            local_path = self._store_locally(sftp, dest_path, encounter_id)
        except Exception as exc:
            logger.error("MT sorting: failed to store locally for %s: %s", encounter_id, exc)

        # 6. Update encounter status → MT Reviewed
        try:
            self.store.update_encounter(encounter_id, {
                "status": "mt_corrected",
                "mt_completed_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                "mt_soap_local_path": local_path,
            })
        except Exception as exc:
            logger.error("MT sorting: failed to update status for %s: %s", encounter_id, exc)

        logger.info(
            "MT sorting: moved '%s' → '%s' (encounter %s)",
            filename, dest_path, encounter_id,
        )

        return {
            "filename": filename,
            "encounter_id": encounter_id,
            "success": True,
            "error": None,
            "destination_path": dest_path,
        }

    def _scan_master_folder(self, sftp: paramiko.SFTPClient) -> List[str]:
        """List .doc/.docx files in the master upload folder."""
        try:
            entries = sftp.listdir(self.master_upload_path.rstrip("/"))
        except FileNotFoundError:
            logger.warning(
                "MT sorting: master upload folder not found: %s", self.master_upload_path,
            )
            return []
        except IOError as exc:
            logger.error("MT sorting: error listing master folder: %s", exc)
            return []

        return [f for f in entries if MTFileNamer.is_accepted_upload_file(f)]

    def _move_file(
        self, sftp: paramiko.SFTPClient, source_path: str, dest_path: str
    ) -> bool:
        """Move file from master folder to provider folder on SFTP."""
        try:
            sftp.rename(source_path, dest_path)
            return True
        except IOError as exc:
            logger.error(
                "MT sorting: failed to move '%s' → '%s': %s", source_path, dest_path, exc,
            )
            return False

    def _store_locally(
        self,
        sftp: paramiko.SFTPClient,
        remote_path: str,
        encounter_id: str,
    ) -> Optional[str]:
        """Download and store the MT-reviewed SOAP note locally for UI access.

        Stores under MT_SOAP_STORAGE_PATH/<encounter_id>/<filename>.
        Returns local file path on success, None on failure.
        """
        filename = remote_path.rsplit("/", 1)[-1]
        local_dir = os.path.join(MT_SOAP_STORAGE_PATH, encounter_id)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, filename)

        try:
            sftp.get(remote_path, local_path)
            logger.info("MT sorting: stored locally %s → %s", remote_path, local_path)
            return local_path
        except Exception as exc:
            logger.error(
                "MT sorting: failed to download '%s' locally: %s", remote_path, exc,
            )
            return None
