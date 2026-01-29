"""
Auto-Apply module for AI Job Scanner.

Handles profile routing, email template management, outbox storage,
and SMTP sending with comprehensive safety gates.
"""

from .routing import score_profile, route_message, extract_emails, select_email
from .templates import load_applicant_profiles, render_template, extract_job_title, select_template
from .outbox import OutboxManager
from .send import EmailSender, SecurityError, process_pending_sends

__all__ = [
    # Routing
    "score_profile",
    "route_message",
    "extract_emails",
    "select_email",
    # Templates
    "load_applicant_profiles",
    "render_template",
    "extract_job_title",
    "select_template",
    # Outbox
    "OutboxManager",
    # Send
    "EmailSender",
    "SecurityError",
    "process_pending_sends",
]
