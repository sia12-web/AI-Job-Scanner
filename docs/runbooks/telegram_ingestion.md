# Telegram Message Ingestion Runbook

**Purpose**: Guide for ingesting messages from Telegram sources into the AI Job Scanner database.

**Prerequisites**:
- Phase 0 Step 2 completed (sources validated)
- Active Telegram session file exists
- SQLite database initialized
- Environment variables configured

---

## What is Message Ingestion?

Message ingestion is the process of reading NEW messages from Telegram sources and storing them in the local SQLite database.

**Key characteristics**:
- **Incremental**: Only fetches messages newer than the last run (no full history scans)
- **Idempotent**: Re-running the same command won't create duplicate messages
- **Cursor-based**: Uses `ingestion_cursors` table to track progress per source
- **Sanitized**: Sensitive patterns (login codes, verification codes) are redacted before storage

---

## Database Schema

### Table: `ingestion_cursors` (Single Source of Truth)

Tracks the ingestion state for each source:

| Column | Type | Description |
|--------|------|-------------|
| `source_id` | TEXT | Primary key, matches config YAML |
| `tg_chat_id` | INTEGER | Telegram entity ID for the source |
| `last_message_id` | INTEGER | Highest message_id ingested (watermark) |
| `last_message_date` | TEXT | Date of last ingested message |
| `last_run_at` | TEXT | Timestamp of last ingestion run |
| `last_status` | TEXT | Status: running/success/failed |
| `last_error` | TEXT | Error message if failed |

**This is the Single Source of Truth (SSoT) for all ingestion state.**

### Table: `telegram_messages` (Message Storage)

Stores individual messages with idempotency:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `source_id` | TEXT | Source identifier |
| `tg_chat_id` | INTEGER | Telegram entity ID |
| `tg_message_id` | INTEGER | Message ID from Telegram |
| `date` | TEXT | Message timestamp |
| `sender_id` | INTEGER | Sender's Telegram ID |
| `text` | TEXT | **Sanitized** message text |
| `permalink` | TEXT | Direct link to message |
| `raw_json` | TEXT | Full message JSON |
| `ingested_at` | TEXT | When message was stored |
| `processed_status` | TEXT | pending/processing/classified/not_relevant |
| `is_ai_relevant` | INTEGER | NULL/0/1 (for future classification) |

**Idempotency**: `UNIQUE(source_id, tg_message_id)` prevents duplicates at the database level.

---

## Cursor Checkpoint System

The cursor system ensures:

1. **Resumability**: If ingestion is interrupted, it resumes from the last checkpoint
2. **No duplicates**: Only fetches messages with ID > cursor.last_message_id
3. **Crash recovery**: Database survives crashes and restarts
4. **Auditability**: Human-readable state in SQLite

### How it Works

```
Initial state: cursor.last_message_id = 0

Run 1:
  Fetch messages where id > 0
  Insert messages 1-100 to DB
  Update cursor.last_message_id = 100

Run 2:
  Fetch messages where id > 100
  Insert messages 101-150 to DB
  Update cursor.last_message_id = 150

Run 3:
  Fetch messages where id > 150
  No new messages
  cursor.last_message_id stays at 150
```

### Cursor Update Logic

- Cursor is updated **after** successful insert of all messages from a source
- If any message fails, cursor is NOT updated (allowing retry)
- High water mark = max(message_id) from fetched messages
- Next run will fetch from (high_water_mark + 1)

---

## Running Ingestion

### Basic Usage

```bash
# Activate virtual environment
.venv\Scripts\activate

# Dry run (no database writes)
python -m aijobscanner ingest --dry-run

# Ingest from all validated sources
python -m aijobscanner ingest

# Ingest from single source
python -m aijobscanner ingest --only tg_vankar1 --limit-per-source 50

# Ingest and update project_track.md
python -m aijobscanner ingest --update-project-track
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--sources <path>` | Path to telegram_sources.yaml | config/telegram_sources.yaml |
| `--db <path>` | Path to SQLite database | data/db/aijobscanner.sqlite3 |
| `--limit-per-source <N>` | Max messages to fetch per source | 200 |
| `--only <SOURCE_ID>` | Ingest only from specified source | (all sources) |
| `--force` | Ignore validation_status check | False |
| `--dry-run` | Don't write to database | False |
| `--report-dir <path>` | Report output directory | data/reports |
| `--update-project-track [path]` | Update project_track.md | project_track.md |

