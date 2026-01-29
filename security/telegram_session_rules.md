# Telegram Session Security Rules

**Version**: 1.0
**Last Updated**: 2026-01-28
**Applies to**: Phase 0+ - All development and production usage

---

## Overview

This document defines security rules for managing Telegram user sessions in the AI Job Scanner project. Sessions contain authentication credentials that must be protected from unauthorized access.

**Threat Model**: Session theft, account compromise, data over-collection, retention risks

**Security Posture**: Defense in depth - multiple layers of protection

---

## Threat Analysis

### Threat 1: Session File Theft

**Description**: Attacker gains access to the session file, allowing them to impersonate the monitoring account.

**Impact**:
- HIGH - Attacker can read all messages from monitored sources
- HIGH - Attacker can post messages as the monitoring account
- MEDIUM - Attacker can access private groups/channels
- MEDIUM - Attacker can damage reputation of monitoring account

**Attack Vectors**:
- Unauthorized access to filesystem
- Compromised backup/storage
- Accidental commit to version control
- Malware on development machine
- Insufficient file permissions

---

### Threat 2: Account Compromise

**Description**: Attacker gains access to the Telegram account credentials (phone number, 2FA code).

**Impact**:
- CRITICAL - Full account takeover
- CRITICAL - Attacker can reset 2FA and lock out owner
- HIGH - Access to all private communications
- HIGH - Can add/remove monitoring from sources

**Attack Vectors**:
- Phishing attacks
- Credential reuse from compromised sites
- Social engineering
- Brute force on weak 2FA passwords

---

### Threat 3: Data Over-Collection

**Description**: Collecting more data than necessary, increasing privacy and legal risks.

**Impact**:
- MEDIUM - Privacy violations
- MEDIUM - Legal liability (GDPR, PIPEDA, etc.)
- LOW - Increased storage costs
- LOW - Processing overhead

**Causes**:
- Collecting entire message history
- Storing personal information from group members
- Retaining data indefinitely
- Collecting messages unrelated to job postings

---

### Threat 4: Unauthorized Source Access

**Description**: Monitoring sources without proper authorization.

**Impact**:
- MEDIUM - Terms of Service violation
- MEDIUM - Legal liability
- LOW - Reputation damage
- LOW - Account suspension

**Causes**:
- Joining private groups without permission
- Scraping private channels
- Ignoring group rules or guidelines

---

## Security Controls

### Control 1: Dedicated Monitoring Account

**Rule**: **Use a dedicated Telegram account for monitoring.**

**Requirements**:
- Separate from personal account
- Separate phone number
- Professional username
- Unique, strong password
- Unique 2FA code

**Rationale**:
- Isolates risk from personal account
- Easier to recover if compromised
- Cleaner audit trail
- Professional appearance

**Implementation**:
```
Account: @ai_job_scanner_bot (example)
Phone: Dedicated number (not personal number)
Email: Dedicated email address
Password: Unique, 20+ characters, random
2FA: Unique password, not reused anywhere
```

---

### Control 2: Encrypted Session Files

**Rule**: **Session files MUST be encrypted at rest.**

**Requirements**:
- Encrypt session files using AES-256 or equivalent
- Store encryption key in environment variable (not in code)
- Never commit session files to version control
- Never share session files
- Rotate encryption keys periodically

**Rationale**:
- Session files contain authentication credentials
- If stolen, attacker can impersonate account
- Encryption provides defense in depth

**Implementation Example**:

```python
# Python pseudocode
import os
from cryptography.fernet import Fernet

def save_session(session_data):
    """Encrypt and save session data"""
    key = os.environ["SESSION_ENCRYPTION_KEY"]
    fernet = Fernet(key)
    encrypted = fernet.encrypt(session_data)
    with open("session.session.enc", "wb") as f:
        f.write(encrypted)

def load_session():
    """Load and decrypt session data"""
    key = os.environ["SESSION_ENCRYPTION_KEY"]
    fernet = Fernet(key)
    with open("session.session.enc", "rb") as f:
        encrypted = f.read()
    return fernet.decrypt(encrypted)
```

