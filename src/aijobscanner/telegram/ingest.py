"""
Message ingestion module for AI Job Scanner.

Handles incremental message reading from Telegram sources with:
- Cursor-based incremental reading (only NEW messages)
- Message sanitization to avoid sensitive data retention
- Idempotent storage via SQLite
- Report generation
"""

import os
import re
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from telethon import TelegramClient, errors
from telethon.tl.types import Message

import sys
from pathlib import Path
# Add parent directories to path for storage module
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from storage import init_db, get_cursor, upsert_cursor, insert_message_if_new


def sanitize_text(text: str) -> Tuple[str, Dict[str, bool]]:
    """
    Sanitize message text to avoid persisting sensitive data.

    Redacts patterns that look like:
    - Login codes (5-6 digits)
    - Telegram verification codes
    - Password reset codes
    - Verification codes

    Args:
        text: Original message text

    Returns:
        Tuple of (sanitized_text, flags_dict)
    """
    if not text:
        return "", {}

    patterns = [
        # "login code" + 5-6 digits
        (r'login code\s+(\d{5,6})', '[LOGIN CODE REDACTED]'),
        # "Telegram code" + 5-6 digits
        (r'Telegram code\s+(\d{5,6})', '[TELEGRAM CODE REDACTED]'),
        # "code:" + 5-6 digits
        (r'code:\s*(\d{5,6})', 'code: [REDACTED]'),
        # "verification code:" + 5-6 digits
        (r'verification code:\s*(\d{5,6})', 'verification code: [REDACTED]'),
        # "reset code" + 5-6 digits
        (r'reset code\s+(\d{5,6})', '[RESET CODE REDACTED]'),
    ]

    sanitized = text
    flags = {"sanitized": False}

    for pattern, replacement in patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            flags["sanitized"] = True
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Keep the format but redact digits
                redacted = re.sub(r'\d{5,6}', '[REDACTED]', match.group(0))
                sanitized = re.sub(pattern, redacted, sanitized, flags=re.IGNORECASE)

    return sanitized, flags