---

## Message Sanitization

To avoid persisting sensitive data, messages are sanitized before storage.

### Patterns Redacted

| Pattern | Redaction | Example |
|---------|-----------|---------|
| "login code" + 5-6 digits | `[LOGIN CODE REDACTED]` | "Your login code is 123456" → "Your login code [LOGIN CODE REDACTED]" |
| "Telegram code" + 5-6 digits | `[TELEGRAM CODE REDACTED]` | "Telegram code: 789012" → "Telegram code: [TELEGRAM CODE REDACTED]" |
| "code:" + 5-6 digits | `code: [REDACTED]` | "code: 456789" → "code: [REDACTED]" |
| "verification code:" + 5-6 digits | `verification code: [REDACTED]` | "verification code: 654321" → "verification code: [REDACTED]" |
| "reset code" + 5-6 digits | `[RESET CODE REDACTED]` | "reset code 111222" → "reset code [RESET CODE REDACTED]" |

### What is NOT Sanitized

- Phone numbers (job posts contain contact info)
- Salary amounts (job posts contain wages)
- URLs (job application links)
- Regular digits in Persian text

---

## Handling Missed Messages

### Scenario: Source Was Offline During a Run

**Problem**: If a source is temporarily unavailable, the cursor won't update, and messages posted during the outage may be missed when the source comes back online.

**Detection**:
- Check `last_message_date` in cursor vs. actual newest message date
- Large gap may indicate missed messages

**Solution**:
```bash
# Manually backfill by setting lower cursor
# 1. Open SQLite database
sqlite3 data/db/aijobscanner.sqlite3

# 2. Update cursor to earlier message ID
UPDATE ingestion_cursors
SET last_message_id = <earlier_message_id>
WHERE source_id = 'tg_vankar1';

# 3. Re-run ingestion
python -m aijobscanner ingest --only tg_vankar1 --limit-per-source 500
```

---

## Common Errors

### Error: "Session not authorized"

**Cause**: No valid session file found.

**Solution**:
```bash
# Run validation first to create session
python -m aijobscanner validate-sources --write-back
```

### Error: "Source not found: tg_vankar1"

**Cause**: Source ID doesn't exist in config YAML.

**Solution**:
```bash
# List available sources
grep "source_id:" config/telegram_sources.yaml
```

### Error: "No enabled sources found"

**Cause**: All sources are disabled or validation failed.

**Solution**:
```bash
# Check validation status
grep "validation_status:" config/telegram_sources.yaml

# Use --force to ignore validation status
python -m aijobscanner ingest --force
```

### Error: FloodWaitError

**Cause**: Telegram rate limit exceeded.

**Solution**:
- Wait for the specified number of seconds
- Run ingestion again
- Reduce `--limit-per-source` to fetch fewer messages

---

## Verifying Idempotency

Idempotency means re-running the same command won't create duplicate messages.

### Test 1: Run Twice

```bash
# First run
python -m aijobscanner ingest --only tg_vankar1 --limit-per-source 20
# Output: Inserted: 20

# Second run (should show 0 new messages)
python -m aijobscanner ingest --only tg_vankar1 --limit-per-source 20
# Output: Inserted: 0
```

### Test 2: Check Database

```bash
# Open SQLite
sqlite3 data/db/aijobscanner.sqlite3

# Count messages per source
SELECT source_id, COUNT(*) as count
FROM telegram_messages
GROUP BY source_id;

# Check for duplicates (should be 0)
SELECT source_id, tg_message_id, COUNT(*) as count
FROM telegram_messages
GROUP BY source_id, tg_message_id
HAVING count > 1;
```

---

## Querying the Database

### Check High Water Marks

```sql
SELECT source_id, last_message_id, last_message_date, last_status
FROM ingestion_cursors;
```

### Get Message Statistics

