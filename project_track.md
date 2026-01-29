# AI Job Scanner - Project Track

**Last Updated**: 2026-01-29
**Current Phase**: Phase 0 - Foundation
**Current Step**: Step 2 - MTProto Session Bootstrap + Source Validation ✅ **COMPLETE**
**Repository**: https://github.com/sia12-web/AI-Job-Scanner.git

---

## Project Summary

**Goal**: Monitor Telegram sources (groups/channels) that post job offers, classify which tasks can be done remotely by AI/automation, and notify the user with relevant post details.

**Core Architecture**:
- **Ingestion**: MTProto user client (Telethon) for reading messages from groups/channels
- **Processing**: Classify job posts for AI/automation suitability
- **Notification**: Bot API sends DMs to user with relevant job details

**Target Sources**:
- Persian-language job channels for Canada (primarily Vancouver)
- One group with job postings
- Focus on remote-friendly and AI-suitable tasks

---

## Current Phase/Step Status

### Phase 0: Foundation ✅
**Goal**: Set up project documentation, architecture decisions, and basic infrastructure

#### Step 1: Telegram Sources + Access Strategy ✅ COMPLETE
- [x] Create persistent tracking (project_track.md)
- [x] Create directory structure
- [x] Document architecture decision (ADR-001)
- [x] Create Telegram sources registry
- [x] Document access strategy
- [x] Document security rules

#### Step 2: MTProto Session Bootstrap + Source Validation ✅ COMPLETE
- [x] Create Python package structure
- [x] Implement validation CLI with Telethon
- [x] Create security gates (.gitignore, .env.example)
- [x] Write validation runbook
- [x] Validate all 5 sources successfully
- [x] Initialize git repository
- [x] Commit initial implementation
- [x] Add remote repository

**Validation Results** (2026-01-29):
- ✅ 5/5 sources validated successfully
- ✅ Canada Jobs Group (group): Entity ID 1342573502
- ✅ Vankar Jobs (channel): Entity ID 1367311696
- ✅ Karyabi Canada (channel): Entity ID 1221567462
- ✅ JoyaKar Vancouver (channel): Entity ID 1065263857
- ✅ Job Canada (channel): Entity ID 1910830444
- ✅ 25 messages read (5 per source) to verify readability
- ✅ Session file created: `data/telegram_session/14389253715.session`

#### Step 3: Message Ingestion MVP (NEXT)
- [ ] Implement continuous message reading from validated sources
- [ ] Create PostEvent normalization structure
- [ ] Test with one group source
- [ ] Test with one channel source
- [ ] Validate unified source model

#### Step 4: Basic Classification (FUTURE)
- [ ] Implement message reader for one source
- [ ] Create PostEvent normalization structure
- [ ] Test message ingestion from group
- [ ] Test message ingestion from channel

---

## Source Registry

| Source ID | Type | Display Name | Language | Status | Priority | Entity ID |
|-----------|------|--------------|----------|---------|----------|-----------|
| `tg_invite_HBKt5e9nhxVjMzgx` | group | Canada Jobs Group | fa | ✅ joined | high | 1342573502 |
| `tg_vankar1` | channel | Vankar Jobs | fa | ✅ joined | high | 1367311696 |
| `tg_karyabi_canada` | channel | Karyabi Canada | fa | ✅ joined | high | 1221567462 |
| `tg_joyakar_vancouver` | channel | JoyaKar Vancouver | fa | ✅ joined | high | 1065263857 |
| `tg_jobcanadaaa` | channel | Job Canada | fa | ✅ joined | high | 1910830444 |

**Full details**: See `config/telegram_sources.yaml`

---

## Key Decisions

### 1. Two-Lane Architecture (ADR-001)
**Decision**: Use MTProto user client for ingestion, Bot API for notifications
**Rationale**:
- Bots may not be allowed in groups
- Privacy mode limits bot visibility
- Bot-to-bot messages are not received
**Status**: Accepted
**Details**: `ADR/001-telegram-ingestion-choice.md`

### 2. Unified Source Model
**Decision**: Normalize groups and channels to same internal PostEvent format
**Rationale**:
- Simplifies downstream processing
- Only join/subscribe mechanics differ
- Single pipeline for all sources
**Status**: Accepted

