"""
Storage layer for AI Job Scanner.

Handles persistent storage including:
- SQLite database management
- Message storage and retrieval
- Cursor tracking for incremental ingestion
"""

from .sqlite import (
    init_db,
    get_cursor,
    upsert_cursor,
    insert_message_if_new,
    get_high_water_marks,
    get_message_stats,
    fetch_pending_messages,
    upsert_message_classification,
    mark_message_classified,
    get_classification_statistics,
    fetch_ai_relevant_messages,
)

__all__ = [
    "init_db",
    "get_cursor",
    "upsert_cursor",
    "insert_message_if_new",
    "get_high_water_marks",
    "get_message_stats",
    "fetch_pending_messages",
    "upsert_message_classification",
    "mark_message_classified",
    "get_classification_statistics",
    "fetch_ai_relevant_messages",
]