class MessageIngestor:
    """
    Incremental message ingestion from Telegram sources.

    Features:
    - Cursor-based reading (only fetch messages newer than cursor)
    - Message sanitization for sensitive data
    - Idempotent storage
    - Rate limit handling (FloodWaitError)
    - Report generation
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_dir: str,
        two_fa_password: Optional[str] = None,
    ):
        """
        Initialize MessageIngestor.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            phone: Phone number (with country code, e.g., +1234567890)
            session_dir: Directory for session files
            two_fa_password: Optional 2FA password
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_dir = session_dir
        self.two_fa_password = two_fa_password

        # Create session directory if not exists
        Path(session_dir).mkdir(parents=True, exist_ok=True)

        # Initialize Telethon client
        session_name = phone.replace("+", "")
        session_path = os.path.join(session_dir, session_name)

        self.client = TelegramClient(
            session_path,
            api_id,
            api_hash,
        )

    async def connect(self) -> None:
        """
        Connect to Telegram using existing session.

        Expects session file to already exist from validation step.
        """
        await self.client.connect()

        # Check if already authorized
        if not await self.client.is_user_authorized():
            raise RuntimeError(
                "Session not authorized. Please run validation first to create session."
            )

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        await self.client.disconnect()

    async def _resolve_entity(
        self,
        source_config: Dict[str, Any],
    ) -> Any:
        """
        Resolve Telegram entity from source config.

        Uses resolved_entity_id if available (from validation step),
        otherwise falls back to public_handle or invite_link.

        Args:
            source_config: Source configuration dict

        Returns:
            Telegram entity (Chat, Channel, etc.)
        """
        # Prefer resolved_entity_id from validation
        if source_config.get("resolved_entity_id"):
            entity_id = source_config["resolved_entity_id"]
            # For channels, need to use entity ID directly
            return await self.client.get_entity(entity_id)

        # Fall back to public_handle
        if source_config.get("public_handle"):
            handle = source_config["public_handle"]
            return await self.client.get_entity(handle)

        # Fall back to invite link (for groups)
        if source_config.get("invite_link"):
            # For groups with invite links, we should have resolved_entity_id
            raise ValueError(
                f"Source {source_config['source_id']} has invite_link but no resolved_entity_id. "
                "Please run validation first."
            )

        raise ValueError(
            f"Cannot resolve entity for {source_config['source_id']}: "
            "no resolved_entity_id, public_handle, or invite_link"
        )

    async def ingest_source(
        self,
        source_config: Dict[str, Any],
        db_conn,
        limit: int = 200,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest messages from a single source.

        Args:
            source_config: Source configuration dict
            db_conn: SQLite database connection
            limit: Maximum messages to fetch
            dry_run: If True, don't write to DB

        Returns:
            Dict with ingestion results
        """
        source_id = source_config["source_id"]
        result = {
            "source_id": source_id,
            "display_name": source_config.get("display_name", "Unknown"),
            "source_type": source_config.get("type", "unknown"),
            "fetched": 0,
            "new_inserted": 0,
            "skipped": 0,
            "errors": 0,
            "high_water_mark": None,
            "error_message": None,
        }

        try:
            # Get current cursor (skip for dry-run)
            if dry_run:
                last_message_id = 0
                last_message_date = None
            else:
                cursor = get_cursor(db_conn, source_id)

                if cursor is None:
                    last_message_id = 0
                    last_message_date = None
                else:
                    last_message_id = cursor["last_message_id"]
                    last_message_date = cursor["last_message_date"]

            print(f"   [INFO] Current cursor: message_id={last_message_id}")

            # Resolve Telegram entity
            entity = await self._resolve_entity(source_config)
            tg_chat_id = source_config.get(
                "resolved_entity_id",
                source_config.get("tg_chat_id")
            )

            if tg_chat_id is None:
                # Try to get from entity
                tg_chat_id = getattr(entity, 'id', None)

            print(f"   [INFO] Fetching messages (limit={limit}, min_id={last_message_id + 1})")

            # Fetch messages incrementally (only NEW messages)
            messages = []
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                min_id=last_message_id,  # Only fetch messages newer than cursor
                reverse=True,  # Fetch in chronological order
            ):
                messages.append(message)

            result["fetched"] = len(messages)

            if not messages:
                print(f"   [INFO] No new messages")
                result["high_water_mark"] = last_message_id
                if not dry_run:
                    upsert_cursor(
                        db_conn,
                        source_id,
                        tg_chat_id,
                        last_message_id,
                        last_message_date,
                        status="success",
                    )
                return result

            # Process each message
            for msg in messages:
                try:
                    # Skip messages without text (e.g., media-only)
                    if not msg.text:
                        result["skipped"] += 1
                        continue

                    # Build message dict
                    msg_dict = {
                        "tg_chat_id": tg_chat_id,
                        "tg_message_id": msg.id,
                        "date": msg.date.isoformat() if msg.date else None,
                        "sender_id": msg.sender_id,
                        "permalink": f"https://t.me/{source_config.get('public_handle', 'c')}/{msg.id}" if source_config.get("public_handle") else None,
                    }

                    # Sanitize text
                    sanitized_text, flags = sanitize_text(msg.text)

                    # Convert to JSON for raw storage
                    raw_json = json.dumps({
                        "id": msg.id,
                        "date": msg.date.isoformat() if msg.date else None,
                        "message": msg.text,
                        "sender_id": msg.sender_id,
                    }, ensure_ascii=False)

                    # Insert to database (idempotent)
                    if not dry_run:
                        inserted = insert_message_if_new(
                            db_conn,
                            source_id,
                            msg_dict,
                            sanitized_text,
                            raw_json,
                        )
                        if inserted:
                            result["new_inserted"] += 1
                        else:
                            result["skipped"] += 1
                    else:
                        # Dry run - count as would be inserted
                        result["new_inserted"] += 1

                except Exception as e:
                    print(f"   [WARN] Error processing message {msg.id}: {e}")
                    result["errors"] += 1

            # Update cursor to highest message ID
            high_water_mark = max(msg.id for msg in messages)
            result["high_water_mark"] = high_water_mark

            # Get date of last message
            last_msg = max(messages, key=lambda m: m.date) if messages else None
            last_message_date = last_msg.date.isoformat() if last_msg and last_msg.date else None

            print(f"   [INFO] High water mark: {high_water_mark}")

            if not dry_run:
                upsert_cursor(
                    db_conn,
                    source_id,
                    tg_chat_id,
                    high_water_mark,
                    last_message_date,
                    status="success",
                )

        except errors.FloodWaitError as e:
            # Telegram rate limit - wait and retry
            wait_time = e.seconds
            print(f"   [WAIT] FloodWaitError: waiting {wait_time}s")
            result["error_message"] = f"FloodWaitError: {wait_time}s"

            # Don't auto-wait - let user retry manually
            if not dry_run:
                upsert_cursor(
                    db_conn,
                    source_id,
                    source_config.get("resolved_entity_id", 0),
                    0,
                    None,
                    status="failed",
                    error=f"FloodWaitError: {wait_time}s",
                )
            raise

        except Exception as e:
            error_msg = str(e)
            print(f"   [FAIL] {error_msg}")
            result["error_message"] = error_msg
            result["errors"] += 1

            if not dry_run:
                upsert_cursor(
                    db_conn,
                    source_id,
                    source_config.get("resolved_entity_id", 0),
                    0,
                    None,
                    status="failed",
                    error=error_msg,
                )

        return result

    async def ingest_all(
        self,
        sources: List[Dict[str, Any]],
        db_path: str,
        limit: int = 200,
        dry_run: bool = False,
        force: bool = False,
        only_source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ingest messages from all enabled sources.

        Args:
            sources: List of source configs
            db_path: Path to SQLite database
            limit: Max messages per source
            dry_run: If True, don't write to DB
            force: If True, ignore validation_status
            only_source: If set, only ingest this source

        Returns:
            List of ingestion results (one per source)
        """
        # Initialize database
        if not dry_run:
            db_conn = init_db(db_path)
        else:
            db_conn = None

        results = []

        # Filter sources
        if only_source:
            sources = [s for s in sources if s["source_id"] == only_source]
            if not sources:
                raise ValueError(f"Source not found: {only_source}")

        # Filter enabled and validated
        if not force:
            sources = [
                s for s in sources
                if s.get("enabled", True)
                and s.get("validation_status") in ("joined", "not_applicable")
            ]
        else:
            sources = [s for s in sources if s.get("enabled", True)]

        print(f"\n[INFO] Ingesting from {len(sources)} source(s)")

        for source in sources:
            print(f"\n[{source.get('type', 'source').upper()}] {source.get('display_name', source['source_id'])}")
            print(f"   Source ID: {source['source_id']}")

            if not dry_run:
                result = await self.ingest_source(source, db_conn, limit, dry_run)
            else:
                # For dry run, create a mock connection
                result = await self.ingest_source(source, None, limit, dry_run=True)

            results.append(result)

        return results

    def write_report(
        self,
        results: List[Dict[str, Any]],
        report_dir: str,
    ) -> str:
        """
        Write ingestion report to JSON file.

        Args:
            results: List of ingestion results
            report_dir: Report directory path

        Returns:
            Path to report file
        """
        Path(report_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(report_dir, f"ingestion_report_{timestamp}.json")

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_sources": len(results),
                "total_fetched": sum(r.get("fetched", 0) for r in results),
                "total_inserted": sum(r.get("new_inserted", 0) for r in results),
                "total_skipped": sum(r.get("skipped", 0) for r in results),
                "total_errors": sum(r.get("errors", 0) for r in results),
                "sources_with_errors": sum(1 for r in results if r.get("errors", 0) > 0),
            },
            "results": results,
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report_path