### 3. Security-First Approach
**Decision**: Use dedicated monitoring account with encrypted session storage
**Rationale**:
- Isolate personal account from monitoring activity
- Protect session files from compromise
- Minimize data retention
**Status**: Accepted
**Details**: `security/telegram_session_rules.md`

### 4. Python + Telethon Tech Stack
**Decision**: Use Python 3.12 + Telethon for MTProto client
**Rationale**:
- Mature library with excellent async support
- Good documentation and community support
- Proven reliability for Telegram automation
**Status**: Accepted
**Implementation**: Phase 0 Step 2

---

## Repository Map

```
AI Job Scanner/
├── project_track.md           # THIS FILE - Single source of truth
├── requirements.txt           # Python dependencies
├── setup.py                   # Package installer
├── .env.example               # Environment variables template
├── .gitignore                 # Security gates (blocks sessions/secrets)
│
├── config/                    # Configuration files
│   └── telegram_sources.yaml  # Telegram source registry (validated)
│
├── src/                       # Source code
│   └── aijobscanner/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py             # CLI entrypoint
│       └── telegram/
│           ├── __init__.py
│           ├── config.py      # YAML loading/saving
│           └── validate.py    # Validation logic
│
├── data/                      # Data storage (gitignored)
│   ├── telegram_session/      # Telethon session files
│   └── reports/               # Validation reports
│
├── docs/                      # Documentation
│   ├── telegram_access.md     # Two-lane architecture docs
│   └── runbooks/
│       └── telegram_validation.md  # Validation how-to guide
│
├── ADR/                       # Architecture Decision Records
│   └── 001-telegram-ingestion-choice.md
│
├── security/                  # Security policies
│   └── telegram_session_rules.md
│
└── studio/                    # Project state tracking
    └── STATE.md               # Quick state reference
```

**Git Repository**: https://github.com/sia12-web/AI-Job-Scanner.git

---

## Resume Checklist

If you need to continue work after restarting your terminal:

1. **Read current state**:
   ```bash
   # Read this file first
   cat project_track.md

   # Quick state reference
   cat studio/STATE.md
   ```

2. **Activate virtual environment**:
   ```bash
   cd "C:\Users\shahb\myApplications\AI Job Scanner"
   .venv\Scripts\activate
   ```

3. **Check what's done**:
   - Look at checkboxes in "Current Phase/Step Status" section
   - Review change log below

4. **Continue from where you left off**:
   - Find first unchecked item in current step
   - Read relevant documentation (docs/, ADR/)
   - Check security rules before implementing

5. **Before writing code**:
   - Review `security/telegram_session_rules.md`
   - Check `config/telegram_sources.yaml` for source details
   - Read relevant ADRs for architectural context

6. **After completing work**:
   - Update `project_track.md` (this file)
   - Check off completed items
   - Add entry to change log
   - Commit changes to git

---

## Next 3 Steps

### Immediate (Phase 0 Step 3)
**Goal**: Implement message ingestion MVP
- Add continuous message reading from validated sources
- Create PostEvent normalization structure
- Test with one group and one channel
- Validate unified source model

**Estimated effort**: 4-6 hours

### Short-term (Phase 0 Step 4)
**Goal**: Basic job classification
- Extract job details from messages
- Implement simple keyword matching
- Test classification accuracy on sample messages
- Filter for AI/automation suitability

**Estimated effort**: 4-6 hours

### Medium-term (Phase 1: Full Pipeline)
**Goal**: End-to-end job scanning pipeline
- Implement continuous monitoring
- Add notification system (Bot API)
- Deploy to production environment
- Set up monitoring and alerts

**Estimated effort**: 8-12 hours

---

## Risks & Mitigations

### Risk 1: Monitoring Account Blocked by Telegram
**Impact**: High - Could lose access to all sources
**Probability**: Medium
**Mitigation**:
- Use dedicated account (not personal/main account)
- Follow rate limits strictly
- Mimic human behavior patterns
- Avoid spam-like activity
**Fallback**: Propose mirror/forward-to-owned-channel workaround
**Status**: Account active, 5 sources joined successfully

