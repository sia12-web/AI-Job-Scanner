"""
Outbox management for auto-apply system.

Handles JSONL storage, global deduplication, and statistics tracking
for all email applications.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class OutboxManager:
    """
    Manages JSONL outbox storage and global deduplication.

    Outbox format: data/outbox/outbox_YYYYMMDD.jsonl
    Each line is a JSON object representing one application attempt.
    """

    def __init__(self, outbox_dir: str):
        """
        Initialize outbox manager.

        Args:
            outbox_dir: Path to outbox directory (e.g., "data/outbox")
        """
        self.outbox_dir = Path(outbox_dir)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

        # Current outbox file (named by date)
        today = datetime.now().strftime("%Y%m%d")
        self.current_file = self.outbox_dir / f"outbox_{today}.jsonl"

        # Dedupe tracking (in-memory set of all dedupe keys)
        self.dedupe_cache = set()
        self._load_dedupe_cache()

    def _load_dedupe_cache(self):
        """
        Load existing dedupe keys from all outbox files.

        Scans all JSONL files and builds a set of dedupe_keys for
        global deduplication across all profiles and time.
        """
        for jsonl_file in self.outbox_dir.glob("outbox_*.jsonl"):
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                dedupe_key = record.get("dedupe_key")
                                if dedupe_key:
                                    self.dedupe_cache.add(dedupe_key)
                            except json.JSONDecodeError:
                                # Skip invalid JSON lines
                                continue
            except (FileNotFoundError, IOError):
                # Skip files that can't be read
                continue

    def create_entry(
        self,
        profile_id: Optional[str],
        source_id: str,
        tg_chat_id: int,
        tg_message_id: int,
        job_title: str,
        extracted_emails: List[str],
        selected_email: Optional[str],
        subject: Optional[str],
        body: Optional[str],
        cv_path: Optional[str],
        routing_scores: Dict[str, float],
        routing_metadata: Dict[str, Any],
        skip_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new outbox entry and append to JSONL.

        Args:
            profile_id: Profile ID (or None if skipped before routing)
            source_id: Telegram source ID
            tg_chat_id: Telegram chat ID
            tg_message_id: Telegram message ID
            job_title: Extracted job title
            extracted_emails: All emails found in message
            selected_email: Selected email (or None)
            subject: Email subject (or None)
            body: Email body (or None)
            cv_path: Path to CV file (or None)
            routing_scores: Profile scores from routing
            routing_metadata: Routing decision metadata
            skip_reason: Reason for skipping (if applicable)

        Returns:
            Created entry dict
        """
        outbox_id = str(uuid.uuid4())

        # Determine status
        if skip_reason:
            status = "skipped"
        elif selected_email:
            status = "draft"
        else:
            status = "skipped"
            if not skip_reason:
                skip_reason = "no_email_found"

        # Build dedupe key (only if email selected)
        dedupe_key = None
        if selected_email:
            dedupe_key = f"{tg_chat_id}:{tg_message_id}:{selected_email}"

        # Build entry
        entry = {
            "outbox_id": outbox_id,
            "profile_id": profile_id,
            "source_id": source_id,
            "tg_chat_id": tg_chat_id,
            "tg_message_id": tg_message_id,
            "job_title": job_title,
            "extracted_emails": extracted_emails,
            "selected_email": selected_email,
            "subject": subject,
            "body": body,
            "cv_path": cv_path,
            "status": status,
            "dedupe_key": dedupe_key,
            "routing_scores": routing_scores,
            "routing_metadata": routing_metadata,
            "skip_reason": skip_reason,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "sent_at": None,
            "last_error": None,
            "smtp_response": None,
            "attempt_count": 0,
        }

        # Append to JSONL
        self._append_entry(entry)

        # Update dedupe cache
        if dedupe_key:
            self.dedupe_cache.add(dedupe_key)

        return entry

    def _append_entry(self, entry: Dict[str, Any]):
        """
        Append entry to current JSONL file.

        Args:
            entry: Entry dict to append
        """
        with open(self.current_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def is_duplicate(self, dedupe_key: str) -> bool:
        """
        Check if dedupe key already exists in outbox.

        Args:
            dedupe_key: Deduplication key (tg_chat_id:tg_message_id:email)

        Returns:
            True if duplicate (already sent), False otherwise
        """
        return dedupe_key in self.dedupe_cache

    def update_entry(
        self,
        outbox_id: str,
        status: str,
        sent_at: Optional[str] = None,
        last_error: Optional[str] = None,
        smtp_response: Optional[str] = None,
    ):
        """
        Update an existing outbox entry.

        Note: JSONL is append-only, so this appends a new version
        of the entry. Readers should use the last version of each outbox_id.

        Args:
            outbox_id: Outbox entry ID to update
            status: New status (sent/failed/skipped)
            sent_at: ISO timestamp when sent (default: now)
            last_error: Error message if failed
            smtp_response: SMTP server response

        Raises:
            ValueError: If outbox_id not found
        """
        # Find original entry
        original_entry = None
        for jsonl_file in self.outbox_dir.glob("outbox_*.jsonl"):
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                if record.get("outbox_id") == outbox_id:
                                    original_entry = record
                                    break
                            except json.JSONDecodeError:
                                continue
                if original_entry:
                    break
            except (FileNotFoundError, IOError):
                continue

        if not original_entry:
            raise ValueError(f"Entry {outbox_id} not found")

        # Create updated version
        updated_entry = original_entry.copy()
        updated_entry["status"] = status
        updated_entry["sent_at"] = sent_at or datetime.utcnow().isoformat() + "Z"
        updated_entry["last_error"] = last_error
        updated_entry["smtp_response"] = smtp_response
        updated_entry["attempt_count"] = original_entry.get("attempt_count", 0) + 1

        # Append to current file
        self._append_entry(updated_entry)

    def get_pending_entries(self) -> List[Dict[str, Any]]:
        """
        Get all entries with status 'draft' or 'pending'.

        Returns:
            List of entry dicts
        """
        entries = []

        for jsonl_file in self.outbox_dir.glob("outbox_*.jsonl"):
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                if record.get("status") in ["draft", "pending"]:
                                    entries.append(record)
                            except json.JSONDecodeError:
                                continue
            except (FileNotFoundError, IOError):
                continue

        return entries

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get outbox statistics by status and skip reason.

        Returns:
            Dict with counts: total, draft, pending, sent, failed, skipped,
            by_skip_reason (dict)
        """
        stats = {
            "total": 0,
            "draft": 0,
            "pending": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "by_skip_reason": {},
        }

        for jsonl_file in self.outbox_dir.glob("outbox_*.jsonl"):
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                stats["total"] += 1
                                status = record.get("status", "unknown")
                                stats[status] = stats.get(status, 0) + 1

                                if status == "skipped":
                                    skip_reason = record.get("skip_reason", "unknown")
                                    stats["by_skip_reason"][skip_reason] = \
                                        stats["by_skip_reason"].get(skip_reason, 0) + 1
                            except json.JSONDecodeError:
                                continue
            except (FileNotFoundError, IOError):
                continue

        return stats

    def get_statistics_by_profile(self) -> Dict[str, Dict[str, Any]]:
        """
        Get outbox statistics broken down by profile.

        Returns:
            Dict mapping profile_id → stats dict
        """
        stats = {}

        for jsonl_file in self.outbox_dir.glob("outbox_*.jsonl"):
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                profile_id = record.get("profile_id", "unknown")
                                status = record.get("status", "unknown")

                                if profile_id not in stats:
                                    stats[profile_id] = {
                                        "total": 0,
                                        "draft": 0,
                                        "pending": 0,
                                        "sent": 0,
                                        "failed": 0,
                                        "skipped": 0,
                                    }

                                stats[profile_id]["total"] += 1
                                stats[profile_id][status] = stats[profile_id].get(status, 0) + 1
                            except json.JSONDecodeError:
                                continue
            except (FileNotFoundError, IOError):
                continue

        return stats
