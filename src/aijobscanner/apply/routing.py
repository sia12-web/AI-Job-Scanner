"""
Profile routing and scoring logic for auto-apply system.

Implements deterministic keyword-based scoring with ambiguity detection
to prevent cross-contamination between applicant profiles.
"""

import re
from typing import Dict, List, Any, Optional


def score_profile(text: str, profile: Dict[str, Any]) -> float:
    """
    Score a message against a profile using keyword matching.

    Scoring algorithm:
    - Positive keyword match: +1.0
    - Negative keyword match: -1.5 (stronger weight to prevent false positives)

    Args:
        text: Message text to score
        profile: Profile dict with keywords_positive and keywords_negative lists

    Returns:
        float: Profile score (can be negative)
    """
    score = 0.0
    text_lower = text.lower()

    # Count positive matches
    for keyword in profile.get("keywords_positive", []):
        # Use word boundary matching to avoid substring matches
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, text_lower):
            score += 1.0

    # Subtract negative matches (1.5x weight)
    for keyword in profile.get("keywords_negative", []):
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, text_lower):
            score -= 1.5

    return score


def route_message(
    text: str,
    profiles: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Route a message to the appropriate profile.

    Implements ambiguity detection to prevent cross-contamination:
    - If both profiles score ≥ threshold → SKIP (ambiguous_both_match)
    - If neither scores ≥ threshold → SKIP (no_match)
    - If scores too close (within 0.1) → SKIP (tie_close)
    - Otherwise → Route to clear winner

    Args:
        text: Message text to route
        profiles: Dict of profile_id → profile config

    Returns:
        Dict with:
            - profile_id: str | None (winner or None if skipped)
            - skip_reason: str | None (why routing failed)
            - scores: Dict[profile_id, float] (all profile scores)
            - routing_metadata: Dict (decision details)
    """
    # Score all profiles
    scores = {}
    for profile_id, profile in profiles.items():
        scores[profile_id] = score_profile(text, profile)

    # Find profiles above threshold
    above_threshold = {
        pid: score
        for pid, score in scores.items()
        if score >= profiles[pid].get("threshold", 0.7)
    }

    # Decision logic
    if not above_threshold:
        return {
            "profile_id": None,
            "skip_reason": "no_match",
            "scores": scores,
            "routing_metadata": {
                "decision": "no_profile_above_threshold",
                "threshold_used": profiles.get(list(profiles.keys())[0], {}).get("threshold", 0.7)
            }
        }

    if len(above_threshold) > 1:
        # Multiple profiles above threshold - check for ambiguity
        sorted_scores = sorted(above_threshold.values(), reverse=True)

        # Check if top 2 are too close (within 0.1)
        if len(sorted_scores) >= 2 and abs(sorted_scores[0] - sorted_scores[1]) < 0.1:
            return {
                "profile_id": None,
                "skip_reason": "tie_close",
                "scores": scores,
                "routing_metadata": {
                    "decision": "scores_too_close",
                    "top_scores": sorted_scores[:2],
                    "margin": abs(sorted_scores[0] - sorted_scores[1])
                }
            }

        # Clear winner exists despite multiple above threshold
        winner_id = max(above_threshold, key=above_threshold.get)
        return {
            "profile_id": winner_id,
            "skip_reason": None,
            "scores": scores,
            "routing_metadata": {
                "decision": "clear_winner",
                "matched_profiles": list(above_threshold.keys()),
                "winner_margin": sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else 0
            }
        }

    # Single profile above threshold
    winner_id = list(above_threshold.keys())[0]
    return {
        "profile_id": winner_id,
        "skip_reason": None,
        "scores": scores,
        "routing_metadata": {
            "decision": "single_match",
            "score": above_threshold[winner_id]
        }
    }


def extract_emails(text: str) -> List[str]:
    """
    Extract all email addresses from text using regex.

    Args:
        text: Message text to search

    Returns:
        List of unique email addresses (order preserved)
    """
    # Email regex pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    # Find all matches
    emails = re.findall(email_pattern, text, re.IGNORECASE)

    # Deduplicate while preserving order
    seen = set()
    unique_emails = []
    for email in emails:
        if email.lower() not in seen:
            seen.add(email.lower())
            unique_emails.append(email)

    return unique_emails


def select_email(
    emails: List[str],
    pick_index: Optional[int] = None
) -> Optional[str]:
    """
    Select an email from extracted emails with safety rules.

    Safety rules:
    - 0 emails → Return None
    - 1 email → Use it
    - 2+ emails without pick_index → Return None (ambiguous)
    - 2+ emails with pick_index → Use selected index

    Args:
        emails: List of extracted email addresses
        pick_index: User-specified index (from --pick-email flag)

    Returns:
        Selected email or None if ambiguous/invalid

    Raises:
        ValueError: If pick_index is out of range
    """
    if not emails:
        return None

    if len(emails) == 1:
        return emails[0]

    # Multiple emails
    if pick_index is None:
        # Ambiguous - caller should skip
        return None

    # User specified index
    if pick_index < 0 or pick_index >= len(emails):
        raise ValueError(
            f"pick_index {pick_index} out of range [0, {len(emails) - 1}]"
        )

    return emails[pick_index]