### Risk 2: Session File Compromise
**Impact**: High - Unauthorized access to account
**Probability**: Low
**Mitigation**:
- Session file in `.gitignore` (protected)
- Never commit to version control
- Use strong passwords
- Regular security audits
**Status**: ✅ Session secured (40KB file in data/telegram_session/)

### Risk 3: Bot Privacy Mode Limitations
**Impact**: Medium - Limited visibility in groups
**Probability**: High (known limitation)
**Mitigation**:
- Use MTProto user client (not bot) for ingestion
- This is why we chose two-lane architecture
- See ADR-001 for details
**Status**: ✅ Mitigated by architecture decision

### Risk 4: Source Access Denied
**Impact**: Medium - Cannot monitor specific source
**Probability**: Low (all 5 sources validated successfully)
**Mitigation**:
- Document "hard constraint" in access docs
- All sources currently accessible
**Status**: ✅ All sources validated and accessible

### Risk 5: Data Over-Collection/Retention
**Impact**: Medium - Privacy/legal concerns
**Probability**: Low
**Mitigation**:
- Minimal retention policy
- Only collect necessary data
- Regular cleanup of old data
- Document retention periods
**Reference**: `security/telegram_session_rules.md`

---

## Change Log

### 2026-01-29 - Phase 0 Step 2: MTProto Session Bootstrap + Source Validation
**Completed**:
- Created Python package structure (src/aijobscanner/)
- Implemented validation CLI with Telethon (validate-sources command)
- Created configuration files (requirements.txt, .env.example, .gitignore)
- Implemented core validation logic:
  - SourceValidator class with connect/disconnect
  - Group join logic (ImportChatInviteRequest)
  - Channel subscribe logic (JoinChannelRequest)
  - Message readability verification
  - Entity resolution for already-joined groups
- Implemented YAML loading/saving with validation
- Created security gates (.gitignore blocks sessions and .env)
- Created validation runbook (docs/runbooks/telegram_validation.md)
- Initialized git repository
- Added remote repository (GitHub)
- Committed initial implementation (commit d4b2e1b)

**Key Features Implemented**:
1. Async Telegram client using Telethon 1.42.0
2. Unified validation pipeline for groups and channels
3. Dry-run mode for safe testing
4. Write-back mode to update YAML with validation results
5. JSON report generation for auditing
6. Rate limiting awareness (FloodWaitError handling)
7. 2FA support for Telegram accounts
8. Invite hash extraction bug fix

**Tech Stack Chosen**: Python + Telethon
- Python 3.12.4
- Telethon 1.42.0
- PyYAML 6.0.3
- python-dotenv 1.2.1

**Files Created**:
- `requirements.txt`: telethon, pyyaml, python-dotenv
- `.env.example`: Template for TG_API_ID, TG_API_HASH, TG_PHONE
- `.gitignore`: Blocks sessions, .env, reports, __pycache__
- `setup.py`: Package installer for editable mode
- `src/aijobscanner/__init__.py`: Package initialization
- `src/aijobscanner/__main__.py`: Module entrypoint
- `src/aijobscanner/cli.py`: CLI with argparse (validate-sources command)
- `src/aijobscanner/telegram/config.py`: YAML load/save functions
- `src/aijobscanner/telegram/validate.py`: SourceValidator class
- `src/aijobscanner/telegram/__init__.py`: Module exports
- `docs/runbooks/telegram_validation.md`: How-to guide
- Created directories: data/telegram_session/, data/reports/, docs/runbooks/

**Validation Results**:
- All 5 sources validated successfully
- 1 group (Canada Jobs Group): joined, messages readable
- 4 channels: all joined, messages readable
- Entity IDs resolved for all sources
- Configuration updated with validation_status, timestamps
- JSON report created: data/reports/source_validation_20260129_054443.json

**Session Information**:
- Phone: +14389253715
- Session file: data/telegram_session/14389253715.session
- Size: 40KB
- Created: 2026-01-29
- Status: Active and secure

**Git Repository**:
- Remote: https://github.com/sia12-web/AI-Job-Scanner.git
- First commit: d4b2e1b (Phase 0 Step 2 implementation)
- Files tracked: 18
- Sensitive files excluded: .env, data/telegram_session/, data/reports/

