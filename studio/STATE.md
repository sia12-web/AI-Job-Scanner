# AI Job Scanner - Project State

**Last Updated**: 2026-01-28
**Current Phase**: Phase 0 - Foundation
**Current Step**: Step 2 - MTProto Session Bootstrap + Source Validation

---

## Quick Status

**Overall Progress**: Phase 0 Step 2 ✅ **COMPLETE**

```
Phase 0: Foundation
├── Step 1: Telegram Sources + Access Strategy ✅ DONE
├── Step 2: MTProto Session Bootstrap + Source Validation ✅ DONE
├── Step 3: Message Ingestion MVP (NEXT)
└── Step 4: Basic Classification (FUTURE)
```

---

## Current Phase/Step Details

### Phase 0: Foundation
**Goal**: Set up project documentation, architecture decisions, and basic infrastructure

#### ✅ Step 1: Telegram Sources + Access Strategy (COMPLETE)
**Completed**: 2026-01-28

**Deliverables created**:
- ✅ `project_track.md` - Persistent tracking system
- ✅ `config/telegram_sources.yaml` - 5 sources registered (1 group, 4 channels)
- ✅ `docs/telegram_access.md` - Two-lane architecture documentation
- ✅ `ADR/001-telegram-ingestion-choice.md` - Architecture decision record
- ✅ `security/telegram_session_rules.md` - Security guidelines
- ✅ `studio/STATE.md` - This file

**Key decisions made**:
1. **Two-lane architecture**:
   - Lane A: MTProto user client for ingestion (reading messages)
   - Lane B: Bot API for notifications (sending DMs)
2. **Unified source model**: Groups and channels normalized to same PostEvent format
3. **Security-first**: Dedicated monitoring account, encrypted sessions

**Sources registered**:
- `tg_invite_HBKt5e9nhxVjMzgx` (group)
- `tg_vankar1` (channel)
- `tg_karyabi_canada` (channel)
- `tg_joyakar_vancouver` (channel)
- `tg_jobcanadaaa` (channel)

**Tech stack**: Python + Telethon ✅ **CHOSEN**

---

#### ✅ Step 2: MTProto Session Bootstrap + Source Validation (COMPLETE)
**Completed**: 2026-01-28

**Deliverables**:
- ✅ Python package structure (`src/aijobscanner/`)
- ✅ Validation CLI with Telethon
- ✅ Security gates (`.gitignore`, `.env.example`)
- ✅ Validation runbook
- ✅ Updated `project_track.md`

**Tech stack chosen**: Python + Telethon
- Rationale: Mature library, excellent async support, good documentation

**Key files created**:
- `requirements.txt`: Dependencies (telethon, pyyaml)
- `.env.example`: Template for Telegram credentials
- `.gitignore`: Security gates for sessions/secrets
- `src/aijobscanner/telegram/config.py`: YAML loading/saving
- `src/aijobscanner/telegram/validate.py`: SourceValidator class
- `src/aijobscanner/cli.py`: CLI entrypoint (`validate-sources` command)
- `docs/runbooks/telegram_validation.md`: How-to guide

**CLI command available**:
```bash
python -m aijobscanner validate-sources --dry-run
```

**Sources ready for validation**:
- `tg_invite_HBKt5e9nhxVjMzgx` (group) - invite link provided
- `tg_vankar1` (channel) - @vankar1
- `tg_karyabi_canada` (channel) - @karyabi_canada
- `tg_joyakar_vancouver` (channel) - @JoyaKarVancouver
- `tg_jobcanadaaa` (channel) - @jobcanadaaa

**Validation status**: TBD (will be set when validator runs)

---

#### 🔄 Step 3: Message Ingestion MVP (NEXT)
**Status**: Not started

**Tasks**:
- [ ] Implement continuous message reading from validated sources
- [ ] Create PostEvent normalization structure
- [ ] Test message ingestion from one group
- [ ] Test message ingestion from one channel
- [ ] Validate unified source model

**Estimated effort**: 4-6 hours

---

#### ⏳ Step 4: Basic Classification (FUTURE)
**Status**: Not started

**Tasks**:
- [ ] Implement message reader for one source
- [ ] Create PostEvent normalization structure
- [ ] Test message ingestion from group
- [ ] Test message ingestion from channel
- [ ] Validate unified source model
- [ ] Basic message parsing/processing

---

## Key Decisions

