"""
SMTP email sending with comprehensive safety gates.

Implements EmailSender class with multiple safety layers to prevent
accidental sends and ensure proper CV attachment.
"""

import os
import smtplib
import time
import stat
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

from .outbox import OutboxManager
from .templates import load_applicant_profiles, extract_emails, extract_job_title, select_template, render_template
from .routing import route_message, select_email


class SecurityError(Exception):
    """Raised when a safety gate fails."""
    pass


class EmailSender:
    """
    SMTP email sender with comprehensive safety gates.

    Safety layers:
    1. APPLY_ENABLED environment variable check (before SMTP)
    2. CV file validation (exists + PDF check)
    3. Deduplication check (global across profiles)
    4. Rate limiting (max per run + sleep between sends)
    """

    def __init__(
        self,
        outbox_manager: OutboxManager,
        apply_enabled: Optional[bool] = None,
        sleep_seconds: int = 5,
        max_per_run: int = 10,
    ):
        """
        Initialize email sender.

        Args:
            outbox_manager: OutboxManager instance
            apply_enabled: Override APPLY_ENABLED (for testing)
            sleep_seconds: Delay between sends (default: 5)
            max_per_run: Maximum emails to send per run (default: 10)
        """
        self.outbox = outbox_manager

        # Load from env if not provided
        if apply_enabled is None:
            apply_enabled = os.getenv("APPLY_ENABLED", "false").lower() == "true"

        self.apply_enabled = apply_enabled
        self.sleep_seconds = sleep_seconds
        self.max_per_run = max_per_run
        self.sent_count = 0

        # SMTP config
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")

    def validate_cv(self, cv_path: str) -> bool:
        """
        Validate CV file exists and is a PDF.

        Args:
            cv_path: Path to CV file

        Returns:
            True if valid

        Raises:
            FileNotFoundError: If CV file doesn't exist
            ValueError: If CV is not a PDF
        """
        cv_file = Path(cv_path)

        if not cv_file.exists():
            raise FileNotFoundError(f"CV file not found: {cv_path}")

        # Check file extension
        if cv_file.suffix.lower() != '.pdf':
            raise ValueError(
                f"CV must be PDF file, got: {cv_file.suffix}"
            )

        # Note: File permissions check is Unix-only and best-effort
        # Windows doesn't support Unix-style permissions
        return True

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cv_path: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Send email via SMTP with safety gates.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            cv_path: Path to CV PDF file
            dry_run: If True, skip actual send

        Returns:
            Dict with success, error, smtp_response, dry_run

        Raises:
            SecurityError: If any safety gate fails
        """
        result = {
            "success": False,
            "error": None,
            "smtp_response": None,
            "dry_run": dry_run,
        }

        # SAFETY GATE 1: Apply enabled check
        if not self.apply_enabled and not dry_run:
            raise SecurityError(
                "APPLY_ENABLED is false. Cannot send emails. "
                "Set APPLY_ENABLED=true in .env to enable."
            )

        # SAFETY GATE 2: CV validation
        try:
            self.validate_cv(cv_path)
        except (FileNotFoundError, ValueError) as e:
            raise SecurityError(f"CV validation failed: {e}")

        # SAFETY GATE 3: Rate limiting check
        if self.sent_count >= self.max_per_run and not dry_run:
            raise SecurityError(
                f"Max per run limit reached ({self.max_per_run}). "
                "Run again later or increase APPLY_MAX_PER_RUN."
            )

        if dry_run:
            print(f"[DRY-RUN] Would send email to: {to_email}")
            print(f"[DRY-RUN] Subject: {subject}")
            print(f"[DRY-RUN] CV: {cv_path}")
            result["success"] = True
            return result

        # Build email message
        msg = MIMEMultipart()
        msg['From'] = self.smtp_username
        msg['To'] = to_email
        msg['Subject'] = subject

        # Attach body
        msg.attach(MIMEText(body, 'plain'))

        # Attach CV
        with open(cv_path, 'rb') as f:
            cv_attachment = MIMEApplication(f.read(), _subtype='pdf')
            cv_attachment.add_header(
                'Content-Disposition',
                'attachment',
                filename=Path(cv_path).name
            )
            msg.attach(cv_attachment)

        # Send via SMTP
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                # STARTTLS
                server.starttls()

                # Login
                server.login(self.smtp_username, self.smtp_password)

                # Send
                response = server.send_message(msg)
                result["smtp_response"] = str(response)
                result["success"] = True

                print(f"[SENT] Email to {to_email} (response: {response})")

        except Exception as e:
            result["error"] = str(e)
            print(f"[ERROR] Failed to send email: {e}")
            raise

        # Update counters
        self.sent_count += 1

        # Rate limiting delay (unless this was the last one)
        if self.sent_count < self.max_per_run:
            print(f"[INFO] Sleeping {self.sleep_seconds}s before next send...")
            time.sleep(self.sleep_seconds)

        return result


def process_pending_sends(
    db_conn,
    applicants_config: str,
    outbox_dir: str,
    send_mode: bool = False,
    dry_run: bool = False,
    max_per_run: int = 10,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process pending sends: route jobs, create outbox entries, send emails.

    This is the main orchestration function for the auto-apply pipeline.

    Args:
        db_conn: SQLite database connection
        applicants_config: Path to config/applicants.yaml
        outbox_dir: Path to outbox directory
        send_mode: If False, only create outbox entries
        dry_run: If True, skip actual SMTP sends
        max_per_run: Maximum emails to send this run
        limit: Maximum messages to process

    Returns:
        Processing statistics dict
    """
    # Import fetch function here to avoid circular dependency
    from storage import fetch_ai_relevant_messages

    # Initialize components
    outbox = OutboxManager(outbox_dir)
    profiles = load_applicant_profiles(applicants_config)
    sender = EmailSender(
        outbox_manager=outbox,
        max_per_run=max_per_run,
    )

    stats = {
        "processed": 0,
        "sent": 0,
        "skipped": 0,
        "errors": 0,
        "skip_reasons": {},
    }

    # Fetch AI-relevant messages
    messages = fetch_ai_relevant_messages(db_conn, limit=limit)

    print(f"[INFO] Found {len(messages)} AI-relevant messages")

    for msg in messages:
        try:
            # Extract emails
            emails = extract_emails(msg["text"])
            job_title = extract_job_title(msg["text"])

            # Route to profile
            routing_result = route_message(msg["text"], profiles)

            # Skip if routing failed
            if routing_result["skip_reason"]:
                skip_reason = routing_result["skip_reason"]
                stats["skipped"] += 1
                stats["skip_reasons"][skip_reason] = \
                    stats["skip_reasons"].get(skip_reason, 0) + 1

                # Create skipped outbox entry
                outbox.create_entry(
                    profile_id=None,
                    source_id=msg["source_id"],
                    tg_chat_id=msg["tg_chat_id"],
                    tg_message_id=msg["tg_message_id"],
                    job_title=job_title,
                    extracted_emails=emails,
                    selected_email=None,
                    subject=None,
                    body=None,
                    cv_path=None,
                    routing_scores=routing_result["scores"],
                    routing_metadata=routing_result["routing_metadata"],
                    skip_reason=skip_reason,
                )
                continue

            # Profile selected
            profile_id = routing_result["profile_id"]
            profile = profiles[profile_id]

            # Select email
            if not emails:
                stats["skipped"] += 1
                stats["skip_reasons"]["no_email_found"] = \
                    stats["skip_reasons"].get("no_email_found", 0) + 1

                outbox.create_entry(
                    profile_id=profile_id,
                    source_id=msg["source_id"],
                    tg_chat_id=msg["tg_chat_id"],
                    tg_message_id=msg["tg_message_id"],
                    job_title=job_title,
                    extracted_emails=[],
                    selected_email=None,
                    subject=None,
                    body=None,
                    cv_path=profile["cv_path"],
                    routing_scores=routing_result["scores"],
                    routing_metadata=routing_result["routing_metadata"],
                    skip_reason="no_email_found",
                )
                continue

            if len(emails) > 1:
                stats["skipped"] += 1
                stats["skip_reasons"]["multiple_emails_ambiguous"] = \
                    stats["skip_reasons"].get("multiple_emails_ambiguous", 0) + 1

                outbox.create_entry(
                    profile_id=profile_id,
                    source_id=msg["source_id"],
                    tg_chat_id=msg["tg_chat_id"],
                    tg_message_id=msg["tg_message_id"],
                    job_title=job_title,
                    extracted_emails=emails,
                    selected_email=None,
                    subject=None,
                    body=None,
                    cv_path=profile["cv_path"],
                    routing_scores=routing_result["scores"],
                    routing_metadata=routing_result["routing_metadata"],
                    skip_reason="multiple_emails_ambiguous",
                )
                continue

            # Single email found
            selected_email = emails[0]

            # Check dedupe
            dedupe_key = f"{msg['tg_chat_id']}:{msg['tg_message_id']}:{selected_email}"
            if outbox.is_duplicate(dedupe_key):
                stats["skipped"] += 1
                stats["skip_reasons"]["duplicate"] = \
                    stats["skip_reasons"].get("duplicate", 0) + 1

                outbox.create_entry(
                    profile_id=profile_id,
                    source_id=msg["source_id"],
                    tg_chat_id=msg["tg_chat_id"],
                    tg_message_id=msg["tg_message_id"],
                    job_title=job_title,
                    extracted_emails=emails,
                    selected_email=selected_email,
                    subject=None,
                    body=None,
                    cv_path=profile["cv_path"],
                    routing_scores=routing_result["scores"],
                    routing_metadata=routing_result["routing_metadata"],
                    skip_reason="duplicate",
                )
                continue

            # Generate email from template
            template = select_template(profile)
            source_link = msg.get("permalink", "")
            email = render_template(
                template,
                job_title=job_title,
                source_link=source_link,
                applicant_name=profile["applicant_name"],
            )

            # Create outbox entry (draft status)
            outbox_entry = outbox.create_entry(
                profile_id=profile_id,
                source_id=msg["source_id"],
                tg_chat_id=msg["tg_chat_id"],
                tg_message_id=msg["tg_message_id"],
                job_title=job_title,
                extracted_emails=emails,
                selected_email=selected_email,
                subject=email["subject"],
                body=email["body"],
                cv_path=profile["cv_path"],
                routing_scores=routing_result["scores"],
                routing_metadata=routing_result["routing_metadata"],
                skip_reason=None,
            )

            stats["processed"] += 1

            # Send if enabled
            if send_mode and not dry_run:
                try:
                    send_result = sender.send_email(
                        to_email=selected_email,
                        subject=email["subject"],
                        body=email["body"],
                        cv_path=profile["cv_path"],
                        dry_run=dry_run,
                    )

                    if send_result["success"]:
                        stats["sent"] += 1
                        outbox.update_entry(
                            outbox_id=outbox_entry["outbox_id"],
                            status="sent",
                            smtp_response=send_result["smtp_response"],
                        )
                    else:
                        stats["errors"] += 1
                        outbox.update_entry(
                            outbox_id=outbox_entry["outbox_id"],
                            status="failed",
                            last_error=send_result["error"],
                        )

                except SecurityError as e:
                    print(f"[SECURITY] Send blocked: {e}")
                    stats["skipped"] += 1
                    stats["skip_reasons"]["security_gate"] = \
                        stats["skip_reasons"].get("security_gate", 0) + 1

                    outbox.update_entry(
                        outbox_id=outbox_entry["outbox_id"],
                        status="skipped",
                        last_error=str(e),
                    )

            elif send_mode and dry_run:
                print(f"[DRY-RUN] Would send: {selected_email}")
                stats["sent"] += 1  # Count as would-be sent

        except Exception as e:
            print(f"[ERROR] Failed to process message {msg['tg_message_id']}: {e}")
            stats["errors"] += 1

    return stats
