# Classification MVP Runbook

**Purpose**: Guide for classifying Telegram messages for AI/automation relevance using heuristic keyword matching.

**Prerequisites**:
- Phase 0 Step 3 completed (messages ingested into SQLite)
- SQLite database with pending messages
- Environment configured

---

## What is Heuristic Classification?

Heuristic classification uses keyword matching with weights to determine if a job post is relevant for AI/automation work.

**Key characteristics**:
- **Deterministic**: Same input always produces same output (no LLM calls)
- **Bilingual**: Supports English and Persian (Farsi) keywords
- **Weighted**: Different keyword groups have different weights
- **Guardrails**: Remote keywords only count when paired with tech keywords
- **Auditable**: Full classification metadata stored for tuning

---

## Database Schema

### Table: `telegram_messages` (Updated)
Now includes classification fields:

| Column | Type | Description |
|--------|------|-------------|
| `processed_status` | TEXT | pending, classified, etc. |
| `is_ai_relevant` | INTEGER | 0 or 1 |
| `ai_relevance_score` | REAL | Relevance score |
| `classified_at` | TEXT | When message was classified |

### Table: `message_classifications` (Audit Trail)
Stores full classification history:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `source_id` | TEXT | Source identifier |
| `tg_message_id` | INTEGER | Message ID from Telegram |
| `tg_chat_id` | INTEGER | Telegram chat ID |
| `classifier_version` | TEXT | Version identifier (e.g., "1.0.0") |
| `is_ai_relevant` | INTEGER | 0 or 1 |
| `score` | REAL | Relevance score |
| `reasons_json` | TEXT | JSON array of reason strings |
| `classification_metadata` | TEXT | JSON with matched keywords, weights |
| `created_at` | TEXT | Timestamp |

**Critical**: `classification_metadata` contains:
- `matched_keywords`: List of keywords found
- `matched_groups`: List of keyword groups triggered
- `weights_applied`: Weights for each group
- `negative_matches`: Negative keywords found
- `score_breakdown`: Score per group
- `guardrail_triggered`: Whether guardrail was applied

---

## Running Classification

### Basic Usage

```bash
# Activate virtual environment
.venv\Scripts\activate

# Dry run (no database writes)
python -m aijobscanner classify --dry-run

# Classify pending messages
python -m aijobscanner classify

# Classify from single source
python -m aijobscanner classify --only tg_vankar1 --limit 50

# Reprocess already-classified messages
python -m aijobscanner classify --reprocess

# Classify and update project track
python -m aijobscanner classify --update-project-track
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--db <path>` | Path to SQLite database | data/db/aijobscanner.sqlite3 |
| `--limit <N>` | Max messages to classify | 500 |
| `--only <SOURCE_ID>` | Classify only from specified source | (all sources) |
| `--reprocess` | Reprocess already-classified messages | False |
| `--dry-run` | Classify without writing to database | False |
| `--export-dir <path>` | CSV export directory | data/review |
| `--export-limit <N>` | Max candidates to export | 100 |
| `--update-project-track <path>` | Update project_track.md | project_track.md |

---

## Keyword Groups

### High Weight (1.0)

#### Tech Core
**English**: software, developer, programmer, engineer, API, database, SQL, etc.
**Persian**: برنامه نویس, توسعه دهنده, مهندس نرم افزار, پایگاه داده

#### Automation
**English**: automation, script, Python, JavaScript, bash, workflow, pipeline
**Persian**: اتوماسیون, اسکریپت, پایتون, جاوااسکریپت, پاورشل

#### DevOps
**English**: DevOps, Docker, Kubernetes, AWS, Linux, server
**Persian**: دوکر, کوبرنتیز, لینوکس, سرور, کلاد

#### AI/ML
**English**: AI, ML, LLM, NLP, computer vision, prompt
**Persian**: هوش مصنوعی, یادگیری ماشین, مدل زبانی, NLP

#### Security
**English**: security, pentest, SOC, vulnerability, OWASP
**Persian**: امنیت, تست نفوذ, آسیب پذیری, OWASP

### Medium Weight (0.7)

#### IT Support
**English**: IT support, helpdesk, sysadmin, network, VPN
**Persian**: پشتیبانی IT, هلپ دسک, ادمین سیستم, شبکه

### Low Weight (0.2)

#### Remote
**English**: remote, WFH, freelance, contract, project-based
**Persian**: دورکاری, فریلنس, پروژه‌ای, قراردادی

**Guardrail**: Remote keywords ONLY count when paired with tech keywords. A job that's only "remote" with no tech keywords will NOT be classified as AI-relevant.

### Negative (Filter)

#### Non-Tech Jobs
**English**: cashier, waiter, driver, warehouse, construction, cleaner
**Persian**: صندوقدار, گارسون, راننده, انبار, ساختمان, نظافت

**Rule**: If negative keywords appear without strong tech keywords, the message is marked as NOT relevant.

---

## Scoring Algorithm