**Key Management**:
- Generate strong encryption key (32+ bytes)
- Store key in environment variable
- Never hardcode in source code
- Use different keys for dev/staging/prod
- Rotate keys every 90 days

**File Permissions**:
- Session files: `0600` (read/write for owner only)
- Encryption key: Environment variable only
- No group or world read permissions

---

### Control 3: Version Control Exclusions

**Rule**: **Never commit session files or credentials to git.**

**Requirements**:
- Add session files to `.gitignore`
- Add encryption key files to `.gitignore`
- Use `git-secrets` or similar to prevent accidental commits
- Scan repository for accidentally committed secrets

**.gitignore entries**:
```gitignore
# Session files
*.session
*.session.enc
*.session-journal

# Encryption keys
*.key
.env
secrets/
credentials/

# Telethon/GramJS specific
telethon.session
gramjs.session
```

**Prevention tools**:
```bash
# Install git-secrets
brew install git-secrets  # macOS
# or
apt-get install git-secrets  # Linux

# Configure to block common secrets
git secrets --install
git secrets --register-aws
git secrets --add 'api_key\s*=\s*["\'].*["\'"]'
git secrets --add 'password\s*=\s*["\'].*["\'"]'
git secrets --add 'session.*encryption.*key'
```

**If secrets are accidentally committed**:
1. Immediately remove from repository
2. Rotate all exposed credentials
3. Force remove from git history: `git filter-branch` or BFG Repo-Cleaner
4. Notify all stakeholders
5. Document incident in security log

---

### Control 4: Minimal Data Retention

**Rule**: **Only retain data necessary for job classification.**

**Requirements**:
- Only store job-related messages
- Delete messages after classification (or within 7 days)
- Do not store personal information from group members
- Do not store message history indefinitely
- Implement automatic cleanup

**Data retention policy**:

| Data Type | Retention Period | Reason |
|-----------|------------------|---------|
| Job postings | 7 days after classification | Time to process and notify |
| Non-job messages | Immediate deletion | Not needed |
| User personal info | Never stored | Privacy compliance |
| Source metadata | Until source removed | Operational need |
| Audit logs | 90 days | Security monitoring |
| Session files | Until rotated or revoked | Authentication |

**Implementation**:
```python
# Pseudocode for automatic cleanup
def cleanup_old_messages():
    """Delete messages older than retention period"""
    cutoff_date = datetime.now() - timedelta(days=7)
    old_messages = db.messages.filter(
        timestamp__lt=cutoff_date,
        processed=True
    )
    old_messages.delete()
```

---

### Control 5: Authorized Source Access Only

**Rule**: **Only monitor sources where the monitoring account is a legitimate member.**

**Requirements**:
- Only join groups where membership is authorized
- Only subscribe to public channels
- Do not bypass access restrictions
- Respect source rules and guidelines
- Leave sources if requested by owner

**Authorization criteria**:
- ✅ Public channels (anyone can subscribe)
- ✅ Groups with invite links (publicly accessible)
- ✅ Groups where owner has given explicit permission
- ❌ Private channels without invite
- ❌ Groups with restricted membership
- ❌ Sources that require hacking/circumvention

**If access is denied**:
1. Document the reason in source registry
2. Set `validation_status: join_failed`
3. Set `enabled: false`
4. Do not attempt to bypass restrictions
5. Consider asking source owner for permission

**Statement of authorization**:
> "The AI Job Scanner only monitors Telegram sources where the monitoring user account is a legitimate member or subscriber. We do not attempt to access private or restricted sources without proper authorization. We respect all source rules and community guidelines."

---

### Control 6: Credential Storage Best Practices

**Rule**: **Store credentials securely using industry-standard practices.**

