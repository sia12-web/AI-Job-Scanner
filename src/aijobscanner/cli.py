"""
CLI entrypoint for AI Job Scanner.

Provides command-line interface for source validation.
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from aijobscanner.telegram import (
    load_sources,
    save_sources,
    get_enabled_sources,
    update_source_validation,
    SourceValidator,
    MessageIngestor,
)

from aijobscanner.classify import MessageClassifier

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from storage import get_classification_statistics
from aijobscanner.classify.run import update_project_track_with_classification


def print_summary(results: list) -> None:
    """Print validation summary to console."""
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    total = len(results)
    joined = sum(1 for r in results if r["validation_status"] == "joined")
    failed = sum(1 for r in results if r["validation_status"] == "join_failed")
    blocked = sum(1 for r in results if r["validation_status"] == "blocked")

    print(f"\nTotal sources checked: {total}")
    print(f"[OK] Joined: {joined}")
    print(f"[FAIL] Failed: {failed}")
    print(f"[BLOCKED] Blocked: {blocked}")

    print("\n" + "-" * 60)
    print("PER-SOURCE RESULTS:")
    print("-" * 60)

    for result in results:
        status_symbol = {
            "joined": "[OK]",
            "join_failed": "[FAIL]",
            "blocked": "[BLOCKED]",
        }.get(result["validation_status"], "[?]")

        print(f"\n{status_symbol} {result['display_name']} ({result['source_id']})")
        print(f"   Status: {result['validation_status']}")
        print(f"   Type: {result.get('source_type', 'unknown')}")
        print(f"   Messages readable: {result.get('messages_readable', False)}")
        print(f"   Message count: {result.get('message_count', 0)}")

        if result.get("last_error"):
            print(f"   Error: {result['last_error']}")

        if result.get("resolved_entity_id"):
            print(f"   Entity ID: {result['resolved_entity_id']} ({result.get('resolved_entity_type', 'unknown')})")

        if result.get("last_validated_at"):
            print(f"   Validated at: {result['last_validated_at']}")


async def validate_sources_command(args) -> int:
    """
    Execute the validate-sources command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Load environment variables
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    phone = os.getenv("TG_PHONE")
    two_fa_password = os.getenv("TG_2FA_PASSWORD")
    session_dir = os.getenv("TG_SESSION_DIR", "./data/telegram_session")

    # Validate required environment variables
    if not api_id or not api_hash or not phone:
        print("[ERROR] Missing required environment variables.")
        print("\nPlease set the following in your .env file:")
        print("  - TG_API_ID")
        print("  - TG_API_HASH")
        print("  - TG_PHONE")
        print("\nGet API credentials from: https://my.telegram.org/apps")
        return 1

    try:
        api_id = int(api_id)
    except ValueError:
        print(f"[ERROR] Invalid TG_API_ID: '{api_id}' must be an integer")
        return 1

    # Load sources configuration
    try:
        config = load_sources(args.sources)
        print(f"[OK] Loaded configuration from: {args.sources}")
    except Exception as e:
        print(f"[ERROR] Failed to load configuration: {e}")
        return 1

    # Get enabled sources
    sources = get_enabled_sources(config)

    if not sources:
        print("[ERROR] No enabled sources found in configuration")
        return 1

    # Filter by source_id if --only specified
    if args.only:
        sources = [s for s in sources if s.get("source_id") == args.only]
        if not sources:
            print(f"[ERROR] No enabled source found with ID: {args.only}")
            return 1

    print(f"\n[INFO] Found {len(sources)} enabled source(s) to validate")

    # Initialize validator
    validator = SourceValidator(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        session_dir=session_dir,
        two_fa_password=two_fa_password,
    )

    try:
        # Connect to Telegram
        await validator.connect()

        # Validate all sources
        results = await validator.validate_all(
            sources=sources,
            only_id=args.only,
            message_limit=args.limit,
        )

        if not results:
            print("\n⚠️  No validation results")
            return 1

        # Disconnect
        await validator.disconnect()

        # Print summary
        print_summary(results)

        # Write report
        report_path = validator.write_report(results, args.report_dir)
        print(f"\n[REPORT] Report written to: {report_path}")

        # Write back to YAML if --write-back specified
        if args.write_back:
            if args.dry_run:
                print("\n[DRY-RUN] Skipping YAML update (use --write-back without --dry-run)")
            else:
                print(f"\n[SAVE] Updating YAML: {args.sources}")

                for result in results:
                    update_source_validation(
                        config,
                        result["source_id"],
                        result["validation_status"],
                        result["last_validated_at"],
                        result.get("last_error"),
                        result.get("resolved_entity_id"),
                        result.get("resolved_entity_type"),
                    )

                save_sources(args.sources, config)
                print("[OK] Configuration updated")
        else:
            if args.dry_run:
                print("\n[DRY-RUN] YAML not modified (add --write-back to update)")

        return 0

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Validation cancelled by user")
        await validator.disconnect()
        return 130

    except Exception as e:
        print(f"\n[ERROR] Validation failed: {e}")
        import traceback
        traceback.print_exc()

        try:
            await validator.disconnect()
        except:
            pass

        return 1


