"""
Telegram module for AI Job Scanner.

Handles Telegram client operations including:
- Source validation
- Message ingestion
- Session management
"""

from .config import load_sources, save_sources, get_enabled_sources, update_source_validation
from .validate import SourceValidator
from .ingest import MessageIngestor, sanitize_text

__all__ = [
    "load_sources",
    "save_sources",
    "get_enabled_sources",
    "update_source_validation",
    "SourceValidator",
    "MessageIngestor",
    "sanitize_text",
]
