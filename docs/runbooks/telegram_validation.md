# Telegram Validation Runbook

**Version**: 1.0
**Last Updated**: 2026-01-28
**Component**: AI Job Scanner - Telegram Source Validation

---

## What This Validator Does

The Telegram source validator checks if your monitoring account can access the registered Telegram sources (groups and channels). It:

1. **Connects to Telegram** using an MTProto user session (Telethon)
2. **Validates access** to each enabled source in `config/telegram_sources.yaml`
3. **Joins groups** via invite links (using `ImportChatInviteRequest`)
4. **Subscribes to channels** via public handles (using `JoinChannelRequest`)
5. **Verifies readability** by fetching the last N messages from each source
6. **Updates validation status** in the configuration file (with `--write-back`)
7. **Generates JSON reports** for auditing and troubleshooting

**Key Features**:
- Unified pipeline for both groups and channels
- Dry-run mode for safe testing
- Rate limiting awareness (handles `FloodWaitError`)
- 2FA password support
- Detailed error reporting

---

## How Login Works

### First Run (Authentication)

When you run the validator for the first time, it will:

1. **Request SMS code**:
   - The validator asks Telegram to send an SMS code to your phone number
   - You enter the code when prompted
   - The code is only valid for a short time (usually a few minutes)

2. **Request 2FA password** (if enabled):
   - If your Telegram account has two-factor authentication enabled
   - The validator will request your 2FA password
   - This must be set in `TG_2FA_PASSWORD` environment variable

3. **Create session file**:
   - After successful authentication, a session file is created
   - Location: `data/telegram_session/{phone_number}.session`
   - This file contains your authentication credentials
   - **TREAT THIS FILE AS A PASSWORD - NEVER SHARE OR COMMIT IT**

4. **Session persistence**:
   - The session file is automatically reused on subsequent runs
   - No need to re-enter SMS code or 2FA password
   - Session remains valid until explicitly revoked or deleted

### Subsequent Runs

After the first successful authentication:

1. The validator loads the existing session file
2. Connects to Telegram without requiring SMS code or 2FA
3. Validates sources immediately

**Session location**: `data/telegram_session/` (gitignored for security)

**Troubleshooting authentication issues**:
- If you get authentication errors, delete the session file and re-authenticate
- Session file format: `{phone_number}.session` (e.g., `1234567890.session`)
- To reset: `rm data/telegram_session/*.session`

---

## Validation Status Values

The validator updates the `validation_status` field for each source:

| Status | Meaning | When Set |
|--------|---------|----------|
| `unverified` | Not yet checked | Initial state before validation |
| `joined` | Successfully joined/subscribed and can read messages | Validation successful |
| `join_failed` | Could not join or subscribe | Invalid/expired invite, channel not found, etc. |
| `blocked` | Joined but cannot read messages | Chat forbidden, privacy restrictions |
| `not_applicable` | Source doesn't require validation | Reserved for future use |

**Status transition**:
```
unverified → [validation] → joined / join_failed / blocked
```

**Additional fields updated**:
- `last_validated_at`: ISO8601 timestamp of last validation attempt
- `last_error`: Error message if validation failed (null if successful)
- `resolved_entity_id`: Telegram entity ID (channel/group ID)
- `resolved_entity_type`: Entity type ("channel" or "group")

---

## Common Errors and Mitigations

| Error | Cause | Mitigation |
|-------|-------|------------|
| `ApiKeyInvalidError` | Wrong API_ID or API_HASH | Check `.env` file for correct credentials from https://my.telegram.org/apps |
| `PhoneCodeInvalidError` | Wrong SMS code entered | Re-run validation and enter correct code |
| `SessionPasswordNeededError` | 2FA enabled but TG_2FA_PASSWORD not set | Set `TG_2FA_PASSWORD` in `.env` file |
| `InviteHashInvalidError` | Invalid invite link (group) | Check `invite_link` in `config/telegram_sources.yaml` |
| `InviteHashExpiredError` | Invite link has expired | Get new invite link from source owner |
| `UserAlreadyParticipantError` | Already joined group | Not an error - validator continues normally |
| `ChannelPrivateError` | Channel is private or invite-only | Check if channel is public or requires invite |
| `UsernameNotOccupiedError` | Public handle not found | Check `public_handle` in config YAML |
| `FloodWaitError` | Rate limited by Telegram | Wait N seconds before retrying (validator shows wait time) |
| `ChannelsTooMuchError` | Too many channels joined | Leave some channels or increase account limits |
| `ChatForbiddenError` | Access blocked by source | Account may be blocked or banned from source |

### Error Recovery Workflow

