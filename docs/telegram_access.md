# Telegram Access Strategy

**Version**: 1.0
**Last Updated**: 2026-01-28
**Status**: Accepted (see ADR-001)

---

## Overview

This document describes the AI Job Scanner's strategy for accessing Telegram sources (groups and channels) to monitor job postings. We use a **two-lane architecture** that separates ingestion (reading messages) from notification (alerting the user).

---

## Unified Source Model

### Core Principle
**Groups and channels are treated identically by the system after ingestion.**

Both source types are normalized into a single internal `PostEvent` format:
```typescript
interface PostEvent {
  source_id: string;
  source_type: 'group' | 'channel';
  message_id: number;
  timestamp: Date;
  author: string;          // Username or display name
  content: string;         // Message text
  media_urls?: string[];   // Attached images/documents
  reactions?: Reaction[];  // Emoji reactions
  is_bot_post: boolean;    // Whether posted by a bot
}
```

### Why Unify?
- **Simplified pipeline**: Single code path for processing all messages
- **Easier classification**: Job suitability analysis works on normalized format
- **Flexibility**: Easy to add new source types in the future
- **Maintainability**: Fewer edge cases to handle

### External Differences Only
The **only** difference between groups and channels is in the **join/subscribe mechanics**:

| Aspect | Group | Channel |
|--------|-------|---------|
| **How to access** | Join via invite link | Subscribe/follow via public handle |
| **Who can post** | All participants | Channel admins only |
| **Message visibility** | See all messages from all members | See posts from admins |
| **Join approval** | May require admin approval | None (public channels) |
| **After ingestion** | **IDENTICAL** - normalized to PostEvent | **IDENTICAL** - normalized to PostEvent |

---

## Two-Lane Access Model

We use **two separate mechanisms** for accessing Telegram:

### Lane A: MTProto User Client (Ingestion)

**Purpose**: Read messages from monitored sources

