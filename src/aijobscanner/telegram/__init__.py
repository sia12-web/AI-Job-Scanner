"""
Telegram module for AI Job Scanner.

Handles Telegram client operations including:
- Source validation
- Message ingestion
- Session management
"""

from .config import load_sources, save_sources, get_enabled_sources, update_source_validation
from .validate import SourceValidator

__all__ = [
    "load_sources",
    "save_sources",
    "get_enabled_sources",
    "update_source_validation",
    "SourceValidator",
]