async def ingest_sources_command(args) -> int:
    """
    Execute the ingest command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Load environment variables
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    phone = os.getenv("TG_PHONE")
    two_fa_password = os.getenv("TG_2FA_PASSWORD")
    session_dir = os.getenv("TG_SESSION_DIR", "./data/telegram_session")

    # Validate required environment variables
    if not api_id or not api_hash or not phone:
        print("[ERROR] Missing required environment variables.")
        print("\nPlease set the following in your .env file:")
        print("  - TG_API_ID")
        print("  - TG_API_HASH")
        print("  - TG_PHONE")
        print("\nGet API credentials from: https://my.telegram.org/apps")
        return 1

    try:
        api_id = int(api_id)
    except ValueError:
        print(f"[ERROR] Invalid TG_API_ID: '{api_id}' must be an integer")
        return 1

    # Load sources configuration
    try:
        config = load_sources(args.sources)
        print(f"[OK] Loaded configuration from: {args.sources}")
    except Exception as e:
        print(f"[ERROR] Failed to load configuration: {e}")
        return 1

    # Get enabled sources
    sources = get_enabled_sources(config)

    if not sources:
        print("[ERROR] No enabled sources found in configuration")
        return 1

    print(f"\n[INFO] Found {len(sources)} enabled source(s)")

    # Initialize ingestor
    ingestor = MessageIngestor(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        session_dir=session_dir,
        two_fa_password=two_fa_password,
    )

    try:
        # Connect to Telegram
        print("\n[INFO] Connecting to Telegram...")
        await ingestor.connect()

        # Ingest messages
        print(f"\n[INFO] Starting ingestion (dry-run={args.dry_run})")

        results = await ingestor.ingest_all(
            sources=sources,
            db_path=args.db,
            limit=args.limit_per_source,
            dry_run=args.dry_run,
            force=args.force,
            only_source=args.only,
        )

        # Disconnect
        await ingestor.disconnect()

        # Print summary
        print("\n" + "=" * 60)
        print("INGESTION SUMMARY")
        print("=" * 60)

        total_fetched = sum(r.get("fetched", 0) for r in results)
        total_inserted = sum(r.get("new_inserted", 0) for r in results)
        total_skipped = sum(r.get("skipped", 0) for r in results)
        total_errors = sum(r.get("errors", 0) for r in results)

        print(f"\nTotal sources processed: {len(results)}")
        print(f"Total messages fetched: {total_fetched}")
        print(f"New messages inserted: {total_inserted}")
        print(f"Messages skipped (duplicates/no text): {total_skipped}")
        print(f"Errors: {total_errors}")

        print("\n" + "-" * 60)
        print("PER-SOURCE RESULTS:")
        print("-" * 60)

        for result in results:
            status_symbol = "[OK]" if result.get("errors", 0) == 0 else "[FAIL]"

            print(f"\n{status_symbol} {result['display_name']} ({result['source_id']})")
            print(f"   Type: {result.get('source_type', 'unknown')}")
            print(f"   Fetched: {result.get('fetched', 0)}")
            print(f"   Inserted: {result.get('new_inserted', 0)}")
            print(f"   Skipped: {result.get('skipped', 0)}")
            print(f"   High water mark: {result.get('high_water_mark', 'N/A')}")

            if result.get("error_message"):
                print(f"   Error: {result['error_message']}")

        # Write report
        report_path = ingestor.write_report(results, args.report_dir)
        print(f"\n[REPORT] Report written to: {report_path}")

        # Update project_track.md if requested
        if args.update_project_track:
            print(f"\n[INFO] Updating project_track.md...")
            update_project_track_with_ingestion(
                args.update_project_track,
                results,
            )
            print("[OK] project_track.md updated")

        return 0

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Ingestion cancelled by user")
        await ingestor.disconnect()
        return 130

    except Exception as e:
        print(f"\n[ERROR] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()

        try:
            await ingestor.disconnect()
        except:
            pass

        return 1


def update_project_track_with_ingestion(
    project_track_path: str,
    results: list,
) -> None:
    """
    Update project_track.md with ingestion run summary.

    Uses markers to locate and replace the ingestion summary section.

    Args:
        project_track_path: Path to project_track.md
        results: Ingestion results list
    """
    try:
        with open(project_track_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Generate summary
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        summary_lines = [
            f"\n**Last Run**: {timestamp}\n",
            "| Source ID | Type | Fetched | Inserted | Skipped | High Water Mark | Status |",
            "|-----------|------|---------|----------|---------|-----------------|--------|",
        ]

        for result in results:
            status = "[OK]" if result.get("errors", 0) == 0 else "[FAIL]"
            summary_lines.append(
                f"| {result['source_id']} | {result.get('source_type', 'unknown')} | "
                f"{result.get('fetched', 0)} | {result.get('new_inserted', 0)} | "
                f"{result.get('skipped', 0)} | {result.get('high_water_mark', 'N/A')} | "
                f"{status} |"
            )

        summary = "\n".join(summary_lines)

        # Check if markers exist
        start_marker = "<!-- INGESTION_LAST_RUN_START -->"
        end_marker = "<!-- INGESTION_LAST_RUN_END -->"

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


def classify_command(args) -> int:
    """
    Execute the classify command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Initialize classifier
    classifier = MessageClassifier(args.db)

    try:
        # Connect to database
        classifier.connect()

        # Get initial statistics
        stats_before = get_classification_statistics(classifier.conn)
        print(f"[INFO] Total messages in database: {stats_before['total_messages']}")
        print(f"[INFO] Pending classification: {stats_before['pending_count']}")
        print(f"[INFO] Already classified: {stats_before['classified_count']}")

        # Classify batch
        print(f"\n[INFO] Starting classification (dry-run={args.dry_run})")

        results = classifier.classify_batch(
            limit=args.limit,
            only_source_id=args.only,
            reprocess=args.reprocess,
            dry_run=args.dry_run,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("CLASSIFICATION SUMMARY")
        print("=" * 60)

        print(f"\nProcessed: {results['processed']}")
        print(f"[OK] AI Relevant: {results['ai_relevant']}")
        print(f"[INFO] Not Relevant: {results['not_relevant']}")
        print(f"[FAIL] Errors: {results['errors']}")

        # Export candidates if not dry-run and we have AI-relevant messages
        if not args.dry_run and results['ai_relevant'] > 0:
            print("\n[INFO] Exporting AI-relevant candidates to CSV...")
            csv_path = classifier.export_candidates_to_csv(
                export_dir=args.export_dir,
                export_limit=args.export_limit,
            )
            if csv_path:
                print(f"[OK] Exported to: {csv_path}")

        # Update project_track.md if requested
        if args.update_project_track and not args.dry_run:
            stats_after = get_classification_statistics(classifier.conn)

            print(f"\n[INFO] Updating project_track.md...")
            update_project_track_with_classification(
                args.update_project_track,
                results,
                stats_after,
            )
            print("[OK] project_track.md updated")

        # Disconnect
        classifier.disconnect()

        return 0

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Classification cancelled by user")
        classifier.disconnect()
        return 130

    except Exception as e:
        print(f"\n[ERROR] Classification failed: {e}")
        import traceback
        traceback.print_exc()

        try:
            classifier.disconnect()
        except:
            pass

        return 1


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="AI Job Scanner - Telegram Job Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate sources
  python -m aijobscanner validate-sources --dry-run

  # Ingest messages (dry run)
  python -m aijobscanner ingest --dry-run

  # Ingest from single source
  python -m aijobscanner ingest --only tg_vankar1 --limit-per-source 50

  # Ingest and update project track
  python -m aijobscanner ingest --update-project-track

Environment Variables:
  TG_API_ID          Telegram API ID (required) - get from my.telegram.org
  TG_API_HASH        Telegram API hash (required)
  TG_PHONE           Phone number for monitoring account (required)
  TG_2FA_PASSWORD    Two-factor password (if enabled on account)
  TG_SESSION_DIR     Session file directory (default: ./data/telegram_session)

For more information, see:
  - Validation: docs/runbooks/telegram_validation.md
  - Ingestion: docs/runbooks/telegram_ingestion.md
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate-sources command
    validate_parser = subparsers.add_parser(
        "validate-sources",
        help="Validate Telegram source access",
    )

    validate_parser.add_argument(
        "--sources",
        type=str,
        default="config/telegram_sources.yaml",
        help="Path to telegram_sources.yaml (default: config/telegram_sources.yaml)",
    )

    validate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without writing YAML back (default behavior)",
    )

    validate_parser.add_argument(
        "--write-back",
        action="store_true",
        help="Update YAML with validation results",
    )

    validate_parser.add_argument(
        "--only",
        type=str,
        metavar="SOURCE_ID",
        help="Validate only the specified source ID",
    )

    validate_parser.add_argument(
        "--report-dir",
        type=str,
        default="data/reports",
        help="Report output directory (default: data/reports)",
    )

    validate_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of messages to fetch for verification (default: 5)",
    )

    # ingest command
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest messages from Telegram sources",
    )

    ingest_parser.add_argument(
        "--sources",
        type=str,
        default="config/telegram_sources.yaml",
        help="Path to telegram_sources.yaml (default: config/telegram_sources.yaml)",
    )

    ingest_parser.add_argument(
        "--db",
        type=str,
        default="data/db/aijobscanner.sqlite3",
        help="Path to SQLite database (default: data/db/aijobscanner.sqlite3)",
    )

    ingest_parser.add_argument(
        "--limit-per-source",
        type=int,
        default=200,
        help="Maximum messages to fetch per source (default: 200)",
    )

    ingest_parser.add_argument(
        "--only",
        type=str,
        metavar="SOURCE_ID",
        help="Ingest only from the specified source ID",
    )

    ingest_parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore validation_status check (ingest from all enabled sources)",
    )

    ingest_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ingest without writing to database",
    )

    ingest_parser.add_argument(
        "--report-dir",
        type=str,
        default="data/reports",
        help="Report output directory (default: data/reports)",
    )

    ingest_parser.add_argument(
        "--update-project-track",
        type=str,
        nargs="?",
        const="project_track.md",
        help="Update project_track.md with ingestion summary (default path: project_track.md)",
    )

    # classify command
    classify_parser = subparsers.add_parser(
        "classify",
        help="Classify messages for AI/automation relevance",
    )

    classify_parser.add_argument(
        "--db",
        type=str,
        default="data/db/aijobscanner.sqlite3",
        help="Path to SQLite database (default: data/db/aijobscanner.sqlite3)",
    )

    classify_parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum messages to classify (default: 500)",
    )

    classify_parser.add_argument(
        "--only",
        type=str,
        metavar="SOURCE_ID",
        help="Classify only from the specified source ID",
    )

    classify_parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reprocess already-classified messages",
    )

    classify_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify without writing to database",
    )

    classify_parser.add_argument(
        "--export-dir",
        type=str,
        default="data/review",
        help="CSV export directory (default: data/review)",
    )

    classify_parser.add_argument(
        "--export-limit",
        type=int,
        default=100,
        help="Maximum candidates to export (default: 100)",
    )

    classify_parser.add_argument(
        "--update-project-track",
        type=str,
        nargs="?",
        const="project_track.md",
        help="Update project_track.md with classification summary (default path: project_track.md)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "validate-sources":
        # Run async command
        exit_code = asyncio.run(validate_sources_command(args))
        return exit_code
    elif args.command == "ingest":
        # Run async command
        exit_code = asyncio.run(ingest_sources_command(args))
        return exit_code
    elif args.command == "classify":
        # Run classify command (sync)
        exit_code = classify_command(args)
        return exit_code
    else:
        print(f"[ERROR] Unknown command: {args.command}")
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