**Security Measures Implemented**:
- Session files in .gitignore (treated as passwords)
- .env file blocked from git
- No hardcoded credentials
- Environment variable validation
- Session file stored securely locally

**Bugs Fixed**:
1. Invite hash extraction - Fixed regex for t.me/+HASH format
2. Entity resolution for already-joined groups - Added dialog iteration
3. Unicode encoding - Replaced emojis with ASCII for Windows console

**CLI Commands Available**:
```bash
# Activate environment
.venv\Scripts\activate

# Dry run (no YAML updates)
python -m aijobscanner validate-sources --dry-run

# Validate single source
python -m aijobscanner validate-sources --only tg_vankar1 --dry-run

# Write validation results to YAML
python -m aijobscanner validate-sources --write-back

# Validate with custom message limit
python -m aijobscanner validate-sources --limit 10
```

**Next**: Phase 0 Step 3 - Message Ingestion MVP

---

### 2026-01-28 - Phase 0 Step 1 Foundation
**Completed**:
- Created project tracking system (project_track.md)
- Set up directory structure (config/, docs/, ADR/, security/, studio/)
- Documented two-lane architecture decision (ADR-001)
- Created Telegram sources registry with 5 sources (1 group, 4 channels)
- Documented Telegram access strategy with evidence-based rationale
- Created security rules for session management
- Created quick state reference (studio/STATE.md)

**Key Decisions Made**:
1. MTProto user client for ingestion (not bot-only)
2. Bot API for notifications (separate concern)
3. Unified source model (groups + channels)
4. Security-first approach (dedicated account, encrypted sessions)

**Sources Registered**:
- tg_invite_HBKt5e9nhxVjMzgx (group)
- tg_vankar1 (channel)
- tg_karyabi_canada (channel)
- tg_joyakar_vancouver (channel)
- tg_jobcanadaaa (channel)

**Next**: Phase 0 Step 2 - Project structure and tech stack selection

---

## Notes

### Language Context
- Most sources are Persian-language (Farsi: "fa")
- Jobs target Iranian community in Canada (primarily Vancouver)
- May need translation/parsing for Persian text

### Join Mechanics Reminder
- **Groups**: Join via invite link → See messages from all participants
- **Channels**: Subscribe/follow → See posts from admins only
- **Pipeline**: Identical after ingestion (unified PostEvent)

### Session File Security
- Session file: `data/telegram_session/14389253715.session`
- Contains authentication credentials
- MUST be encrypted at rest (future enhancement)
- MUST be in .gitignore
- Use environment variable for encryption key
- Never hardcode secrets

### Rate Limiting
- Telegram has rate limits for MTProto
- Will implement priority-based scheduling later
- High-priority sources checked more frequently
- All sources: respect Telegram's ToS

### Git Workflow
```bash
# View commit history
git log --oneline

# View last commit details
git show HEAD

# Push to remote (when ready)
git push -u origin master

# Pull latest changes
git pull origin master
```

---

## Quick Reference

**Key Files**:
- Tracking: `project_track.md` (this file)
- Sources: `config/telegram_sources.yaml`
- Architecture: `ADR/001-telegram-ingestion-choice.md`
- Access: `docs/telegram_access.md`
- Security: `security/telegram_session_rules.md`
- State: `studio/STATE.md`

**Important Links**:
- Telegram Bot API: https://core.telegram.org/bots/api
- Bot Privacy Mode: https://core.telegram.org/bots/features#privacy-mode
- MTProto: https://core.telegram.org/mtproto
- Telethon (Python): https://docs.telethon.dev/
- GitHub Repository: https://github.com/sia12-web/AI-Job-Scanner.git

**Commands to Remember**:
```bash
# View project status
cat project_track.md

# Quick state check
cat studio/STATE.md

# View sources
cat config/telegram_sources.yaml

# Check architecture decisions
ls ADR/

# Check security rules
cat security/telegram_session_rules.md

# Run validation
python -m aijobscanner validate-sources --dry-run

# Git operations
git status
git log --oneline
git push -u origin master
```

---

**Remember**: ALWAYS update this file when completing work or making changes. This is the single source of truth for project progress.
