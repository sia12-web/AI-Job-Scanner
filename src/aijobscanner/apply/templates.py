"""
Email template management for auto-apply system.

Handles loading applicant profiles, rendering email templates with
job-specific placeholders, and extracting job titles from messages.
"""

import re
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path


def load_applicant_profiles(config_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load applicant profiles from YAML configuration.

    Args:
        config_path: Path to config/applicants.yaml

    Returns:
        Dict mapping profile_id → profile config

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Applicant config not found: {config_path}")

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config['applicants']


def render_template(
    template: Dict[str, str],
    job_title: str,
    source_link: str,
    applicant_name: str
) -> Dict[str, str]:
    """
    Render email template with job-specific placeholders.

    Replaces:
    - {{JOB_TITLE}} → job_title
    - {{SOURCE_LINK}} → source_link
    - {{APPLICANT_NAME}} → applicant_name

    Args:
        template: Template dict with subject and body
        job_title: Extracted job title
        source_link: Permalink to original job post
        applicant_name: Applicant's name from profile

    Returns:
        Dict with rendered subject and body
    """
    subject = template["subject"]
    body = template["body"]

    # Define placeholders
    placeholders = {
        "{{JOB_TITLE}}": job_title,
        "{{SOURCE_LINK}}": source_link,
        "{{APPLICANT_NAME}}": applicant_name,
    }

    # Replace placeholders in subject
    for placeholder, value in placeholders.items():
        subject = subject.replace(placeholder, value)

    # Replace placeholders in body
    for placeholder, value in placeholders.items():
        body = body.replace(placeholder, value)

    return {
        "subject": subject,
        "body": body
    }


def extract_job_title(text: str) -> str:
    """
    Extract job title from message text.

    Strategy:
    1. Look for patterns: "Title:", "Position:", "Role:", "Job:"
    2. Use first line if reasonable length (<100 chars)
    3. Fallback: "Position"

    Args:
        text: Message text

    Returns:
        Extracted job title
    """
    # Remove leading/trailing whitespace
    text = text.strip()

    # Split into lines
    lines = text.split('\n')

    # Look for title patterns in first few lines
    title_patterns = [
        r'(?:title|position|role|job):\s*(.+?)(?:\n|$|\r)',
        r'job\s+(?:title|position|role):\s*(.+?)(?:\n|$|\r)',
    ]

    # Check first 5 lines for title patterns
    for line in lines[:5]:
        for pattern in title_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Clean up common artifacts
                title = re.sub(r'^[\-\*#]+\s*', '', title)  # Remove leading bullets
                title = re.sub(r'\s*[\-\*#]+$', '', title)  # Remove trailing bullets
                if len(title) > 5 and len(title) < 100:
                    return title[:80]  # Truncate to 80 chars max

    # Fallback 1: First line if reasonable
    if lines and len(lines[0].strip()) < 100:
        first_line = lines[0].strip()
        # Remove common prefixes
        first_line = re.sub(r'^[\-\*#]+\s*', '', first_line)
        if len(first_line) > 5:
            return first_line[:80]

    # Fallback 2: Generic placeholder
    return "Position"


def select_template(
    profile: Dict[str, Any],
    template_index: Optional[int] = None
) -> Dict[str, str]:
    """
    Select an email template from profile.

    Args:
        profile: Profile dict with email_templates list
        template_index: Template index (default: first template)

    Returns:
        Selected template dict

    Raises:
        ValueError: If template_index is out of range
    """
    templates = profile.get("email_templates", [])

    if not templates:
        raise ValueError(f"No email templates found for profile")

    if template_index is None:
        # Default: use first template
        return templates[0]

    if template_index < 0 or template_index >= len(templates):
        raise ValueError(
            f"template_index {template_index} out of range [0, {len(templates) - 1}]"
        )

    return templates[template_index]