### Calculation
```
base_score = 0.0

for each keyword group:
    for each keyword match in text:
        base_score += group.weight

# Guardrail 1: Remote requires tech
if remote_low matched and no high/mid tech matched:
    base_score = 0.0

# Guardrail 2: Negative filter
if negative_nontech matched and no high tech matched:
    base_score = 0.0

is_ai_relevant = (base_score >= 0.7) ? 1 : 0
```

### Threshold
- Score >= 0.7 → AI Relevant (is_ai_relevant = 1)
- Score < 0.7 → Not Relevant (is_ai_relevant = 0)

---

## CSV Export

### What Gets Exported
Only messages where `is_ai_relevant = 1` are exported to CSV.

### CSV Columns
| Column | Description | Security |
|--------|-------------|----------|
| `source_id` | Telegram source identifier | Raw |
| `tg_message_id` | Message ID | Raw |
| `date` | Message date | Raw |
| `score` | AI relevance score | Raw |
| `snippet` | First 200 chars of text | Truncated, formula-safe |
| `reasons` | Comma-separated reasons | Raw |
| `matched_keywords` | Keywords that triggered | Raw |
| `permalink` | Direct link to message | Raw |

### Security Measures

#### 1. Formula Injection Mitigation
Excel treats cells starting with `=`, `+`, `-`, `@` as formulas. We prefix these cells with a single quote (`'`) to force text interpretation.

**Example**:
- Cell value: `=SUM(A1:A10)` → Exported as: `'=SUM(A1:A10)`

#### 2. Snippet Truncation
- Text truncated to 200 characters maximum
- Newlines stripped (replaced with spaces)
- Prevents CSV corruption

#### 3. No Full Text Export
- Only snippets exported
- Full text remains in database (gitignored)
- Reduces risk of sensitive data leakage

### CSV Format
- **RFC 4180** compliant
- Quoting: `csv.QUOTE_MINIMAL`
- Newline handling: `newline=""` in csv.writer
- Encoding: UTF-8
- Location: `data/review/candidates_<timestamp>.csv`

---

## Adding Keywords Safely

### Runtime (Temporary)
```python
from aijobscanner.classify import add_keyword

# Add English keyword
add_keyword("automation_high", "graphql", "en")

# Add Persian keyword
add_keyword("automation_high", "گراف کیو ال", "fa")
```

### Permanent (Code)
Edit `src/aijobscanner/classify/rules.py`:

```python
"automation_high": {
    "weight": 1.0,
    "keywords_en": [
        # ... existing keywords ...
        "graphql",  # NEW
    ],
    "keywords_fa": [
        # ... existing keywords ...
        "گراف کیو ال",  # NEW
    ],
},
```

### Best Practices
1. **Start conservative**: Add fewer keywords, test, then expand
2. **Test with dry-run**: Always use `--dry-run` first
3. **Check false positives**: Review exported CSV for irrelevant jobs
4. **Check false negatives**: Review database for jobs that should be relevant
5. **Tune weights**: Adjust group weights if needed
6. **Version control**: Track changes to `rules.py`

---

## Tuning Keywords

### 1. Analyze Classifications
```bash
# Run classification
python -m aijobscanner classify

# Export candidates
# Check CSV for false positives
```

### 2. Review Metadata
Query the `message_classifications` table:
```sql
SELECT
    tg_message_id,
    score,
    reasons_json,
    classification_metadata
FROM message_classifications
WHERE classifier_version = '1.0.0'
ORDER BY score DESC;
```

### 3. Adjust Keywords
Based on findings:
- **Too many false positives**: Remove generic keywords, increase threshold
- **Too many false negatives**: Add more keywords, decrease threshold
- **Persian jobs missed**: Add more FA keywords
- **Remote jobs overmatched**: Check if guardrail is working

### 4. Update Classifier Version
After changing keywords, update `CLASSIFIER_VERSION` in `src/aijobscanner/classify/run.py`:
```python
CLASSIFIER_VERSION = "1.1.0"  # Changed from 1.0.0
```

This allows you to compare performance across versions.

---

## Common Errors

### Error: "No pending messages"
**Cause**: All messages already classified or no messages in database.

**Solution**:
```bash
# Check database
python -c "import sqlite3; conn = sqlite3.connect('data/db/aijobscanner.sqlite3'); c = conn.execute('SELECT processed_status, COUNT(*) FROM telegram_messages GROUP BY processed_status'); print(c.fetchall())"

# Use --reprocess to reclassify
python -m aijobscanner classify --reprocess
```

### Error: "No AI-relevant candidates to export"
**Cause**: No messages scored >= 0.7

**Solution**:
```bash
# Run with dry-run to see scores
python -m aijobscanner classify --dry-run

# Check classification metadata in database
```

### Error: "Database file not found"
**Cause**: Database doesn't exist yet.

**Solution**:
```bash
# Run ingestion first to create database
python -m aijobscanner ingest --limit 10
```

### Error: "UnicodeEncodeError" on Windows
**Cause**: Persian characters in console output.

**Solution**: This is handled by the system. CSV export uses UTF-8.

---

## Verification

### Check Classification Results

