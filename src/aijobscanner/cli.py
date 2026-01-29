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
)


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


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="AI Job Scanner - Telegram Source Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (no YAML modification)
  python -m aijobscanner validate-sources --dry-run

  # Validate single source
  python -m aijobscanner validate-sources --only tg_vankar1 --dry-run

  # Validate and update configuration
  python -m aijobscanner validate-sources --write-back

  # Validate with custom message limit
  python -m aijobscanner validate-sources --limit 10

Environment Variables:
  TG_API_ID          Telegram API ID (required) - get from my.telegram.org
  TG_API_HASH        Telegram API hash (required)
  TG_PHONE           Phone number for monitoring account (required)
  TG_2FA_PASSWORD    Two-factor password (if enabled on account)
  TG_SESSION_DIR     Session file directory (default: ./data/telegram_session)

For more information, see: docs/runbooks/telegram_validation.md
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "validate-sources":
        # Run async command
        exit_code = asyncio.run(validate_sources_command(args))
        return exit_code
    else:
        print(f"[ERROR] Unknown command: {args.command}")
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