**Technology**: MTProto user client library
- Python: [Telethon](https://docs.telethon.dev/)
- Node.js: [GramJS](https://gram.js.org/)

**How it works**:
1. User account authenticates with phone number + 2FA
2. Session file stores authentication credentials
3. Client connects to Telegram servers via MTProto
4. User joins groups and subscribes to channels
5. Client reads all messages from joined sources
6. Messages are normalized to PostEvent format
7. Posts are processed for job classification

**Why MTProto user client?**
- **Full visibility**: Sees all messages, including from other bots
- **No bot limitations**: Bypasses privacy mode restrictions
- **Group access**: Can join groups that don't allow bots
- **Reliability**: Message delivery guaranteed when connected

**Evidence**: See [Why Bot-Only Ingestion Fails](#why-bot-only-ingestion-fails) below

---

### Lane B: Bot API (Notification)

**Purpose**: Send notifications to the user

**Technology**: Telegram Bot API
- Official bot API: https://core.telegram.org/bots/api
- Libraries: python-telegram-bot, telebot, node-telegram-bot-api, etc.

**How it works**:
1. Bot is created via @BotFather
2. User starts a private chat with the bot (DM)
3. Bot sends job alerts directly to user's DM
4. Bot does **NOT** need to be in monitored sources
5. User can configure alert preferences via bot commands

**Why Bot API for notifications?**
- **Purpose-built**: Designed for sending messages to users
- **Efficient**: Lightweight, no need for user session
- **Rich formatting**: Supports Markdown, HTML, inline keyboards
- **No privacy concerns**: Bot only talks to user, not monitoring sources
- **Separation of concerns**: Monitoring and notification are independent

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         TELEGRAM                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐         ┌──────────────┐                      │
│  │   Group      │         │   Channel    │                      │
│  │  (Members)   │         │  (Admins)    │                      │
│  └──────┬───────┘         └──────┬───────┘                      │
│         │                        │                              │
│         └────────────┬───────────┘                              │
│                      │                                           │
│                      ▼                                           │
│         ┌─────────────────────────┐                             │
│         │   MTProto User Client   │◄──── User Account            │
│         │   (Telethon/GramJS)     │     (Authentication)         │
│         └────────────┬────────────┘                             │
│                      │                                           │
│                      │ PostEvent Stream                          │
└──────────────────────┼───────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AI JOB SCANNER                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Message Processing Pipeline                  │   │
│  │  1. Normalize to PostEvent                                │   │
│  │  2. Extract job details                                   │   │
│  │  3. Classify AI suitability                               │   │
│  │  4. Filter by user preferences                            │   │
│  └───────────────────────────┬──────────────────────────────┘   │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Match Found?                                 │   │
│  └───────────────────────────┬──────────────────────────────┘   │
│                              │                                    │
│              ┌───────────────┴───────────────┐                  │
│              │                               │                   │
│              ▼                               ▼                   │
│         ┌─────────┐                    ┌─────────┐              │
│         │   YES   │                    │   NO    │              │
│         └────┬────┘                    └────┬────┘              │
│              │                               │                   │
└──────────────┼───────────────────────────────┼───────────────────┘
               │                               │
               ▼                               │
┌──────────────────────────────┐               │
│   Telegram Bot API           │               │
│   (Notification Lane)        │               │
│   ┌──────────────────┐       │               │
│   │ Send DM to User  │       │               │
│   │ with job details │       │               │
│   └──────────────────┘       │               │
└──────────────────────────────┘               │
               │                               │
               ▼                               ▼
         ┌─────────┐                    ┌─────────┐
         │ NOTIFY  │                    │ DISCARD │
         └─────────┘                    └─────────┘
```

---

## Source Types and Join Mechanics

### Groups

**What is a group?**
- A chat where **all members can post messages**
- Can be public or private
- May require admin approval to join

**How to access**:
1. User must have an invite link (e.g., `https://t.me/+HBKt5e9nhxVjMzgx`)
2. MTProto user client sends join request via invite link
3. Group admins may need to approve the request
4. Once joined, user receives **all messages from all participants**
5. User can leave the group at any time

**Characteristics**:
- Multiple participants contribute job postings
- More conversational (replies, discussions)
- May have spam or off-topic messages
- Harder to filter (need to identify actual job posts)

**Our current group**:
- `tg_invite_HBKt5e9nhxVjMzgx` - Canada Jobs Group
- Invite link: https://t.me/+HBKt5e9nhxVjMzgx
- Language: Persian (Farsi)
- Validation status: Unverified (not yet joined)

---

### Channels

**What is a channel?**
- A one-way broadcast where **only admins can post**
- Can be public (with username) or private (invite-only)
- Unlimited number of subscribers

**How to access**:
1. For public channels: Subscribe via username (e.g., `@vankar1`)
2. For private channels: Need invite link
3. No approval required for public channels
4. Once subscribed, user receives **posts from channel admins only**
5. User can unsubscribe at any time

**Characteristics**:
- Curated content (only admins post)
- Usually cleaner, more focused on job listings
- Easier to filter (most posts are relevant)
- May have media (images, documents) with job details

**Our current channels**:
1. `tg_vankar1` - Vankar Jobs (https://t.me/vankar1)
2. `tg_karyabi_canada` - Karyabi Canada (https://t.me/karyabi_canada)
3. `tg_joyakar_vancouver` - JoyaKar Vancouver (https://t.me/JoyaKarVancouver)
4. `tg_jobcanadaaa` - Job Canada (https://t.me/jobcanadaaa)
- Language: Persian (Farsi)
- Validation status: Unverified (not yet subscribed)

---

## Why Bot-Only Ingestion Fails

### Evidence-Based Limitations

Using **only a bot** for message ingestion (reading from sources) has **critical limitations** that make it unsuitable for our use case:

---

### Limitation 1: Bot Privacy Mode in Groups

**Problem**: In groups, bots operate under "privacy mode" by default.

**What this means**:
- Bots **cannot see messages from other users** in a group
- Bots **only receive messages** that:
  - Explicitly mention the bot (e.g., `/command@botname`)
  - Are sent directly to the bot in a private chat
  - Are sent by the bot itself

**Official documentation**:
> "When a bot is added to a group, it can't see messages sent by other users... The bot will only receive messages that are sent directly to it or that mention it."
> — [Telegram Bot API - Privacy Mode](https://core.telegram.org/bots/features#privacy-mode)

**Impact on job monitoring**:
- Bot would miss **99%+ of job postings** in groups
- Only see messages that explicitly tag the bot (unlikely)
- Makes group monitoring **functionally impossible**

**Workaround?** Group admins can disable privacy mode for the bot, but:
- Requires admin cooperation
- Not guaranteed (admins may refuse)
- Not scalable (need to ask every group owner)
- Defeats the purpose of automated monitoring

---

### Limitation 2: Bot-to-Bot Visibility

**Problem**: Bots **cannot see messages from other bots**.

**What this means**:
- Many channels use **bots to automatically post job listings**
- Our monitoring bot would be **blind to these bot-posted jobs**

**Official documentation**:
> "Bots ignore messages from other bots... A bot will not receive updates from messages sent by other bots."
> — [Telegram Bot API - Privacy Mode](https://core.telegram.org/bots#privacy-mode)

**Impact on job monitoring**:
- Miss automated job postings (which are common)
- Cross-posting bots would be invisible
- Creates **blind spots** in monitoring

**Example**:
- Channel `@jobcanadaaa` might use a bot to auto-post from a database
- Our bot would **never see these posts**
- Critical jobs would be missed

---

### Limitation 3: Bot Must Be Member to Receive Updates

**Problem**: Bots only receive messages from sources where they are a member.

**What this means**:
- Bot must be added to groups (requires admin approval)
- Bot must subscribe to channels
- Bot can be removed at any time by source owners

**Official documentation**:
> "A bot will only receive updates from chats where it is a member... If the bot is removed from a group, it will stop receiving updates."
> — [Telegram Bot API - Getting Updates](https://core.telegram.org/bots/api#getting-updates)

**Impact on job monitoring**:
- **Dependence on source owners**: Need permission to add bot
- **Fragility**: Bot can be removed without notice
- **Limited scalability**: Need to ask each source owner
- **No control**: Can't join without permission

**Our scenario**:
- Persian job channels may not accept English-language bots
- Source owners might be suspicious of monitoring bots
- No guarantee of access

---

### Limitation 4: Group Membership Restrictions

**Problem**: Some groups **do not allow bots at all**.

**What this means**:
- Group admins can configure "No bots allowed"
- Bot cannot join, regardless of permissions
- Entire source becomes inaccessible

**Impact on job monitoring**:
- **Hard constraint**: If bot can't join, source can't be monitored
- No workaround (except using a user account)
- Limits source coverage

---

### Conclusion: Bot-Only Ingestion is Not Viable

**Summary of limitations**:
1. ❌ Privacy mode blocks most messages in groups
2. ❌ Cannot see bot-posted messages (bot-to-bot blindness)
3. ❌ Requires permission from each source owner
4. ❌ Can be removed at any time
5. ❌ Some groups don't allow bots at all

**Result**: Using a bot-only approach would make reliable job monitoring **impossible** for our use case.

**Solution**: Use an **MTProto user client** for ingestion (see ADR-001).

---

## Hard Constraint: Join to Monitor

### The Rule

> **If the monitoring user account cannot join a source, that source cannot be monitored.**

There is **no technical workaround** for this limitation. Telegram's architecture requires membership to receive messages from a source.

---

### What This Means

**For Groups**:
- Must successfully join via invite link
- Admin approval may be required
- If join is rejected, source is inaccessible

**For Channels**:
- Must subscribe (follow) the channel
- Public channels: Always accessible
- Private channels: Need invite link

---

### If You Can't Join: Workarounds

If a source cannot be joined directly, consider these alternatives:

#### Option 1: Ask Source Owner for Permission
- Contact group/channel admin
- Explain your legitimate use case (job monitoring)
- Request to add your monitoring account
- **Risk**: May be refused or ignored

#### Option 2: Find a Public Mirror
- Some groups have public channels that repost content
- Search for related channels with same content
- **Risk**: May not exist or may be incomplete

#### Option 3: Forward-to-Owned-Channel Strategy
- Ask source owner to forward posts to your own channel
- You own the channel, so guaranteed access
- **Risk**: Requires source owner cooperation

#### Option 4: Use Alternative Sources
- Find other sources covering similar content
- Focus on sources that allow access
- **Risk**: May miss unique content from inaccessible source

---

### Documentation Requirements

When a source cannot be accessed:
1. Document the reason in `config/telegram_sources.yaml` (notes field)
2. Set `validation_status: join_failed`
3. Set `enabled: false`
4. Record attempted workaround in project notes
5. Consider re-attempting join later (policies change)

---

## Operational Notes

### Dedicated Monitoring Account

**Requirement**: Use a **dedicated Telegram account** for monitoring, not your personal account.

**Why?**
- **Isolation**: If monitoring account is compromised, personal account is safe
- **Professionalism**: Separate identity for automated monitoring
- **Recovery**: Easier to recover if blocked by Telegram
- **Testing**: Can test features without affecting personal use

**Best practices**:
- Create new Telegram account specifically for this project
- Use professional username (e.g., `@ai_job_scanner_bot`)
- Use a phone number that can be dedicated to this purpose
- Keep credentials secure and encrypted

---

### Encrypted Session Storage

**Requirement**: MTProto session files must be **encrypted at rest**.

**Why?**
- Session files contain authentication credentials
- If stolen, attacker can impersonate your account
- Protects account from unauthorized access

**Implementation**:
1. Never commit session files to git (add to `.gitignore`)
2. Encrypt session files using AES-256 or similar
3. Store encryption key in environment variable (not in code)
4. Rotate encryption keys periodically
5. Decrypt session in memory only when needed

**Example approach**:
```python
# Pseudocode for session encryption
def save_session(session_data, key):
    encrypted = encrypt(session_data, key)
    write_file("session.session.enc", encrypted)

def load_session(key):
    encrypted = read_file("session.session.enc")
    return decrypt(encrypted, key)

# Get key from environment
key = os.environ["SESSION_ENCRYPTION_KEY"]
session = load_session(key)
```

---

### Rate Limit Awareness

**Problem**: Telegram has rate limits on MTProto operations.

**What this means**:
- Cannot read all sources instantly
- Must throttle requests to avoid being blocked
- High-priority sources should be checked more frequently

**Telegram's limits** (approximate):
- Messages per second: ~30 (varies by account)
- Join requests per minute: ~5-10
- Channel views per minute: ~50

**Our strategy**:
1. Implement priority-based scheduling
2. High-priority sources: Check every 5-10 minutes
3. Medium-priority: Check every 30-60 minutes
4. Low-priority: Check every 2-4 hours
5. Spread requests evenly over time
6. Implement exponential backoff on errors

**Future enhancement**: In Phase 1+, we'll implement a smart scheduler that:
- Learns posting patterns of each source
- Dynamically adjusts check frequency
- Prioritizes sources with more job postings
- Respects rate limits automatically

---

### Behave Like a Normal User

**Principle**: Avoid triggering Telegram's anti-abuse systems.

**Do's**:
- ✅ Read messages at a human-like pace
- ✅ Take breaks (don't run 24/7 initially)
- ✅ Vary check intervals (add randomness)
- ✅ Limit concurrent operations
- ✅ Respect source rules and guidelines

**Don'ts**:
- ❌ Read thousands of messages per second
- ❌ Join/leave sources rapidly
- ❌ Send automated messages (unless authorized)
- ❌ Scrape or download media aggressively
- ❌ Violate Telegram's Terms of Service

**Goal**: Fly under the radar. We're monitoring, not spamming.

---

## References

### Official Telegram Documentation
- **Bot API**: https://core.telegram.org/bots/api
- **Bot Privacy Mode**: https://core.telegram.org/bots/features#privacy-mode
- **MTProto Protocol**: https://core.telegram.org/mtproto
- **Telegram API Rate Limits**: https://core.telegram.org/api/limits
- **Bot API - Privacy Mode**: https://core.telegram.org/bots#privacy-mode
- **Getting Updates**: https://core.telegram.org/bots/api#getting-updates

### Client Libraries
- **Telethon (Python)**: https://docs.telethon.dev/
- **GramJS (Node.js)**: https://gram.js.org/
- **TDLib (C/C++)**: https://core.telegram.org/tdlib

### Architecture Decision Records
- **ADR-001**: Telegram Ingestion Choice - [Why we chose MTProto user client](../ADR/001-telegram-ingestion-choice.md)

### Configuration Files
- **Telegram Sources Registry**: [config/telegram_sources.yaml](../config/telegram_sources.yaml)

---

## Summary

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Ingestion method** | MTProto user client | Bots have visibility limitations (privacy mode, bot-to-bot) |
| **Notification method** | Bot API | Efficient for sending DMs to user |
| **Source model** | Unified (groups + channels) | Simplifies processing, single pipeline |
| **Authentication** | Dedicated user account | Isolation from personal account |
| **Session storage** | Encrypted at rest | Security best practice |
| **Rate limiting** | Priority-based scheduling | Avoid Telegram anti-abuse |
| **Access constraint** | Must join to monitor | Hard limit, no technical workaround |

---

**Document status**: Accepted
**Next review**: After Phase 0 Step 4 (proof-of-concept ingestion)
**Maintainer**: AI Job Scanner project
