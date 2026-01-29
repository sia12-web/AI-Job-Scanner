"""
SQLite storage layer for AI Job Scanner.

Provides:
- Database initialization
- Cursor management (Single Source of Truth for ingestion state)
- Message storage with idempotency guarantees
- High water mark tracking
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple


def init_db(db_path: str) -> sqlite3.Connection:
    """
    Initialize SQLite database with required tables.

    Creates tables if they don't exist:
    - ingestion_cursors: Single Source of Truth for ingestion state
    - telegram_messages: Message storage with idempotency
    - message_classifications: Audit trail for classifications

    Args:
        db_path: Path to SQLite database file

    Returns:
        sqlite3.Connection: Database connection
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Create ingestion_cursors table (SSoT)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_cursors (
            source_id TEXT PRIMARY KEY,
            tg_chat_id INTEGER NOT NULL,
            last_message_id INTEGER NOT NULL DEFAULT 0,
            last_message_date TEXT,
            last_run_at TEXT,
            last_status TEXT,
            last_error TEXT
        )
    """)

    # Create telegram_messages table with idempotency
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            tg_chat_id INTEGER NOT NULL,
            tg_message_id INTEGER NOT NULL,
            date TEXT,
            sender_id INTEGER,
            text TEXT,
            permalink TEXT,
            raw_json TEXT,
            ingested_at TEXT NOT NULL,
            processed_status TEXT NOT NULL DEFAULT 'pending',
            is_ai_relevant INTEGER,
            ai_relevance_score REAL,
            classified_at TEXT,
            UNIQUE(source_id, tg_message_id)
        )
    """)

    # Add new columns if they don't exist (for existing databases)
    try:
        conn.execute("ALTER TABLE telegram_messages ADD COLUMN ai_relevance_score REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        conn.execute("ALTER TABLE telegram_messages ADD COLUMN classified_at TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create message_classifications table (audit trail)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS message_classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            tg_message_id INTEGER NOT NULL,
            tg_chat_id INTEGER NOT NULL,
            classifier_version TEXT NOT NULL,
            is_ai_relevant INTEGER NOT NULL,
            score REAL NOT NULL,
            reasons_json TEXT NOT NULL,
            classification_metadata TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(source_id, tg_message_id, classifier_version)
        )
    """)

    conn.commit()
    return conn


def get_cursor(conn: sqlite3.Connection, source_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve current cursor for a source.

    Args:
        conn: Database connection
        source_id: Source identifier from config YAML

    Returns:
        Dict with cursor fields or None if not found
    """
    cursor = conn.execute(
        "SELECT source_id, tg_chat_id, last_message_id, last_message_date, "
        "last_run_at, last_status, last_error FROM ingestion_cursors "
        "WHERE source_id = ?",
        (source_id,)
    )
    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "source_id": row[0],
        "tg_chat_id": row[1],
        "last_message_id": row[2],
        "last_message_date": row[3],
        "last_run_at": row[4],
        "last_status": row[5],
        "last_error": row[6],
    }


def upsert_cursor(
    conn: sqlite3.Connection,
    source_id: str,
    tg_chat_id: int,
    message_id: int,
    date: Optional[str] = None,
    status: str = "running",
    error: Optional[str] = None,
) -> None:
    """
    Update or insert cursor for a source.

    This is the SINGLE SOURCE OF TRUTH for ingestion state.

    Args:
        conn: Database connection
        source_id: Source identifier
        tg_chat_id: Telegram entity ID
        message_id: Highest message_id ingested (watermark)
        date: Date of last ingested message
        status: Status (running/success/failed)
        error: Error message if failed
    """
    now = datetime.utcnow().isoformat()

    conn.execute("""
        INSERT INTO ingestion_cursors
            (source_id, tg_chat_id, last_message_id, last_message_date, last_run_at, last_status, last_error)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source_id) DO UPDATE SET
            tg_chat_id = excluded.tg_chat_id,
            last_message_id = excluded.last_message_id,
            last_message_date = excluded.last_message_date,
            last_run_at = excluded.last_run_at,
            last_status = excluded.last_status,
            last_error = excluded.last_error
    """, (source_id, tg_chat_id, message_id, date, now, status, error))

    conn.commit()