```sql
SELECT
    source_id,
    COUNT(*) as total_messages,
    SUM(CASE WHEN processed_status = 'pending' THEN 1 ELSE 0 END) as pending,
    SUM(CASE WHEN processed_status = 'classified' THEN 1 ELSE 0 END) as classified
FROM telegram_messages
GROUP BY source_id;
```

### View Recent Messages

```sql
SELECT
    source_id,
    tg_message_id,
    date,
    SUBSTR(text, 1, 100) as text_preview,
    processed_status
FROM telegram_messages
ORDER BY date DESC
LIMIT 20;
```

### Check for AI-Relevant Messages (future)

```sql
SELECT
    source_id,
    tg_message_id,
    date,
    text,
    permalink
FROM telegram_messages
WHERE is_ai_relevant = 1
ORDER BY date DESC;
```

---

## Report Files

Each ingestion run generates a JSON report in `data/reports/`:

```
ingestion_report_YYYYMMDD_HHMMSS.json
```

**Report Contents**:
- Timestamp
- Summary: total sources, fetched, inserted, skipped, errors
- Per-source results: fetched, inserted, skipped, high_water_mark, errors

**Example**:
```json
{
  "timestamp": "2026-01-29T12:34:56.789Z",
  "summary": {
    "total_sources": 5,
    "total_fetched": 125,
    "total_inserted": 85,
    "total_skipped": 40,
    "total_errors": 0
  },
  "results": [
    {
      "source_id": "tg_vankar1",
      "display_name": "Vankar Jobs",
      "fetched": 25,
      "new_inserted": 20,
      "skipped": 5,
      "high_water_mark": 12345,
      "errors": 0
    }
  ]
}
```

---

## Next Steps

After successful ingestion:

1. **Phase 0 Step 4**: Basic Classification
   - Implement keyword-based classification
   - Update `processed_status` based on results
   - Filter for AI/automation relevant jobs

2. **Phase 1**: Full Pipeline
   - Continuous monitoring daemon
   - Notification system (Bot API)
   - Production deployment

---

## Troubleshooting

### Problem: No messages fetched

**Checks**:
1. Is source validated? Check `validation_status: joined` in YAML
2. Are there new messages since last run? Check `last_message_id` in cursor
3. Is source enabled? Check `enabled: true` in YAML

### Problem: Database locked

**Cause**: Another process is using the database.

**Solution**:
```bash
# Check for running processes
# Windows:
tasklist | findstr python

# Kill the process if needed
taskkill /PID <pid> /F
```

### Problem: Messages not appearing in database

**Checks**:
1. Did you use `--dry-run`? (no database writes)
2. Check SQLite file exists: `ls data/db/`
3. Check for errors in ingestion report
4. Verify database has tables:
   ```sql
   .tables
   ```

---

## Best Practices

1. **Start with dry-run**: Always test with `--dry-run` first
2. **Use small limits**: Start with `--limit-per-source 20` for testing
3. **Check reports**: Review JSON reports after each run
4. **Monitor cursors**: Check `ingestion_cursors` table regularly
5. **Sanitize before storage**: Trust the sanitization logic
6. **Use --only for testing**: Test single sources before ingesting from all
7. **Update project_track.md**: Use `--update-project-track` to track progress

---

## Quick Reference

```bash
# Dry run (no writes)
python -m aijobscanner ingest --dry-run

# Ingest from single source (small limit)
python -m aijobscanner ingest --only tg_vankar1 --limit-per-source 20

# Full ingestion
python -m aijobscanner ingest --update-project-track

# Check database
sqlite3 data/db/aijobscanner.sqlite3
SELECT * FROM ingestion_cursors;
SELECT source_id, COUNT(*) FROM telegram_messages GROUP BY source_id;

# Force re-ingest (ignore validation status)
python -m aijobscanner ingest --force

# Backfill missed messages
sqlite3 data/db/aijobscanner.sqlite3
UPDATE ingestion_cursors SET last_message_id = <earlier_id> WHERE source_id = '<source_id>';
```

---

**For more information**, see:
- `project_track.md` - Project progress tracking
- `ADR/001-telegram-ingestion-choice.md` - Architecture decision
- `docs/runbooks/telegram_validation.md` - Source validation guide
