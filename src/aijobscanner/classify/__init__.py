"""
Classification module for AI Job Scanner.

Handles heuristic classification of job messages for AI/automation relevance.
"""

from .rules import classify, ClassificationResult, KEYWORD_GROUPS, get_keyword_groups, add_keyword
from .run import MessageClassifier

__all__ = [
    "classify",
    "ClassificationResult",
    "KEYWORD_GROUPS",
    "get_keyword_groups",
    "add_keyword",
    "MessageClassifier",
]