**Requirements**:
- Never hardcode credentials in source code
- Use environment variables for secrets
- Use a secrets manager for production (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate credentials periodically
- Use strong, unique passwords

**Environment variables**:
```bash
# Required environment variables
SESSION_ENCRYPTION_KEY=<encryption_key>
TELEGRAM_API_ID=<api_id>
TELEGRAM_API_HASH=<api_hash>
TELEGRAM_PHONE_NUMBER=<phone_number>
TELEGRAM_2FA_PASSWORD=<2fa_password>
NOTIFICATION_BOT_TOKEN=<bot_token>
```

**Example .env file** (never commit):
```env
SESSION_ENCRYPTION_KEY=your_base64_encoded_encryption_key_here
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE_NUMBER=+1234567890
TELEGRAM_2FA_PASSWORD=your_strong_unique_2fa_password
NOTIFICATION_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

**Password requirements**:
- Minimum 20 characters
- Mix of uppercase, lowercase, numbers, symbols
- Unique (not reused from other sites)
- Randomly generated (not dictionary words)
- Stored in password manager

---

### Control 7: Audit and Monitoring

**Rule**: **Maintain audit logs and monitor for security incidents.**

**Requirements**:
- Log all join/leave actions
- Log all message access
- Monitor for unusual activity
- Regular security audits
- Incident response plan

**Audit log entries**:
- Source joins and departures (timestamp, source_id)
- Message ingestion statistics (count per source per day)
- Failed authentication attempts
- Unusual activity spikes
- Configuration changes

**Monitoring alerts**:
- Session file access failures
- Unusual message volume
- Failed login attempts
- Account suspension by Telegram
- New sources added without approval

**Audit frequency**:
- Daily: Automated checks for unusual activity
- Weekly: Review access logs
- Monthly: Full security audit
- Quarterly: Rotate encryption keys and credentials

---

## Security Do's and Don'ts

### ✅ DO

- ✅ Use a dedicated Telegram account for monitoring
- ✅ Encrypt session files at rest
- ✅ Store credentials in environment variables
- ✅ Use strong, unique passwords for 2FA
- ✅ Add session files to `.gitignore`
- ✅ Implement automatic data cleanup
- ✅ Monitor for security incidents
- ✅ Respect source rules and guidelines
- ✅ Leave sources if requested by owner
- ✅ Keep libraries up to date
- ✅ Use different credentials for dev/staging/prod
- ✅ Document all security procedures

### ❌ DO NOT

- ❌ Use your personal Telegram account
- ❌ Commit session files to git
- ❌ Hardcode credentials in source code
- ❌ Share session files or credentials
- ❌ Store messages indefinitely
- ❌ Collect personal information from group members
- ❌ Join private sources without permission
- ❌ Bypass access restrictions
- ❌ Ignore source rules
- ❌ Use weak or reused passwords
- ❌ Expose encryption keys in logs
- ❌ Disable 2FA on monitoring account

---

## Incident Response Plan

### Incident Type 1: Session File Compromise

**Detection**:
- Unauthorized file access detected
- Session file found in unexpected location
- Session file accidentally committed to git

**Response Steps**:
1. **IMMEDIATE**: Terminate MTProto client connection
2. **IMMEDIATE**: Revoke all active sessions in Telegram settings
3. **IMMEDIATE**: Change 2FA password on monitoring account
4. **IMMEDIATE**: Rotate session encryption key
5. **WITHIN 1 HOUR**: Regenerate session file with new credentials
6. **WITHIN 24 HOURS**: Review audit logs for unauthorized access
7. **WITHIN 24 HOURS**: Document incident and lessons learned
8. **WITHIN 7 DAYS**: Implement additional preventive measures

---

### Incident Type 2: Account Compromise

**Detection**:
- Unusual messages sent from account
- Account suspended by Telegram
- Password changed without authorization
- 2FA password no longer works

**Response Steps**:
1. **IMMEDIATE**: Contact Telegram support
2. **IMMEDIATE**: Attempt account recovery via phone number
3. **IMMEDIATE**: Notify all stakeholders
4. **WITHIN 1 HOUR**: Change phone number password (carrier)
5. **WITHIN 24 HOURS**: Secure or recreate monitoring account
6. **WITHIN 24 HOURS**: Review all source memberships
7. **WITHIN 7 DAYS**: Migrate to new monitoring account if needed
8. **WITHIN 30 DAYS**: Conduct full security review

---

### Incident Type 3: Data Breach

**Detection**:
- Evidence of unauthorized data access
- Data found in unexpected locations
- Logs show unusual access patterns

**Response Steps**:
1. **IMMEDIATE**: Secure affected systems
2. **IMMEDIATE**: Identify scope of breach
3. **WITHIN 1 HOUR**: Notify affected parties if required
4. **WITHIN 24 HOURS**: Document incident details
5. **WITHIN 7 DAYS**: Implement remediation measures
6. **WITHIN 30 DAYS**: Review and update security policies

---

## Compliance and Legal Considerations

### Data Protection Laws

**Canada**:
- **PIPEDA** (Personal Information Protection and Electronic Documents Act)
- Must obtain consent for collecting personal information
- Must protect personal information with appropriate safeguards
- Must retain data only as long as necessary

**European Union**:
- **GDPR** (General Data Protection Regulation)
- Right to be forgotten (delete data on request)
- Data minimization (only collect what's necessary)
- Privacy by design and by default

**Best Practices**:
- Assume global jurisdiction (comply with strictest laws)
- Minimize data collection
- Implement privacy by design
- Provide data deletion on request
- Document data processing activities

---

### Telegram Terms of Service

**Key provisions**:
- Do not violate user privacy
- Do not collect data without authorization
- Do not bypass access restrictions
- Do not spam or send unsolicited messages
- Do not use automated tools to abuse the platform

**Our compliance**:
- ✅ We only join sources where account is legitimate member
- ✅ We do not scrape or download media aggressively
- ✅ We respect rate limits
- ✅ We do not send unsolicited messages (only DM user on their request)
- ✅ We follow community guidelines

---

## Security Checklist

### Before First Run
- [ ] Created dedicated monitoring account
- [ ] Set strong, unique 2FA password
- [ ] Generated session encryption key
- [ ] Added session files to `.gitignore`
- [ ] Set up environment variables
- [ ] Tested session encryption/decryption
- [ ] Reviewed source authorization for all sources
- [ ] Documented security procedures

### Regular Maintenance
- [ ] Monthly: Review audit logs
- [ ] Monthly: Update dependencies
- [ ] Quarterly: Rotate encryption keys
- [ ] Quarterly: Review and update security policies
- [ ] Annually: Full security audit

### After Security Incident
- [ ] Documented incident details
- [ ] Identified root cause
- [ ] Implemented remediation
- [ ] Updated procedures
- [ ] Notified stakeholders
- [ ] Tested preventive measures

---

## References

### External Resources
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [OWASP Key Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)
- [Telegram Security Guidelines](https://telegram.org/privacy)
- [PIPEDA Compliance Guide](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/)
- [GDPR Compliance Guide](https://gdpr.eu/)

### Internal Documentation
- [Telegram Access Strategy](../docs/telegram_access.md)
- [ADR-001: Telegram Ingestion Choice](../ADR/001-telegram-ingestion-choice.md)
- [Project Track](../project_track.md)

---

## Summary

**Security is not optional.** The AI Job Scanner handles authentication credentials and processes potentially sensitive data. Following these rules is **mandatory** for all development and production usage.

**Key principles**:
1. Dedicated account (isolate risk)
2. Encrypted sessions (protect credentials)
3. Minimal retention (reduce exposure)
4. Authorized access only (legal compliance)
5. Audit everything (detect incidents)

**Remember**: Security is everyone's responsibility. If you see something suspicious, report it immediately. If you're unsure about something, ask before proceeding.

---

**Document status**: Active
**Next review**: 2026-04-28 (quarterly)
**Maintainer**: AI Job Scanner project
