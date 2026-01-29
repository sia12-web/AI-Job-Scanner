# ADR-001: Telegram Ingestion Architecture Choice

**Status**: Accepted
**Date**: 2026-01-28
**Context**: Phase 0, Step 1 - AI Job Scanner Foundation

---

## Context

The AI Job Scanner needs to monitor Telegram sources (groups and channels) that post job listings, classify which tasks can be done remotely by AI/automation, and notify the user with relevant details.

**Key Requirements**:
1. Read messages from both groups and channels
2. See all messages, including from bots
3. Reliable message delivery (no blind spots)
4. Efficient notification delivery to user
5. Comply with Telegram's Terms of Service

**Constraints**:
- Some sources may not allow bots
- Bots have privacy mode limitations
- Must maintain session security
- Must respect rate limits

---

## Decision

We will use a **two-lane architecture**:

### Lane A: MTProto User Client for Ingestion
- **Technology**: Telethon (Python) or GramJS (Node.js)
- **Purpose**: Read messages from monitored sources
- **Authentication**: User account (phone number + 2FA)
- **Session**: Encrypted session file storage

### Lane B: Bot API for Notifications
- **Technology**: Telegram Bot API
- **Purpose**: Send job alerts to user via DM
- **Authentication**: Bot token from @BotFather
- **Session**: Stateless (no session storage needed)

---

## Rationale

### Why MTProto User Client for Ingestion?

**1. Bypass Bot Privacy Mode Limitations**
- Bots in groups cannot see messages from other users (privacy mode)
- Official docs: "Bots can't see messages sent by other users in groups"
- User clients see all messages, no privacy restrictions

**2. Receive Bot-Posted Messages**
- Bots cannot see messages from other bots (bot-to-bot blindness)
- Many channels use bots to auto-post job listings
- User clients receive all messages, including from bots

**3. Guaranteed Source Access**
- User accounts can join any accessible group or channel
- No dependency on source owner approval for bot access
- Only requirement: User account must be able to join

**4. Reliability**
- Message delivery guaranteed when connected
- No blind spots or missing messages
- Works consistently across all source types

### Why Bot API for Notifications?

**1. Purpose-Built for Notifications**
- Designed specifically for sending messages to users
- Rich formatting support (Markdown, HTML, inline keyboards)
- Efficient and lightweight

**2. Separation of Concerns**
- Monitoring and notification are independent
- Bot doesn't need to be in monitored sources
- Bot only talks to user, not reading from sources

**3. User Control**
- User can start/stop bot easily
- User can configure preferences via bot commands
- No need for user session in notification pipeline

### Why Not Bot-Only Architecture?

**Critical Limitations**:
1. **Privacy mode**: Bot sees <1% of messages in groups
2. **Bot-to-bot blindness**: Can't see bot-posted messages
3. **Access dependency**: Needs permission from each source owner
4. **Fragility**: Can be removed without notice
5. **Source restrictions**: Some groups don't allow bots

**Conclusion**: Bot-only ingestion makes reliable monitoring **impossible** for our use case.

---

## Consequences

### Positive

**Operational Benefits**:
- ✅ Reliable message ingestion from all sources
- ✅ No blind spots or missing messages
- ✅ Independent access control (not dependent on source owners)
- ✅ Works for both groups and channels identically
- ✅ Future-proof (can add more sources without permission)

**Technical Benefits**:
- ✅ Clean separation of concerns (ingestion vs notification)
- ✅ Each lane uses optimal technology for its purpose
- ✅ Easier to test and debug independently
- ✅ Can replace one lane without affecting the other

**Security Benefits**:
- ✅ Dedicated monitoring account isolates risk
- ✅ Bot token has minimal permissions (DM only)
- ✅ Compromise of one lane doesn't compromise both

### Negative

**Complexity**:
- ❌ More complex than bot-only architecture
- ❌ Requires managing two authentication mechanisms
- ❌ More moving parts to maintain