1. **Read the error message** carefully
2. **Check the mitigation** in the table above
3. **Fix the issue** (e.g., update .env, fix invite link)
4. **Re-run validation** with `--dry-run` first
5. **Check the report** in `data/reports/` for detailed results
6. **Use `--write-back`** to update YAML if validation succeeds

---

## Safety Guidelines

### Session File Security

⚠️ **CRITICAL**: Session files contain authentication credentials and must be protected.

**DO**:
- Keep session files in `data/telegram_session/` (gitignored)
- Ensure `.gitignore` blocks `*.session` files
- Treat session files as sensitively as passwords
- Delete session files before decommissioning the account

**DO NOT**:
- Commit session files to version control
- Share session files with others
- Store session files in cloud storage
- Leave session files on shared computers

### Credential Management

**DO**:
- Store API credentials in `.env` file
- Keep `.env` file in `.gitignore`
- Use strong, unique passwords for 2FA
- Rotate credentials periodically
- Use different credentials for dev/staging/prod

**DO NOT**:
- Hardcode credentials in source code
- Share `.env` files
- Use production credentials for development
- Reuse passwords from other services

### Rate Limiting

**DO**:
- Respect Telegram's rate limits
- Use `--only` flag to validate one source at a time
- Add delays between validation runs if needed
- Monitor for `FloodWaitError` messages

**DO NOT**:
- Run validation continuously in a loop
- Validate all sources simultaneously
- Ignore rate limit warnings
- Attempt to bypass rate limits

### Authorization

**DO**:
- Only validate sources where your account is a legitimate member
- Join groups only with valid invite links
- Subscribe only to public channels
- Respect source rules and guidelines
- Leave sources if requested by owner

**DO NOT**:
- Attempt to access private sources without authorization
- Bypass access restrictions
- Spam or harass source owners
- Violate Telegram's Terms of Service

---

## Example Workflows

### 1. First-Time Setup

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate (Windows)
.venv\Scripts\activate
# OR (macOS/Linux)
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials:
# - TG_API_ID (from https://my.telegram.org/apps)
# - TG_API_HASH (from https://my.telegram.org/apps)
# - TG_PHONE (your phone number with + prefix)
# - TG_2FA_PASSWORD (if 2FA is enabled on your account)

# 5. Run validation (dry-run, safe mode)
python -m aijobscanner validate-sources --dry-run

# 6. When prompted, enter SMS code sent to your phone
# 7. If 2FA enabled, the validator will use TG_2FA_PASSWORD from .env
# 8. Session will be saved for future runs
```

### 2. Validate Specific Source

```bash
# Validate only tg_vankar1 channel
python -m aijobscanner validate-sources --only tg_vankar1 --dry-run
```

### 3. Validate and Update Configuration

```bash
# Validate all sources and update YAML with results
python -m aijobscanner validate-sources --write-back

# Check updated validation status
cat config/telegram_sources.yaml
```

### 4. Validate with Custom Message Limit

```bash
# Fetch 10 messages to verify readability (default is 5)
python -m aijobscanner validate-sources --limit 10 --dry-run
```

### 5. Check Validation Report

```bash
# Run validation
python -m aijobscanner validate-sources --write-back

# Find latest report
ls -lt data/reports/

