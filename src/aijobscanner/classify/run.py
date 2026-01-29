"""
Classification orchestrator for AI Job Scanner.

Handles batch classification of messages and CSV export.
"""

import os
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from storage import (
    init_db,
    fetch_pending_messages,
    upsert_message_classification,
    mark_message_classified,
    get_classification_statistics,
    fetch_ai_relevant_messages,
)
from .rules import classify, ClassificationResult


CLASSIFIER_VERSION = "1.0.0"


class MessageClassifier:
    """
    Orchestrates message classification and CSV export.

    Features:
    - Batch classification of pending messages
    - Idempotent processing (skip already-classified unless --reprocess)
    - CSV export with formula injection mitigation
    - Audit trail in message_classifications table
    """

    def __init__(self, db_path: str):
        """
        Initialize classifier.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.conn = None
        self.results = {
            "processed": 0,
            "ai_relevant": 0,
            "not_relevant": 0,
            "errors": 0,
        }

    def connect(self):
        """Initialize database connection."""
        self.conn = init_db(self.db_path)

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def classify_batch(
        self,
        limit: Optional[int] = None,
        only_source_id: Optional[str] = None,
        reprocess: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Classify a batch of messages.

        Args:
            limit: Maximum messages to process
            only_source_id: Filter to specific source
            reprocess: Reprocess already-classified messages
            dry_run: Don't write to database

        Returns:
            Dict with processing results
        """
        # Reset results
        self.results = {
            "processed": 0,
            "ai_relevant": 0,
            "not_relevant": 0,
            "errors": 0,
        }

        # Fetch messages
        messages = fetch_pending_messages(
            self.conn,
            limit=limit,
            only_source_id=only_source_id,
            reprocess=reprocess,
        )

        print(f"\n[INFO] Processing {len(messages)} message(s)")

        for msg in messages:
            try:
                # Classify
                result: ClassificationResult = classify(msg["text"])

                if not dry_run:
                    # Write to message_classifications (audit trail)
                    upsert_message_classification(
                        self.conn,
                        source_id=msg["source_id"],
                        tg_message_id=msg["tg_message_id"],
                        tg_chat_id=msg["tg_chat_id"],
                        classifier_version=CLASSIFIER_VERSION,
                        is_ai_relevant=result.is_ai_relevant,
                        score=result.score,
                        reasons=result.reasons,
                        classification_metadata=result.metadata,
                    )

                    # Update telegram_messages
                    mark_message_classified(
                        self.conn,
                        source_id=msg["source_id"],
                        tg_message_id=msg["tg_message_id"],
                        is_ai_relevant=result.is_ai_relevant,
                        score=result.score,
                    )

                # Update counters
                self.results["processed"] += 1
                if result.is_ai_relevant == 1:
                    self.results["ai_relevant"] += 1
                else:
                    self.results["not_relevant"] += 1

            except Exception as e:
                print(f"   [WARN] Error processing message {msg['tg_message_id']}: {e}")
                self.results["errors"] += 1

        return self.results

    def export_candidates_to_csv(
        self,
        export_dir: str,
        export_limit: Optional[int] = None,
    ) -> Optional[str]:
        """
        Export AI-relevant candidates to CSV.

        Args:
            export_dir: Directory to write CSV file
            export_limit: Max candidates to export

        Returns:
            Path to CSV file or None if no candidates
        """
        # Fetch AI-relevant messages
        candidates = fetch_ai_relevant_messages(
            self.conn,
            limit=export_limit,
        )

        if not candidates:
            print("\n[INFO] No AI-relevant candidates to export")
            return None

        # Create export directory
        Path(export_dir).mkdir(parents=True, exist_ok=True)

        # Generate CSV filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(export_dir, f"candidates_{timestamp}.csv")

        # Write CSV with security measures
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)

            # Header
            writer.writerow([
                "source_id",
                "tg_message_id",
                "date",
                "score",
                "snippet",
                "reasons",
                "matched_keywords",
                "permalink",
            ])

            # Rows
            for candidate in candidates:
                # Truncate and sanitize snippet
                snippet = candidate["text"] or ""
                snippet = snippet.replace("\n", " ").replace("\r", " ")  # Strip newlines
                snippet = snippet[:200]  # Truncate to 200 chars

                # Formula injection mitigation
                snippet = mitigate_formula_injection(snippet)

                # Reasons as comma-separated
                reasons = ", ".join(candidate.get("reasons", []))

                # Get classification metadata
                # (This would need to be fetched from message_classifications table)
                matched_keywords = "N/A"  # Placeholder

                # Permalink
                permalink = candidate.get("permalink", "")

                writer.writerow([
                    candidate["source_id"],
                    candidate["tg_message_id"],
                    candidate["date"],
                    candidate["score"],
                    snippet,
                    reasons,
                    matched_keywords,
                    permalink,
                ])

        print(f"\n[EXPORT] Exported {len(candidates)} candidate(s) to: {csv_path}")
        return csv_path


def mitigate_formula_injection(value: str) -> str:
    """
    Mitigate CSV formula injection by prefixing dangerous cells.

    Excel treats cells starting with =, +, -, @ as formulas.
    Prefix with single quote to treat as text.

    Args:
        value: Cell value

    Returns:
        Safe value
    """
    if not value:
        return value

    # Check if starts with formula character
    if value[0] in "=+@":
        return f"'{value}"

    return value


def update_project_track_with_classification(
    project_track_path: str,
    results: Dict[str, Any],
    stats: Dict[str, Any],
) -> None:
    """
    Update project_track.md with classification run summary.

    Args:
        project_track_path: Path to project_track.md
        results: Classification results
        stats: Database statistics
    """
    try:
        with open(project_track_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Generate summary
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        summary_lines = [
            f"\n**Last Run**: {timestamp}\n",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Total Messages | {stats['total_messages']} |",
            f"| Pending | {stats['pending_count']} |",
            f"| Classified | {stats['classified_count']} |",
            f"| AI Relevant | {stats['ai_relevant_count']} |",
            f"| Not Relevant | {stats['not_relevant_count']} |",
            f"| Avg Score | {stats['avg_score']} |",
            "",
            "**This Run**:",
            f"| Processed | {results['processed']} |",
            f"| AI Relevant Found | {results['ai_relevant']} |",
            f"| Not Relevant | {results['not_relevant']} |",
            f"| Errors | {results['errors']} |",
        ]

        summary = "\n".join(summary_lines)

        # Check if markers exist
        start_marker = "<!-- CLASSIFICATION_LAST_RUN_START -->"
        end_marker = "<!-- CLASSIFICATION_LAST_RUN_END -->"

        if start_marker in content and end_marker in content:
            # Replace content between markers
            start_idx = content.find(start_marker)
            end_idx = content.find(end_marker) + len(end_marker)

            new_content = content[:start_idx] + start_marker + summary + "\n" + end_marker + content[end_idx:]

            with open(project_track_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        else:
            # Append markers and summary at end
            new_section = f"\n{start_marker}\n{summary}\n{end_marker}\n"

            with open(project_track_path, "a", encoding="utf-8") as f:
                f.write(new_section)

    except Exception as e:
        print(f"[WARN] Failed to update project_track.md: {e}")