#### Method 1: CSV Export
```bash
# Run classification
python -m aijobscanner classify

# Open CSV in Excel
# Verify:
# - No formula execution (cells starting with ' are safe)
# - Snippets are <= 200 chars
# - All entries have tech keywords
```

#### Method 2: Database Query
```sql
-- Check classification statistics
SELECT
    processed_status,
    is_ai_relevant,
    COUNT(*) as count,
    AVG(ai_relevance_score) as avg_score
FROM telegram_messages
GROUP BY processed_status, is_ai_relevant;

-- Check high-scoring messages
SELECT
    source_id,
    tg_message_id,
    SUBSTR(text, 1, 100) as text_preview,
    ai_relevance_score,
    classified_at
FROM telegram_messages
WHERE is_ai_relevant = 1
ORDER BY ai_relevance_score DESC
LIMIT 20;
```

#### Method 3: Idempotency Test
```bash
# First run
python -m aijobscanner classify --limit 50
# Output: Processed: 50, AI Relevant: 10

# Second run (should be 0 unless --reprocess)
python -m aijobscanner classify --limit 50
# Output: Processed: 0, AI Relevant: 0
```

---

## Guardrail Examples

### Example 1: Remote Without Tech
**Input**: "Remote waiter wanted for restaurant"
**Score Calculation**:
- "remote" → remote_low (+0.2)
- No tech keywords matched
- Guardrail triggered: remote without tech = 0.0
- **Final Score**: 0.0
- **AI Relevant**: No

### Example 2: Tech With Remote
**Input**: "Python developer needed for automation script. Remote OK."
**Score Calculation**:
- "python" → automation_high (+1.0)
- "automation" → automation_high (+1.0)
- "script" → automation_high (+1.0)
- "remote" → remote_low (+0.2)
- Tech matched, remote counted
- **Final Score**: 3.2
- **AI Relevant**: Yes

### Example 3: Non-Tech Job
**Input**: "Warehouse worker needed for shipping department"
**Score Calculation**:
- "warehouse" → negative_nontech (-1.0)
- No tech keywords matched
- Negative filter applied
- **Final Score**: 0.0
- **AI Relevant**: No

---

## Performance Tips

### 1. Use --limit for Testing
```bash
# Test with small batch
python -m aijobscanner classify --limit 50
```

### 2. Use --only for Specific Sources
```bash
# Classify one source
python -m aijobscanner classify --only tg_vankar1
```

### 3. Batch Processing
```bash
# Process in batches
python -m aijobscanner classify --limit 1000
python -m aijobscanner classify --limit 1000
python -m aijobscanner classify --limit 1000
```

### 4. Check Statistics First
```bash
# Run dry-run to see what would be processed
python -m aijobscanner classify --dry-run
```

---

## Troubleshooting

### Problem: Too Many False Positives
**Symptoms**: CSV contains irrelevant jobs

**Solutions**:
1. Remove generic keywords from rules.py
2. Increase score threshold (modify `classify()` function)
3. Add more negative keywords
4. Check if guardrail is working correctly

### Problem: Too Many False Negatives
**Symptoms**: Known relevant jobs not exported

**Solutions**:
1. Add more keywords to relevant groups
2. Decrease score threshold
3. Check if keywords are matching (case sensitivity)
4. Verify Persian keywords are correct

### Problem: Persian Jobs Not Classified
**Symptoms**: Persian/Farsi jobs never marked as relevant

**Solutions**:
1. Verify Persian keywords in rules.py are correct
2. Check for encoding issues
3. Test with known Persian job text
4. Add more Persian keywords

### Problem: CSV Opens Corrupted
**Symptoms**: Excel shows misaligned columns

**Solutions**:
1. Ensure RFC 4180 compliance (csv.QUOTE_MINIMAL)
2. Check for unescaped newlines
3. Verify newline="" in csv.writer
4. Check for unescaped quotes in text

---

## Best Practices

1. **Always start with dry-run**: Test before writing to database
2. **Review CSV exports**: Check for false positives/negatives
3. **Tune incrementally**: Small changes, test, repeat
4. **Track versions**: Update CLASSIFIER_VERSION when changing keywords
5. **Backup database**: Before major changes
6. **Monitor statistics**: Track classified/relevant ratios over time
7. **Test with real data**: Use actual job posts for testing

---

## Quick Reference

```bash
# Dry run (no writes)
python -m aijobscanner classify --dry-run

# Classify pending
python -m aijobscanner classify

# Reprocess all
python -m aijobscanner classify --reprocess

# Single source
python -m aijobscanner classify --only tg_vankar1

# With project track update
python -m aijobscanner classify --update-project-track

# Query database
sqlite3 data/db/aijobscanner.sqlite3
SELECT * FROM telegram_messages WHERE is_ai_relevant = 1 LIMIT 10;
```

---

**For more information**, see:
- `project_track.md` - Project progress tracking
- `docs/runbooks/telegram_ingestion.md` - Ingestion guide
- `src/aijobscanner/classify/rules.py` - Keyword definitions
