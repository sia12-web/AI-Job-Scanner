# Auto-Apply No-LLM System - Safety Guide

## Overview

The Auto-Apply system automatically sends job applications via email using **deterministic keyword matching** (NO LLM). It supports **TWO applicant profiles** (Tech + Biotech) with strict isolation to prevent cross-contamination.

**Core Philosophy**: Safety-first, deterministic, auditable.

---

## Table of Contents

1. [Safety-First Philosophy](#safety-first-philosophy)
2. [Profile Routing & Ambiguity Detection](#profile-routing--ambiguity-detection)
3. [APPLY_ENABLED Kill-Switch](#apply_enabled-kill-switch)
4. [SOURCE_LINK Transparency](#source_link-transparency)
5. [Global Deduplication](#global-deduplication)
6. [SMTP Configuration](#smtp-configuration)
7. [CV Folder Permissions](#cv-folder-permissions)
8. [Testing Workflow](#testing-workflow)
9. [Manual Approval Workflow](#manual-approval-workflow)
10. [Common Error Scenarios](#common-error-scenarios)

---

## Safety-First Philosophy

The auto-apply system is designed with **multiple safety layers** to prevent accidental or inappropriate sends:

### Layer 1: APPLY_ENABLED Kill-Switch
- **Default**: `APPLY_ENABLED=false` in `.env`
- **Check**: BEFORE opening SMTP connection
- **Result**: Refuses to send unless explicitly enabled

### Layer 2: CLI Confirmation Flags
- **Required**: `--send` AND `--yes-i-confirm`
- **Prevents**: Accidental sends from typos
- **Error**: "APPLY_ENABLED is false in .env"

### Layer 3: Profile Routing & Ambiguity Detection
- **Skip if**: BOTH profiles match (ambiguous_both_match)
- **Skip if**: NEITHER profile matches (no_match)
- **Skip if**: Scores too close (tie_close)
- **Prevents**: Sending wrong CV to wrong job type

### Layer 4: Email Extraction Safety
- **Skip if**: 0 emails found (no_email_found)
- **Skip if**: 2+ emails found (multiple_emails_ambiguous)
- **Requires**: Single, clear email address

### Layer 5: Global Deduplication
- **Dedupe key**: `tg_chat_id:tg_message_id:email`
- **Scope**: Across all profiles and all time
- **Prevents**: Sending same email for same job twice

### Layer 6: Rate Limiting
- **APPLY_SLEEP_SECONDS**: Delay between sends (default: 5)
- **APPLY_MAX_PER_RUN**: Max emails per run (default: 10)
- **Prevents**: Runaway sends and spamming

### Layer 7: CV Validation
- **Check**: CV file exists AND is PDF
- **Prevents**: Sending without proper attachment

---

## Profile Routing & Ambiguity Detection

### How Routing Works

1. **Score Job Post** against ALL profiles using keyword matching
2. **Apply Threshold**: Only profiles with score ≥ 0.7 are considered
3. **Check for Ambiguity**:
   - Both profiles above threshold → SKIP (ambiguous_both_match)
   - Scores too close (margin < 0.1) → SKIP (tie_close)
4. **Select Winner**: Clear winner above threshold → Route to profile

### Skip Reasons

| Skip Reason | When Triggered | Example |
|------------|----------------|---------|
| `no_match` | Neither profile scores ≥ 0.7 | Job for truck driver |
| `ambiguous_both_match` | BOTH profiles ≥ threshold | "Software for Bioinformatics" |
| `tie_close` | Top scores within 0.1 | Both profiles score 2.1 and 2.15 |
| `no_email_found` | 0 emails extracted | Job post with no contact email |
| `multiple_emails_ambiguous` | 2+ emails extracted | "jobs@company.com, hr@company.com" |
| `duplicate` | Dedupe key already exists | Sent to this email for this job before |

### Keyword Matching

**Scoring Algorithm**:
```
score = (positive_keyword_matches × 1.0) - (negative_keyword_matches × 1.5)
```

**Word Boundaries**: Uses regex `\bkeyword\b` to avoid false matches
- ✅ "software" matches "software engineer"
- ❌ "soft" matches "software" (prevented by word boundary)

**Example: Tech Profile**
```
Positive: software, developer, python, docker, kubernetes...
Negative: biology, lab, research, clinical...

Score: +3.0 (3 positive matches) - 0.0 (0 negative) = 3.0 → Routed
```

**Example: Ambiguous Post**
```
Text: "Bioinformatics Software Developer"

Tech profile: +1.0 (software) - 1.5 (bioinformatics) = -0.5
Biotech profile: +2.0 (bioinformatics, biology) - 1.5 (software) = +0.5

Both below threshold (0.7) → Skip (no_match)
```

---

## APPLY_ENABLED Kill-Switch

### Purpose

The **APPLY_ENABLED** environment variable is the **primary safety mechanism** to prevent accidental email sends.

### How It Works

1. **Default Value**: `APPLY_ENABLED=false` in `.env.example`
2. **Check Location**: BEFORE opening SMTP connection
3. **Check Logic**:
   ```python
   if not self.apply_enabled and not dry_run:
       raise SecurityError("APPLY_ENABLED is false. Cannot send emails.")
   ```

### Enabling Sending

To enable actual email sends:

1. **Edit `.env`** file:
   ```bash
   # Enable sending
   APPLY_ENABLED=true
   ```

2. **Use CLI flags**:
   ```bash
   python -m aijobscanner auto-apply --send --yes-i-confirm
   ```

3. **Confirm 5-second warning**:
   ```
   [WARN] *** SENDING MODE ENABLED ***
   [WARN] This will send REAL emails to employers
   [WARN] Press Ctrl+C to cancel within 5 seconds...
   ```

### Safety Check Sequence

```
1. CLI: --send flag present?
   └─ NO → Dry-run only (safe)
   └─ YES → Continue
2. CLI: --yes-i-confirm flag present?
   └─ NO → ERROR, exit 1
   └─ YES → Continue
3. ENV: APPLY_ENABLED=true?
   └─ NO → ERROR, exit 1
   └─ YES → Continue
4. SMTP: Open connection and send
```

### Disabling Sending

To disable sending after use:

```bash
# Edit .env
APPLY_ENABLED=false

# Future runs will refuse to send
```

---

## SOURCE_LINK Transparency

### Purpose

Every email sent **MUST include** a link to the original job post for transparency and traceability.

### Implementation

**Template Placeholder**: `{{SOURCE_LINK}}`

**Resolves To**: `permalink` field from Telegram message

**Example Email Body**:
```
Dear Hiring Manager,

I am writing to express my interest in the Senior Python Developer position.

[...]

Source: https://t.me/vankar1/123

Best regards,
Tech Applicant
```

### Verification

Check sent emails for SOURCE_LINK:
- ✅ Present: Transparent, auditable
- ❌ Missing: Configuration error (check permalink field)

---

## Global Deduplication

### Purpose

Prevent sending **multiple applications to the same email address for the same job posting**, across all profiles and all time.

### Dedupe Key Format

```
tg_chat_id:tg_message_id:email
```

**Example**:
```
1367311696:12345:jobs@company.com
```

### How It Works

1. **Before sending**, check dedupe_key against all outbox entries
2. **If duplicate found**: Create skipped entry with reason "duplicate"
3. **If not duplicate**: Send email, then add dedupe_key to cache

### Scope

- **Global**: Across all profiles (tech + biotech)
- **Timeless**: Checks all historical outbox files
- **Persistent**: Stored in JSONL files forever

### Example Scenarios

**Scenario 1: Same Job, Same Email**
```
First run: Send to jobs@company.com (success)
Second run: Skip (duplicate) - already sent to jobs@company.com for this job
```

**Scenario 2: Same Job, Different Emails**
```
First run: Send to jobs@company.com (success)
Second run: Send to hr@company.com (allowed) - different email
```

**Scenario 3: Different Jobs, Same Email**
```
First run: Send to jobs@company.com for Job A (success)
Second run: Send to jobs@company.com for Job B (allowed) - different job
```

### Checking Duplicate Status

```bash
# Check if an email was already sent
cat data/outbox/outbox_*.jsonl | jq -r 'select(.dedupe_key == "1367311696:12345:jobs@company.com")'

# Count duplicates
cat data/outbox/outbox_*.jsonl | jq '[.dedupe_key] | unique | length'
```

---

## SMTP Configuration

### Required Environment Variables

Add to `.env` file:

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
```

### Common SMTP Providers

#### Gmail

1. **Enable 2-Factor Authentication** on your Google Account
2. **Generate App Password**:
   - Go to: https://myaccount.google.com/apppasswords
   - Select: Mail
   - Generate: 16-character app password
3. **Configure**:
   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your_email@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop  # 16-char app password
   ```

#### Outlook (Office 365)

```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your_email@outlook.com
SMTP_PASSWORD=your_password
```

#### SendGrid (for testing)

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=SG.xxxxx.xxxxx.xxxxx
```

### STARTTLS Requirement

The system **requires STARTTLS** for secure SMTP connections:

```python
server.starttls()  # Raises exception if unavailable
```

**Verify your SMTP provider supports STARTTLS on port 587**.

### Testing SMTP Connection

To test SMTP credentials:

```python
import smtplib

# Test connection
with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.starttls()
    server.login("your_email@gmail.com", "your_app_password")
    print("SMTP connection successful!")
```

---

## CV Folder Permissions

### Unix/Linux Systems

Set restrictive permissions (owner-only access):

```bash
# Create directory
mkdir -p data/cv

# Set permissions (owner: rwx, group: ---, other: ---)
chmod 700 data/cv

# Verify
ls -ld data/cv
# Output: drwx------ 2 user group ... data/cv
```

### Windows Systems

Windows doesn't support Unix-style permissions. **Alternatives**:
- Use file system encryption (BitLocker, EFS)
- Set folder permissions in Windows Explorer
- Ensure sensitive files are in user profile only

### Validation

The system validates CVs before sending:

```python
# Checks performed:
1. CV file exists? → FileNotFoundError if not
2. CV is PDF? → ValueError if not (.doc, .txt, etc.)
```

**Errors**:
```
[SECURITY] CV validation failed: CV file not found: data/cv/tech_cv.pdf
[SECURITY] CV validation failed: CV must be PDF file, got: .docx
```

---

## Testing Workflow

### Step 1: Dry-Run (Recommended First Step)

Test routing without sending:

```bash
python -m aijobscanner auto-apply --dry-run --limit 10
```

**Expected Output**:
```
[INFO] Found 8 AI-relevant messages
[DRY-RUN] Would send: jobs@company.com
[DRY-RUN] Would send: hr@startup.io
...
```

**What It Does**:
- ✅ Routes jobs to profiles
- ✅ Extracts emails
- ✅ Creates outbox entries (status: "draft")
- ✅ Shows what would be sent
- ❌ Does NOT send emails
- ❌ Does NOT open SMTP connection

**Verify**:
```bash
# Check outbox entries
cat data/outbox/outbox_$(date +%Y%m%d).jsonl | jq '.'
```

### Step 2: Review Outbox

Review skipped entries and reasons:

```bash
# View skip reasons
cat data/outbox/outbox_*.jsonl | jq -r 'select(.skip_reason) | .skip_reason' | sort | uniq -c

# View specific entry
cat data/outbox/outbox_*.jsonl | jq 'select(.profile_id == "tech_profile")'
```

### Step 3: Test Kill-Switch

Verify kill-switch blocks sends:

```bash
# Ensure APPLY_ENABLED=false in .env
python -m aijobscanner auto-apply --send --yes-i-confirm --max-per-run 1

# Expected: ERROR
```

**Expected Output**:
```
[ERROR] APPLY_ENABLED is false in .env

To enable sending:
1. Edit .env file
2. Set APPLY_ENABLED=true
3. Re-run this command
```

### Step 4: Test with Test Email (Optional)

Send one test email to yourself:

1. **Add test email** to a test message in database
2. **Set APPLY_ENABLED=true** in `.env`
3. **Run**:
   ```bash
   python -m aijobscanner auto-apply --send --yes-i-confirm --max-per-run 1
   ```
4. **Verify** email received with correct CV attached

---

## Manual Approval Workflow

### Recommended Production Workflow

#### Phase 1: Initial Setup (One-Time)

1. **Configure SMTP**:
   ```bash
   # Edit .env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   ```

2. **Configure Profiles**:
   - Edit `config/applicants.yaml`
   - Set `display_name` and `applicant_name`
   - Update `cv_path` to point to your CV files
   - Review keywords_positive and keywords_negative
   - Adjust `threshold` if needed (default: 0.7)

3. **Add CVs**:
   ```bash
   cp /path/to/tech_cv.pdf data/cv/tech_cv.pdf
   cp /path/to/biotech_cv.pdf data/cv/biotech_cv.pdf
   ```

4. **Test Routing**:
   ```bash
   python -m aijobscanner auto-apply --dry-run --limit 20
   ```

#### Phase 2: Review & Tune (Daily)

1. **Run Dry-Run**:
   ```bash
   python -m aijobscanner auto-apply --dry-run
   ```

2. **Review Outbox**:
   ```bash
   # Check skip reasons
   cat data/outbox/outbox_*.jsonl | jq -r '.skip_reason' | sort | uniq -c
   ```

3. **Adjust Keywords** if needed:
   - Too many `ambiguous_both_match`? → Add more negative keywords
   - Too many `no_match`? → Lower threshold or add more positive keywords
   - Too many `no_email_found`? → Consider adding `--pick-email` logic

#### Phase 3: Enable Sending (When Ready)

1. **Enable Kill-Switch**:
   ```bash
   # Edit .env
   APPLY_ENABLED=true
   ```

2. **Start Small**:
   ```bash
   # Send max 1 email first
   python -m aijobscanner auto-apply --send --yes-i-confirm --max-per-run 1
   ```

3. **Verify Success**:
   - Check email received
   - Check correct CV attached
   - Check SOURCE_LINK in email body

4. **Scale Up Gradually**:
   ```bash
   # Send max 3 emails
   python -m aijobscanner auto-apply --send --yes-i-confirm --max-per-run 3

   # Send max 10 emails (default)
   python -m aijobscanner auto-apply --send --yes-i-confirm
   ```

#### Phase 4: Monitor & Maintain

1. **Review Outbox Regularly**:
   ```bash
   # Check success rate
   cat data/outbox/outbox_*.jsonl | jq '[.status] | group_by(.) | map({status: .[0], count: length})'
   ```

2. **Check Failed Sends**:
   ```bash
   cat data/outbox/outbox_*.jsonl | jq 'select(.status == "failed")'
   ```

3. **Disable When Not Needed**:
   ```bash
   # Edit .env
   APPLY_ENABLED=false
   ```

---

## Common Error Scenarios

### Error: "Applicant config not found"

**Cause**: `config/applicants.yaml` doesn't exist

**Solution**:
```bash
# Verify file exists
ls config/applicants.yaml

# Check path in command
python -m aijobscanner auto-apply --applicants config/applicants.yaml
```

### Error: "CV file not found: data/cv/tech_cv.pdf"

**Cause**: CV file doesn't exist

**Solution**:
```bash
# Check CV directory
ls -la data/cv/

# Add CV file
cp /path/to/tech_cv.pdf data/cv/tech_cv.pdf

# Update config if using custom path
# Edit config/applicants.yaml: cv_path: "/custom/path.pdf"
```

### Error: "APPLY_ENABLED is false in .env"

**Cause**: Kill-switch is disabled (intentional safety feature)

**Solution**:
```bash
# Edit .env file
nano .env  # or use your editor

# Set:
APPLY_ENABLED=true

# Save and re-run
```

### Error: "No email found"

**Cause**: No email address in message text

**Solution**:
- This is expected for some job posts
- System skips with reason `no_email_found`
- Review job post to see if email is hidden in image or different format

### Error: "pick_index X out of range"

**Cause**: Invalid email index with `--pick-email` flag

**Solution**:
```bash
# First, see available emails
# (Future enhancement: show emails in output)

# Use valid index (0-based)
python -m aijobscanner auto-apply --pick-email 0
```

### Many "ambiguous_both_match" Skips

**Cause**: Job posts match both profiles (common in interdisciplinary roles)

**Solutions**:
1. **Add more negative keywords** to profiles
2. **Increase threshold** (e.g., from 0.7 to 1.0)
3. **Accept ambiguity** - better to skip than send wrong CV

### Many "no_match" Skips

**Cause**: Job posts don't match either profile strongly enough

**Solutions**:
1. **Lower threshold** (e.g., from 0.7 to 0.5)
2. **Add more positive keywords** to profiles
3. **Review job posts** - are they relevant to either profile?

---

## Summary

The auto-apply system provides:

✅ **Safety**: Multiple layers prevent accidental sends
✅ **Transparency**: SOURCE_LINK in every email
✅ **Traceability**: Complete audit trail in outbox
✅ **Flexibility**: Tunable keywords and thresholds
✅ **Reliability**: No LLM, fully deterministic
✅ **Privacy**: No CV contents in DB, gitignored

**Remember**: Always start with `--dry-run` to verify routing before enabling sending!