**Operational Overhead**:
- ❌ Need to maintain dedicated user account
- ❌ Session file encryption adds complexity
- ❌ Need to monitor account for blocking/suspension
- ❌ 2FA credentials must be securely stored

**Resource Usage**:
- ❌ User client consumes more resources than bot
- ❌ Need to maintain persistent connection
- ❌ Session files require secure storage

**Mitigation**:
- All negative consequences are acceptable trade-offs
- Complexity is manageable with proper documentation
- Operational overhead is necessary for reliability
- Resource usage is reasonable for the value gained

---

## Alternatives Considered

### Alternative 1: Bot-Only Architecture
**Description**: Use only Telegram Bot API for both ingestion and notification

**Pros**:
- Simpler architecture
- No user account management
- Stateless, no session storage

**Cons**:
- **Privacy mode blocks 99% of group messages**
- **Cannot see bot-posted messages**
- Requires permission from each source owner
- Can be removed without notice
- Some groups don't allow bots

**Verdict**: ❌ Rejected - Functionally impossible for reliable monitoring

**Evidence**:
- [Telegram Bot Privacy Mode](https://core.telegram.org/bots/features#privacy-mode)
- [Bot-to-Bot Limitations](https://core.telegram.org/bots#privacy-mode)

---

### Alternative 2: TDLib-Only Architecture
**Description**: Use Telegram's TDLib for both ingestion and notification

**Pros**:
- Official library from Telegram
- Full feature parity with official clients
- Supports all Telegram features

**Cons**:
- Heavier than Telethon/GramJS
- More complex setup
- Less community support
- Overkill for our use case

**Verdict**: ❌ Rejected - Unnecessary complexity for our needs

---

### Alternative 3: Multiple User Accounts (No Bot)
**Description**: Use only user accounts for both ingestion and notification

**Pros**:
- Maximum visibility in all sources
- No bot limitations

**Cons**:
- Notification would need to send message from user account
- Could be flagged as spam
- No clean separation of concerns
- Account at higher risk

**Verdict**: ❌ Rejected - Notification should use Bot API for efficiency

---

### Alternative 4: Web App + Bot
**Description**: Use Telegram Web App embedded in client for ingestion

**Pros**:
- Modern web technologies
- Rich UI potential

**Cons**:
- Web Apps have limitations
- Still need backend for processing
- More complex than necessary
- Not designed for background monitoring

**Verdict**: ❌ Rejected - Wrong tool for background monitoring

---

## Implementation Plan

### Phase 0: Foundation
- ✅ Document architecture decision (this ADR)
- ✅ Create sources registry
- ✅ Document access strategy
- ✅ Document security rules

### Phase 1: Basic Ingestion
- Implement MTProto user client setup
- Create session management (encrypted)
- Implement message reader for one source
- Normalize messages to PostEvent format
- Test with group source
- Test with channel source

### Phase 2: Notification System
- Create Telegram bot via @BotFather
- Implement Bot API client
- Create notification formatting
- Send test DMs to user
- Implement user preference commands

### Phase 3: Classification
- Implement job classification logic
- Extract job details from messages
- Determine AI/automation suitability
- Filter and prioritize matches

### Phase 4: Integration
- Connect ingestion → classification → notification
- Implement end-to-end pipeline
- Add rate limiting and scheduling
- Deploy and monitor

---

## Technology Stack

### For Ingestion (Lane A)

**Option A: Python + Telethon**
- Pros: Mature library, good documentation, async support
- Cons: Python runtime overhead
- Verdict: **Recommended** - Best balance of features and usability

**Option B: Node.js + GramJS**
- Pros: JavaScript/TypeScript, large ecosystem
- Cons: Less mature than Telethon
- Verdict: Acceptable alternative

**Decision**: To be made in Phase 0 Step 2

### For Notification (Lane B)

**Option A: Python + python-telegram-bot**
- Pros: Async support, well-maintained, comprehensive
- Verdict: **Recommended** if using Python for ingestion

**Option B: Node.js + node-telegram-bot-api**
- Pros: Simple API, widely used
- Verdict: Acceptable if using Node.js for ingestion

**Decision**: Align with ingestion language

---

## Security Considerations

### MTProto User Client (Ingestion)
- **Dedicated account**: Separate from personal account
- **Encrypted session**: Session files encrypted at rest
- **Credential storage**: Phone number and 2FA in secure vault
- **Access control**: Only join authorized sources
- **Audit logs**: Track all joins and message access

### Bot API (Notification)
- **Minimal permissions**: Bot only needs to send DMs
- **Token security**: Bot token stored in environment variable
- **Rate limiting**: Respect Bot API rate limits
- **User control**: User can block bot anytime

### Data Protection
- **Minimal retention**: Only store necessary data
- **Encryption**: Sensitive data encrypted at rest
- **Access logs**: Audit all data access
- **Compliance**: Follow data protection best practices

See `security/telegram_session_rules.md` for full security guidelines.

---

## Monitoring and Maintenance

### Health Checks
- Monitor MTProto connection status
- Track message ingestion rates
- Verify Bot API delivery status
- Alert on connection failures

### Session Management
- Rotate session encryption keys periodically
- Backup session files securely
- Monitor account for unusual activity
- Have recovery plan for blocked accounts

### Rate Limit Compliance
- Implement exponential backoff on errors
- Prioritize high-value sources
- Spread requests over time
- Monitor Telegram's response headers

### Updates and Upgrades
- Keep libraries up to date
- Monitor Telegram API changes
- Test updates in staging environment
- Have rollback plan for breaking changes

---

## Compliance and Ethics

### Telegram Terms of Service
- ✅ We only monitor sources where user account is legitimate member
- ✅ We do not scrape or download media aggressively
- ✅ We respect rate limits and behave like normal users
- ✅ We do not spam or send unsolicited messages
- ✅ We do not bypass security measures or restrictions

### Data Minimization
- ✅ We only collect data necessary for job classification
- ✅ We do not store full message history indefinitely
- ✅ We do not collect data about non-job messages
- ✅ We allow users to delete their data

### Transparency
- ✅ We document our architecture and methods
- ✅ We provide security rules and guidelines
- ✅ We are transparent about limitations and constraints
- ✅ We welcome security audits

---

## References

### Official Documentation
- [Telegram Bot API - Privacy Mode](https://core.telegram.org/bots/features#privacy-mode)
- [Bot API - Privacy Mode Details](https://core.telegram.org/bots#privacy-mode)
- [MTProto Protocol](https://core.telegram.org/mtproto)
- [Getting Updates](https://core.telegram.org/bots/api#getting-updates)
- [Telegram API Rate Limits](https://core.telegram.org/api/limits)

### Libraries
- [Telethon (Python)](https://docs.telethon.dev/)
- [GramJS (Node.js)](https://gram.js.org/)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [node-telegram-bot-api](https://github.com/yagop/node-telegram-bot-api)

### Internal Documentation
- [Telegram Access Strategy](../docs/telegram_access.md)
- [Telegram Sources Registry](../config/telegram_sources.yaml)
- [Security Rules](../security/telegram_session_rules.md)
- [Project Track](../project_track.md)

---

## Decision Log

| Date | Change | Reason |
|------|--------|--------|
| 2026-01-28 | Initial decision | Phase 0 Step 1 foundation |

---

## Sign-Off

**Decision made by**: AI Job Scanner project team
**Approval date**: 2026-01-28
**Review date**: After Phase 0 Step 4 (proof-of-concept)
**Status**: ✅ **ACCEPTED**

---

**Next Steps**:
1. Phase 0 Step 2: Choose technology stack (Python vs Node.js)
2. Phase 0 Step 3: Implement MTProto authentication
3. Phase 0 Step 4: Proof-of-concept message ingestion

**Success Criteria**:
- Successfully join group source
- Successfully subscribe to channel source
- Receive messages from both source types
- Normalize messages to PostEvent format
- Send notification via Bot API