| ID | Decision | Status | Link |
|----|----------|--------|------|
| ADR-001 | Two-lane architecture (MTProto + Bot API) | Accepted | [ADR-001](../ADR/001-telegram-ingestion-choice.md) |
| 002 | Unified source model (groups + channels) | Accepted | [Access Strategy](../docs/telegram_access.md) |
| 003 | Security-first approach | Accepted | [Security Rules](../security/telegram_session_rules.md) |
| 004 | Python + Telethon tech stack | Accepted | Step 2 implementation |

---

## Next 3 Steps

### 1. Immediate (Phase 0 Step 3)
**Message Ingestion MVP**
- Implement continuous message reading from validated sources
- Create PostEvent normalization structure
- Test with one group and one channel
- Validate unified source model

**Estimated effort**: 4-6 hours

### 2. Short-term (Phase 0 Step 4)
**Basic Classification**
- Extract job details from messages
- Implement simple keyword matching
- Test classification accuracy

**Estimated effort**: 4-6 hours

### 3. Medium-term (Phase 1: Full Pipeline)
**End-to-End Pipeline**
- Implement continuous monitoring
- Add notification system (Bot API)
- Deploy to production

**Estimated effort**: 8-12 hours

---

## Open Risks

### Risk 1: Source Access Validation
**Status**: In Progress
**Impact**: High
**Mitigation**: Run validator to test access, document failures
**Contingency**: Use forward-to-owned-channel workaround
**Next action**: Run `python -m aijobscanner validate-sources --dry-run`

### Risk 2: Account Blocking
**Status**: Low probability
**Impact**: High
**Mitigation**: Use dedicated account, follow rate limits, behave like human
**Monitoring**: Watch for Telegram warnings/suspensions

### Risk 3: Message Volume
**Status**: Unknown
**Impact**: Medium
**Mitigation**: Implement rate limiting, prioritize high-value sources
**Contingency**: Throttling and batch processing

---

## Quick Reference

### Essential Commands

```bash
# View project status
cat project_track.md

# Quick state check
cat studio/STATE.md

# View sources
cat config/telegram_sources.yaml

# Run validation (dry-run)
python -m aijobscanner validate-sources --dry-run

# Run validation (write-back)
python -m aijobscanner validate-sources --write-back

# Validate single source
python -m aijobscanner validate-sources --only tg_vankar1

# Check architecture decisions
ls ADR/

# Check security rules
cat security/telegram_session_rules.md

# View access strategy
cat docs/telegram_access.md

# View validation runbook
cat docs/runbooks/telegram_validation.md
```

### Key Files

| File | Purpose |
|------|---------|
| `project_track.md` | **Primary tracking document** - Read this first |
| `studio/STATE.md` | This file - Quick state reference |
| `config/telegram_sources.yaml` | Source registry |
| `ADR/001-telegram-ingestion-choice.md` | Architecture decision |
| `docs/telegram_access.md` | Access strategy |
| `security/telegram_session_rules.md` | Security rules |

### Important Links

**Documentation**:
- Telegram Bot API: https://core.telegram.org/bots/api
- Bot Privacy Mode: https://core.telegram.org/bots/features#privacy-mode
- MTProto: https://core.telegram.org/mtproto
- Telethon (Python): https://docs.telethon.dev/
- GramJS (Node.js): https://gram.js.org/

**Internal**:
- Access Strategy: [docs/telegram_access.md](../docs/telegram_access.md)
- ADR-001: [ADR/001-telegram-ingestion-choice.md](../ADR/001-telegram-ingestion-choice.md)
- Security: [security/telegram_session_rules.md](../security/telegram_session_rules.md)

---

## Resume Workflow

If you're returning to work on this project:

1. **Read current state**: `cat studio/STATE.md` (this file)
2. **Read detailed status**: `cat project_track.md`
3. **Check what's next**: Look at "Next 3 Steps" section above
4. **Review relevant docs**: Read ADRs and security rules before coding
5. **Update tracking**: Always update `project_track.md` when completing work

---

## Project Vision

**Goal**: Monitor Telegram job sources, classify AI-suitable tasks, notify user with matches

**Architecture**:
```
Telegram Sources → MTProto Ingestion → Classification → Bot API Notification → User
```

**Unique Value**:
- Automated monitoring of Persian job channels in Canada
- AI/automation suitability classification
- Filtering for remote-friendly opportunities
- Proactive notifications to user

**Current Status**: Foundation phase complete, validation system implemented, ready for message ingestion

---

**End of STATE.md**
**Next update**: After completing Phase 0 Step 2