def insert_message_if_new(
    conn: sqlite3.Connection,
    source_id: str,
    msg_dict: Dict[str, Any],
    sanitized_text: str,
    raw_json: str,
) -> bool:
    """
    Insert message if not already stored (idempotency guarantee).

    The UNIQUE(source_id, tg_message_id) constraint prevents duplicates.
    If the message already exists, this function does nothing.

    Args:
        conn: Database connection
        source_id: Source identifier
        msg_dict: Message data from Telethon
        sanitized_text: Sanitized message text
        raw_json: Raw message JSON

    Returns:
        bool: True if inserted, False if already existed
    """
    now = datetime.utcnow().isoformat()

    try:
        conn.execute("""
            INSERT INTO telegram_messages
                (source_id, tg_chat_id, tg_message_id, date, sender_id, text, permalink, raw_json, ingested_at, processed_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            source_id,
            msg_dict.get("tg_chat_id"),
            msg_dict.get("tg_message_id"),
            msg_dict.get("date"),
            msg_dict.get("sender_id"),
            sanitized_text,
            msg_dict.get("permalink"),
            raw_json,
            now,
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # UNIQUE constraint violated - message already exists
        return False


def get_high_water_marks(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Get high water marks for all sources.

    Returns:
        Dict mapping source_id to last_message_id
    """
    cursor = conn.execute(
        "SELECT source_id, last_message_id FROM ingestion_cursors"
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_message_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Get statistics about stored messages.

    Returns:
        Dict with total_messages, sources_count, pending_count, etc.
    """
    cursor = conn.execute("""
        SELECT
            COUNT(*) as total_messages,
            COUNT(DISTINCT source_id) as sources_count,
            SUM(CASE WHEN processed_status = 'pending' THEN 1 ELSE 0 END) as pending_count,
            SUM(CASE WHEN processed_status = 'classified' THEN 1 ELSE 0 END) as classified_count,
            SUM(CASE WHEN is_ai_relevant = 1 THEN 1 ELSE 0 END) as ai_relevant_count
        FROM telegram_messages
    """)
    row = cursor.fetchone()

    return {
        "total_messages": row[0] or 0,
        "sources_count": row[1] or 0,
        "pending_count": row[2] or 0,
        "classified_count": row[3] or 0,
        "ai_relevant_count": row[4] or 0,
    }


def fetch_pending_messages(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
    only_source_id: Optional[str] = None,
    reprocess: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch messages that need classification.

    Args:
        conn: Database connection
        limit: Maximum number of messages to fetch
        only_source_id: Filter to specific source
        reprocess: If True, fetch all messages; if False, only pending

    Returns:
        List of message dictionaries
    """
    query = """
        SELECT
            id, source_id, tg_chat_id, tg_message_id, date, text, permalink
        FROM telegram_messages
        WHERE 1=1
    """

    params = []

    if not reprocess:
        query += " AND processed_status = 'pending'"

    if only_source_id:
        query += " AND source_id = ?"
        params.append(only_source_id)

    query += " ORDER BY date DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "source_id": row[1],
            "tg_chat_id": row[2],
            "tg_message_id": row[3],
            "date": row[4],
            "text": row[5],
            "permalink": row[6],
        }
        for row in rows
    ]


