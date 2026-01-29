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
)

__all__ = [
    "init_db",
    "get_cursor",
    "upsert_cursor",
    "insert_message_if_new",
    "get_high_water_marks",
]