# View report
cat data/reports/source_validation_YYYYMMDD_HHMMSS.json
```

### 6. Reset and Re-authenticate

```bash
# If authentication issues occur, reset session
rm data/telegram_session/*.session

# Re-run validation to create new session
python -m aijobscanner validate-sources --dry-run
# Enter SMS code and 2FA password again
```

### 7. Troubleshooting Failed Validation

```bash
# Run validation to see errors
python -m aijobscanner validate-sources --dry-run

# Check the report for detailed error messages
cat data/reports/source_validation_*.json | grep -A 10 "last_error"

# Fix the issue (e.g., update invite link in config)
# Then re-run with --write-back to update status
python -m aijobscanner validate-sources --write-back
```

---

## CLI Reference

### Command Syntax

```bash
python -m aijobscanner validate-sources [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--sources PATH` | Path to telegram_sources.yaml | `config/telegram_sources.yaml` |
| `--dry-run` | Validate without writing YAML | Enabled by default |
| `--write-back` | Update YAML with validation results | Disabled |
| `--only SOURCE_ID` | Validate only specified source | Validate all |
| `--report-dir PATH` | Report output directory | `data/reports` |
| `--limit N` | Number of messages to fetch | 5 |
| `--help` | Show help message | - |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TG_API_ID` | Yes | Telegram API ID from https://my.telegram.org/apps |
| `TG_API_HASH` | Yes | Telegram API hash from https://my.telegram.org/apps |
| `TG_PHONE` | Yes | Phone number with + prefix (e.g., +1234567890) |
| `TG_2FA_PASSWORD` | No* | 2FA password if enabled on account |
| `TG_SESSION_DIR` | No | Session file directory (default: ./data/telegram_session) |

*Required if 2FA is enabled on the account

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - All validations completed |
| 1 | Error - Configuration, authentication, or validation failed |
| 130 | Interrupted by user (Ctrl+C) |

---

## Validation Report Format

Reports are saved as JSON: `data/reports/source_validation_YYYYMMDD_HHMMSS.json`

**Structure**:
```json
{
  "timestamp": "2026-01-28T12:34:56.789Z",
  "summary": {
    "total_sources": 5,
    "joined": 4,
    "failed": 1,
    "blocked": 0
  },
  "results": [
    {
      "source_id": "tg_vankar1",
      "display_name": "Vankar Jobs",
      "source_type": "channel",
      "validation_status": "joined",
      "last_validated_at": "2026-01-28T12:34:56.789Z",
      "last_error": null,
      "resolved_entity_id": 1234567890,
      "resolved_entity_type": "channel",
      "messages_readable": true,
      "message_count": 5
    },
    // ... more results
  ]
}
```

**Using the report**:
- Check `summary` for overall validation health
- Review individual `results` for per-source details
- Use `last_error` field to troubleshoot failures
- `resolved_entity_id` is useful for debugging

---

## Best Practices

### Before Validation

1. **Review sources** in `config/telegram_sources.yaml`
2. **Check credentials** in `.env` file
3. **Ensure internet connectivity**
4. **Verify phone access** (for SMS code on first run)

### During Validation

1. **Start with `--dry-run`** to test without modifying YAML
2. **Monitor console output** for progress and errors
3. **Wait for rate limits** if `FloodWaitError` occurs
4. **Keep SMS code handy** on first run

### After Validation

1. **Review the report** in `data/reports/`
2. **Check validation status** in config YAML
3. **Address failed sources** (update invite links, etc.)
4. **Use `--write-back`** to persist successful results

### Regular Maintenance

1. **Re-validate periodically** (weekly recommended)
2. **Update expired invite links**
3. **Leave unused sources** (clean up membership)
4. **Rotate session files** (delete and re-authenticate monthly)

---

## Related Documentation

- **Project Track**: `../../project_track.md` - Overall project progress
- **Access Strategy**: `../../docs/telegram_access.md` - Two-lane architecture
- **Security Rules**: `../../security/telegram_session_rules.md` - Session security
- **ADR-001**: `../../ADR/001-telegram-ingestion-choice.md` - Architecture decision

---

## Troubleshooting Guide

### Problem: "Configuration file not found"

**Cause**: `config/telegram_sources.yaml` doesn't exist

**Solution**:
```bash
# Check if file exists
ls config/telegram_sources.yaml

# If missing, create it from Phase 0 Step 1 deliverables
# See project_track.md for Step 1 details
```

### Problem: "Missing required environment variables"

**Cause**: `.env` file not created or missing variables

**Solution**:
```bash
# Create .env from template
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor

# Ensure these are set:
# TG_API_ID=12345678
# TG_API_HASH=abcdef1234567890abcdef1234567890
# TG_PHONE=+1234567890
```

### Problem: "Invalid invite hash"

**Cause**: Group invite link is invalid or expired

**Solution**:
```bash
# Check the invite link in config
grep "invite_link" config/telegram_sources.yaml

# If expired, get new link from group admin
# Update the invite_link field in the YAML
```

### Problem: "Username not found"

**Cause**: Channel public handle is incorrect

**Solution**:
```bash
# Verify channel exists on Telegram
# Open https://t.me/HANDLE in browser (replace HANDLE)

# Update public_handle in config YAML
```

### Problem: "Rate limited. Wait N seconds"

**Cause**: Too many requests to Telegram API

**Solution**:
```bash
# Wait the specified number of seconds
# Then retry validation

# Or validate sources one at a time:
python -m aijobscanner validate-sources --only tg_vankar1
# Wait a few minutes
python -m aijobscanner validate-sources --only tg_karyabi_canada
```

### Problem: "Channel forbidden" or "Chat forbidden"

**Cause**: Account blocked from source

**Solution**:
- Check if you're manually blocked from the channel/group
- Try accessing the source manually in Telegram app
- If blocked, contact source owner or use alternative account

---

**End of Telegram Validation Runbook**

For additional help, see `project_track.md` or create an issue in the project repository.