def upsert_message_classification(
    conn: sqlite3.Connection,
    source_id: str,
    tg_message_id: int,
    tg_chat_id: int,
    classifier_version: str,
    is_ai_relevant: int,
    score: float,
    reasons: List[str],
    classification_metadata: Dict[str, Any],
) -> None:
    """
    Insert or update classification record in message_classifications table.

    Args:
        conn: Database connection
        source_id: Source identifier
        tg_message_id: Message ID from Telegram
        tg_chat_id: Telegram chat ID
        classifier_version: Version identifier for classifier
        is_ai_relevant: 0 or 1
        score: Relevance score
        reasons: List of reason strings
        classification_metadata: Dict with matched keywords, weights, etc.
    """
    now = datetime.utcnow().isoformat()
    reasons_json = json.dumps(reasons, ensure_ascii=False)
    metadata_json = json.dumps(classification_metadata, ensure_ascii=False)

    conn.execute("""
        INSERT INTO message_classifications
            (source_id, tg_message_id, tg_chat_id, classifier_version,
             is_ai_relevant, score, reasons_json, classification_metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source_id, tg_message_id, classifier_version) DO UPDATE SET
            is_ai_relevant = excluded.is_ai_relevant,
            score = excluded.score,
            reasons_json = excluded.reasons_json,
            classification_metadata = excluded.classification_metadata,
            created_at = excluded.created_at
    """, (
        source_id, tg_message_id, tg_chat_id, classifier_version,
        is_ai_relevant, score, reasons_json, metadata_json, now
    ))

    conn.commit()


def mark_message_classified(
    conn: sqlite3.Connection,
    source_id: str,
    tg_message_id: int,
    is_ai_relevant: int,
    score: float,
) -> None:
    """
    Update telegram_messages to mark as classified.

    Args:
        conn: Database connection
        source_id: Source identifier
        tg_message_id: Message ID from Telegram
        is_ai_relevant: 0 or 1
        score: Relevance score
    """
    now = datetime.utcnow().isoformat()

    conn.execute("""
        UPDATE telegram_messages
        SET processed_status = 'classified',
            is_ai_relevant = ?,
            ai_relevance_score = ?,
            classified_at = ?
        WHERE source_id = ? AND tg_message_id = ?
    """, (is_ai_relevant, score, now, source_id, tg_message_id))

    conn.commit()


def get_classification_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Get statistics about classifications.

    Returns:
        Dict with total, pending, classified, ai_relevant counts
    """
    cursor = conn.execute("""
        SELECT
            COUNT(*) as total_messages,
            SUM(CASE WHEN processed_status = 'pending' THEN 1 ELSE 0 END) as pending_count,
            SUM(CASE WHEN processed_status = 'classified' THEN 1 ELSE 0 END) as classified_count,
            SUM(CASE WHEN is_ai_relevant = 1 THEN 1 ELSE 0 END) as ai_relevant_count,
            SUM(CASE WHEN is_ai_relevant = 0 THEN 1 ELSE 0 END) as not_relevant_count,
            AVG(CASE WHEN ai_relevance_score IS NOT NULL THEN ai_relevance_score ELSE NULL END) as avg_score
        FROM telegram_messages
    """)
    row = cursor.fetchone()

    return {
        "total_messages": row[0] or 0,
        "pending_count": row[1] or 0,
        "classified_count": row[2] or 0,
        "ai_relevant_count": row[3] or 0,
        "not_relevant_count": row[4] or 0,
        "avg_score": round(row[5], 2) if row[5] else 0.0,
    }


def fetch_ai_relevant_messages(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch messages classified as AI-relevant.

    Args:
        conn: Database connection
        limit: Maximum number of messages to fetch

    Returns:
        List of message dictionaries
    """
    query = """
        SELECT
            id, source_id, tg_message_id, date, text,
            ai_relevance_score, permalink, classified_at
        FROM telegram_messages
        WHERE is_ai_relevant = 1
        ORDER BY ai_relevance_score DESC, date DESC
    """

    params = []
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "source_id": row[1],
            "tg_message_id": row[2],
            "date": row[3],
            "text": row[4],
            "score": row[5],
            "permalink": row[6],
            "classified_at": row[7],
        }
        for row in rows
    ]
