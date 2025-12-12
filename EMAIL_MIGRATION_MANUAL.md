# Catalyze Email Migration Manual
## Zoho Domain + SendGrid Integration Guide

**Version:** 1.0  
**Date:** December 11, 2025  
**Application:** Catalyze CRM (Prompt Optimization Platform)  
**Current Stack:** Railway (hosting), PostgreSQL (database), SendGrid (transactional email)

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Zoho Email Domain Setup](#2-zoho-email-domain-setup)
3. [CRM Application Configuration](#3-crm-application-configuration)
4. [SendGrid Integration Guide](#4-sendgrid-integration-guide)
5. [Security Considerations](#5-security-considerations)
6. [Testing & Validation Procedures](#6-testing--validation-procedures)
7. [Troubleshooting Guide](#7-troubleshooting-guide)
8. [Migration Checklist](#8-migration-checklist)

---

## 1. Overview & Architecture

### Current Email Flow
```
User Action → Catalyze App → SendGrid API → Recipient Inbox
                  ↓
            Email Types:
            • Verification emails
            • Password reset
            • Welcome emails
            • Upgrade confirmations
```

### Target Architecture
```
                    ┌─────────────────────────────────────────┐
                    │           ZOHO MAIL DOMAIN              │
                    │  (catalyze.app or your-domain.com)      │
                    │                                         │
                    │  • support@domain.com (team inbox)      │
                    │  • admin@domain.com (admin access)      │
                    │  • noreply@domain.com (SendGrid sender) │
                    └─────────────────────────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │              SENDGRID                    │
                    │  Account Type: Free Tier (100 emails/day)│
                    │  → Upgrade to Essentials for production  │
                    │                                         │
                    │  Sends transactional emails FROM:        │
                    │  noreply@domain.com                      │
                    └─────────────────────────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │         CATALYZE APPLICATION            │
                    │  (auth/email_service.py)                │
                    │                                         │
                    │  Environment Variables:                  │
                    │  • SENDGRID_API_KEY                     │
                    │  • SENDGRID_FROM_EMAIL                  │
                    │  • SENDGRID_FROM_NAME                   │
                    └─────────────────────────────────────────┘
```

### SendGrid Account Specifications

| Attribute | Current/Recommended |
|-----------|---------------------|
| **Account Type** | Free Tier (upgrade to Essentials $19.95/mo for production) |
| **Daily Limit** | 100/day (Free) → 50,000/day (Essentials) |
| **API Version** | v3 (REST API) |
| **SDK** | `sendgrid>=6.10.0` (Python) |
| **Authentication** | API Key (Restricted Access - Mail Send only) |
| **IP Type** | Shared IP (upgrade to Dedicated IP for enterprise) |

---

## 2. Zoho Email Domain Setup

### 2.1 Prerequisites

- [ ] Domain ownership (catalyze.app or your domain)
- [ ] Access to domain DNS settings
- [ ] Zoho Mail account (Free for up to 5 users, or Workplace plan)

### 2.2 Step-by-Step Zoho Setup

#### Step 1: Sign Up for Zoho Mail

1. Go to [zoho.com/mail](https://www.zoho.com/mail/)
2. Click **"Add your existing domain"**
3. Enter your domain: `catalyze.app`
4. Select plan (Free or Workplace)

#### Step 2: Verify Domain Ownership

Zoho will provide a TXT record for verification.

**Add DNS Record:**
```
Type: TXT
Host: @ (or leave blank)
Value: zoho-verification=zb12345678.zmverify.zoho.com
TTL: 3600
```

**Verification Command (optional):**
```bash
dig TXT catalyze.app +short
# Should return the zoho-verification value
```

#### Step 3: Configure MX Records

Remove existing MX records and add Zoho's:

| Priority | Host | Value |
|----------|------|-------|
| 10 | @ | mx.zoho.com |
| 20 | @ | mx2.zoho.com |
| 50 | @ | mx3.zoho.com |

**⚠️ CRITICAL: MX Record Propagation**
- MX changes can take 24-48 hours to propagate globally
- During propagation, some emails may be lost
- **Schedule this during low-traffic hours**

#### Step 4: Configure SPF Record

SPF tells receiving servers which IPs are authorized to send email for your domain.

**Combined SPF for Zoho + SendGrid:**
```
Type: TXT
Host: @
Value: v=spf1 include:zoho.com include:sendgrid.net ~all
TTL: 3600
```

**Breakdown:**
- `include:zoho.com` - Authorizes Zoho's mail servers
- `include:sendgrid.net` - Authorizes SendGrid's servers
- `~all` - Soft fail for unauthorized senders (use `-all` for strict)

#### Step 5: Configure DKIM

DKIM adds a digital signature to verify email authenticity.

**For Zoho:**
1. Zoho Admin Console → Email → DKIM
2. Generate DKIM key for your domain
3. Add the provided CNAME/TXT record:

```
Type: TXT
Host: zmail._domainkey
Value: v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBA...
```

**For SendGrid:**
1. SendGrid → Settings → Sender Authentication → Authenticate Your Domain
2. Add the three CNAME records provided:

```
Type: CNAME
Host: em1234.catalyze.app
Value: u12345.wl.sendgrid.net

Type: CNAME
Host: s1._domainkey.catalyze.app
Value: s1.domainkey.u12345.wl.sendgrid.net

Type: CNAME
Host: s2._domainkey.catalyze.app
Value: s2.domainkey.u12345.wl.sendgrid.net
```

#### Step 6: Configure DMARC

DMARC tells receivers what to do with emails that fail SPF/DKIM.

```
Type: TXT
Host: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:admin@catalyze.app; ruf=mailto:admin@catalyze.app; fo=1
TTL: 3600
```

**DMARC Policy Options:**
- `p=none` - Monitor only (start here)
- `p=quarantine` - Send failures to spam
- `p=reject` - Reject failures entirely

**Recommended Rollout:**
1. Week 1-2: `p=none` (monitor reports)
2. Week 3-4: `p=quarantine` (test with 10%)
3. Week 5+: `p=reject` (full enforcement)

#### Step 7: Create Email Accounts in Zoho

1. Zoho Admin → Users → Add User
2. Create these accounts:

| Email | Purpose |
|-------|---------|
| `admin@catalyze.app` | Admin access, DMARC reports |
| `support@catalyze.app` | Customer support |
| `noreply@catalyze.app` | SendGrid sender (no login needed) |

**For noreply@:**
- Create as a user OR use Zoho's "Email Alias" feature
- This email is only used as the FROM address in SendGrid
- Replies can be forwarded to support@

---

## 3. CRM Application Configuration

### 3.1 Current Application Structure

```
auth/
├── __init__.py           # Exports EmailService, get_email_service
├── email_service.py      # SendGrid integration
├── auth_service.py       # Calls email_service for verification/reset
└── stripe_service.py     # Calls email_service for upgrade confirmation
```

### 3.2 Environment Variables

**Railway Dashboard → Your Service → Variables:**

```bash
# SendGrid Configuration
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=noreply@catalyze.app
SENDGRID_FROM_NAME=Catalyze

# Application URL (for email links)
APP_URL=https://catalyze.app
# OR let Railway auto-detect via RAILWAY_PUBLIC_DOMAIN
```

### 3.3 Email Service Code Reference

**File: `auth/email_service.py`**

```python
# Key configuration at top of file:
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@catalyze.app")
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "Catalyze")
```

**Available Email Methods:**

| Method | Trigger | Template |
|--------|---------|----------|
| `send_verification_email()` | User registration | Verify link, 24h expiry |
| `send_password_reset_email()` | Forgot password | Reset link, 1h expiry |
| `send_welcome_email()` | Email verified | Onboarding, feature intro |
| `send_upgrade_confirmation()` | Stripe checkout success | Synapse tier benefits |

### 3.4 Adding New Email Templates

To add a new email type:

```python
# In auth/email_service.py

def send_custom_email(self, to_email: str, custom_data: str) -> bool:
    """Send a custom notification email."""
    subject = "Your Custom Subject"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
            .logo {{ font-size: 28px; font-weight: bold; color: #00D4AA; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">⚗️ CATALYZE</div>
            <p>{custom_data}</p>
        </div>
    </body>
    </html>
    """
    
    return self._send_email(to_email, subject, html_content)
```

---

## 4. SendGrid Integration Guide

### 4.1 SendGrid Account Setup

#### Step 1: Create SendGrid Account

1. Go to [sendgrid.com](https://sendgrid.com)
2. Sign up (use admin@catalyze.app)
3. Complete account verification

#### Step 2: Create API Key

1. Settings → API Keys → Create API Key
2. Name: `Catalyze Production`
3. Permissions: **Restricted Access**
   - ✅ Mail Send → Full Access
   - ❌ All other permissions (principle of least privilege)
4. Copy the key immediately (shown only once)

```
API Key Format: SG.xxxxxxxx.yyyyyyyyyyyyyyyyyyyyyyy
```

#### Step 3: Authenticate Domain

1. Settings → Sender Authentication → Authenticate Your Domain
2. Select DNS Host (Cloudflare, GoDaddy, etc.)
3. Enter domain: `catalyze.app`
4. Add the CNAME records to your DNS (see Section 2.5)
5. Click "Verify"

**Verification Status Check:**
```bash
# Check CNAME records
dig CNAME em1234.catalyze.app +short
dig CNAME s1._domainkey.catalyze.app +short
dig CNAME s2._domainkey.catalyze.app +short
```

#### Step 4: Create Sender Identity

If domain authentication isn't complete yet:

1. Settings → Sender Authentication → Single Sender Verification
2. Add sender:
   - From Email: `noreply@catalyze.app`
   - Reply To: `support@catalyze.app`
   - From Name: `Catalyze`
3. Check inbox for verification email

### 4.2 SendGrid Dashboard Configuration

#### Email Activity Settings

1. Settings → Tracking → Open Tracking: **ON**
2. Settings → Tracking → Click Tracking: **ON** (optional, can break some links)
3. Settings → Mail Settings → Event Webhook: Configure for monitoring (optional)

#### Suppression Management

1. Suppressions → Manage Unsubscribes
2. Add unsubscribe link to marketing emails (not required for transactional)

### 4.3 API Integration Details

**Python SDK Installation:**
```bash
pip install sendgrid>=6.10.0
```

**Basic Send Example:**
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

message = Mail(
    from_email=('noreply@catalyze.app', 'Catalyze'),
    to_emails='user@example.com',
    subject='Welcome to Catalyze',
    html_content='<p>Hello!</p>'
)

sg = SendGridAPIClient('SG.your_api_key')
response = sg.send(message)
print(response.status_code)  # 202 = accepted
```

### 4.4 Rate Limits & Quotas

| Plan | Daily Limit | Monthly Limit | Rate Limit |
|------|-------------|---------------|------------|
| Free | 100/day | 100/day forever | 100/second |
| Essentials ($19.95) | 50,000/day | 50,000/month | 100/second |
| Pro ($89.95) | 100,000/day | 100,000/month | 100/second |

**For Product Hunt Launch:**
- Free tier is likely sufficient initially (100/day)
- Monitor usage in SendGrid → Statistics
- Upgrade to Essentials when approaching limit

---

## 5. Security Considerations

### 5.1 API Key Security

**DO:**
- ✅ Store API key in environment variables only
- ✅ Use Railway's encrypted variables
- ✅ Rotate keys every 90 days
- ✅ Use restricted API key (Mail Send only)

**DON'T:**
- ❌ Commit API key to Git
- ❌ Log API key in error messages
- ❌ Use full-access API key
- ❌ Share API key across environments

**Key Rotation Procedure:**
1. Create new API key in SendGrid
2. Update Railway environment variable
3. Wait for deployment to complete
4. Verify emails still send
5. Delete old API key in SendGrid

### 5.2 Email Security Headers

Our email_service.py sends with proper headers. Verify receiving servers see:

```
Authentication-Results: 
  dkim=pass header.d=catalyze.app;
  spf=pass smtp.mailfrom=noreply@catalyze.app;
  dmarc=pass action=none header.from=catalyze.app;
```

**Test with:** https://www.mail-tester.com/

### 5.3 Content Security

**Prevent Email Injection:**
```python
# Our code already sanitizes, but be careful with:
# - User-provided names (first_name)
# - Any dynamic content in emails

# Example sanitization:
import html
safe_name = html.escape(user_first_name)
```

**Template Injection Prevention:**
- All our templates use f-strings with controlled variables
- Never insert raw user HTML into email templates

### 5.4 Rate Limiting

**Application-Level Protection:**
```python
# Consider adding rate limiting for:
# - Password reset requests (max 3/hour per email)
# - Verification email resends (max 5/hour per user)

# Example with simple counter (add to auth_service.py):
def rate_limit_check(self, key: str, max_requests: int, window_seconds: int) -> bool:
    """Check if action is rate limited."""
    # Implement with Redis or database counter
    pass
```

### 5.5 Data Privacy (GDPR/CCPA)

**Email Data Retention:**
- SendGrid retains activity for 7 days (Free) to 30 days (Pro)
- Our database stores: email, name, timestamps
- Implement data deletion for user account removal

**Required Unsubscribe Handling:**
- Transactional emails (verification, password reset) don't require unsubscribe
- Marketing emails MUST include unsubscribe link
- Handle unsubscribes via SendGrid webhook or manual process

---

## 6. Testing & Validation Procedures

### 6.1 Pre-Migration Testing

**Local Testing (without SendGrid):**
```bash
# email_service.py logs emails when not configured
SENDGRID_API_KEY="" python -c "
from auth.email_service import get_email_service
svc = get_email_service()
print('Configured:', svc.is_configured)  # False
svc.send_verification_email('test@test.com', 'token123', 'Test')
# Logs: SendGrid not configured. Would send to test@test.com: ...
"
```

**Staging Environment Testing:**
```bash
# Use SendGrid sandbox mode or separate API key
# Set up staging subdomain: staging.catalyze.app
```

### 6.2 DNS Verification

**Verify All Records:**
```bash
# SPF
dig TXT catalyze.app +short
# Expected: "v=spf1 include:zoho.com include:sendgrid.net ~all"

# DKIM (Zoho)
dig TXT zmail._domainkey.catalyze.app +short

# DKIM (SendGrid)
dig CNAME s1._domainkey.catalyze.app +short
dig CNAME s2._domainkey.catalyze.app +short

# DMARC
dig TXT _dmarc.catalyze.app +short
# Expected: "v=DMARC1; p=quarantine; ..."

# MX (for Zoho inbound)
dig MX catalyze.app +short
# Expected:
# 10 mx.zoho.com.
# 20 mx2.zoho.com.
# 50 mx3.zoho.com.
```

### 6.3 Email Deliverability Testing

**Tool 1: Mail-Tester (Spam Score)**
1. Go to [mail-tester.com](https://www.mail-tester.com/)
2. Copy the test email address
3. Trigger a test email from your app
4. Check score (aim for 9+/10)

**Tool 2: MXToolbox**
1. Go to [mxtoolbox.com/SuperTool.aspx](https://mxtoolbox.com/SuperTool.aspx)
2. Enter domain: `catalyze.app`
3. Run: MX Lookup, SPF Check, DKIM Check, DMARC Check

**Tool 3: Gmail Deliverability**
1. Send test email to Gmail account
2. Open email → Three dots → "Show original"
3. Verify: `SPF: PASS`, `DKIM: PASS`, `DMARC: PASS`

### 6.4 Functional Testing Checklist

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Registration email | 1. Register new user<br>2. Check inbox | Verification email received within 30s |
| Verification link | 1. Click link in email<br>2. Observe app | Email verified, welcome email sent |
| Password reset | 1. Click "Forgot password"<br>2. Check inbox | Reset email received within 30s |
| Reset link expiry | 1. Wait 1+ hour<br>2. Click reset link | "Link expired" message |
| Upgrade confirmation | 1. Complete Stripe checkout<br>2. Check inbox | Synapse welcome email received |
| Reply handling | 1. Reply to noreply@ email | Reply goes to support@ (if configured) |

### 6.5 Load Testing

**For Product Hunt launch, simulate traffic:**
```python
# Simple load test script
import asyncio
from auth.email_service import get_email_service

async def send_batch():
    svc = get_email_service()
    for i in range(50):
        svc.send_verification_email(
            f"test{i}@example.com",
            f"token{i}",
            f"User{i}"
        )
        await asyncio.sleep(0.1)  # 10/second

asyncio.run(send_batch())
```

**Monitor in SendGrid:**
- Activity → Email Activity
- Statistics → Overview (delivery rate, bounces, spam reports)

---

## 7. Troubleshooting Guide

### 7.1 Common Issues

#### Issue: Emails not sending

**Symptoms:** No emails received, no errors in logs

**Checklist:**
1. Verify `SENDGRID_API_KEY` is set in Railway
2. Check API key hasn't been revoked in SendGrid
3. Verify sender email is authenticated
4. Check SendGrid → Suppressions (email might be blocked)

**Debug:**
```python
# Add to email_service.py temporarily
print(f"SendGrid configured: {self._sendgrid_available}")
print(f"API Key present: {bool(SENDGRID_API_KEY)}")
print(f"API Key prefix: {SENDGRID_API_KEY[:10]}...")
```

#### Issue: Emails going to spam

**Symptoms:** Emails deliver but land in spam folder

**Solutions:**
1. Complete domain authentication in SendGrid
2. Verify SPF, DKIM, DMARC records
3. Check mail-tester.com score
4. Avoid spam trigger words in subject/body
5. Ensure proper unsubscribe handling

#### Issue: "Sender identity not verified" error

**Symptoms:** SendGrid returns 403 error

**Solution:**
1. SendGrid → Sender Authentication
2. Either complete Domain Authentication
3. Or add Single Sender for `noreply@catalyze.app`

#### Issue: DNS records not propagating

**Symptoms:** SendGrid shows "pending" verification

**Solutions:**
1. Wait 24-48 hours for propagation
2. Check for typos in DNS records
3. Verify no conflicting records
4. Try different DNS lookup tools:
   ```bash
   # Use Google's DNS
   dig @8.8.8.8 TXT catalyze.app
   ```

#### Issue: Zoho not receiving emails

**Symptoms:** Emails to @catalyze.app bounce or never arrive

**Solutions:**
1. Verify MX records point to Zoho
2. Check Zoho admin for domain verification status
3. Ensure user mailboxes are created
4. Check Zoho spam folder

### 7.2 Error Codes

| SendGrid Error | Meaning | Solution |
|----------------|---------|----------|
| 401 | Invalid API key | Regenerate key |
| 403 | Sender not verified | Complete sender auth |
| 413 | Payload too large | Reduce email size |
| 429 | Rate limited | Slow down, wait 1 min |
| 500 | SendGrid server error | Retry with backoff |

### 7.3 Monitoring & Alerts

**SendGrid Alerts (recommended):**
1. Settings → Alerts
2. Add alerts for:
   - Bounce rate > 5%
   - Spam report rate > 0.1%
   - Monthly quota 80% used

**Application Monitoring:**
```python
# Add to email_service.py for production monitoring
def _send_email(self, ...):
    try:
        response = sg.send(message)
        if response.status_code not in (200, 201, 202):
            logger.error(f"SendGrid error {response.status_code}")
            # Send to monitoring service (Sentry, etc.)
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        # Alert ops team for critical emails
        return False
```

---

## 8. Migration Checklist

### Phase 1: Preparation (Day -7 to -3)

- [ ] Create Zoho account
- [ ] Document current DNS records (backup)
- [ ] Create SendGrid account
- [ ] Generate SendGrid API key
- [ ] Test SendGrid in development environment
- [ ] Notify team of migration schedule

### Phase 2: DNS Configuration (Day -2)

- [ ] Add SPF record (include both Zoho and SendGrid)
- [ ] Add Zoho DKIM record
- [ ] Add SendGrid CNAME records for domain auth
- [ ] Add DMARC record (p=none initially)
- [ ] **DO NOT change MX records yet**

### Phase 3: SendGrid Go-Live (Day -1)

- [ ] Verify SendGrid domain authentication
- [ ] Update Railway environment variables
- [ ] Deploy application
- [ ] Test all email flows in production
- [ ] Verify emails pass SPF/DKIM/DMARC

### Phase 4: Zoho MX Migration (Day 0)

**⚠️ Schedule during lowest traffic (e.g., 2-4 AM)**

- [ ] Create all Zoho user accounts
- [ ] Change MX records to Zoho
- [ ] Monitor MX propagation
- [ ] Test inbound email to support@
- [ ] Verify no email bounces

### Phase 5: Post-Migration (Day +1 to +7)

- [ ] Monitor DMARC reports
- [ ] Check bounce rates in SendGrid
- [ ] Verify all email flows working
- [ ] Tighten DMARC policy (p=quarantine)
- [ ] Document any issues encountered

### Phase 6: Hardening (Day +14)

- [ ] Review DMARC reports
- [ ] Set DMARC to p=reject
- [ ] Rotate SendGrid API key
- [ ] Final documentation update

---

## Appendix A: DNS Record Summary

**Final DNS Configuration for catalyze.app:**

| Type | Host | Value | Purpose |
|------|------|-------|---------|
| MX | @ | mx.zoho.com (priority 10) | Zoho inbound |
| MX | @ | mx2.zoho.com (priority 20) | Zoho inbound |
| MX | @ | mx3.zoho.com (priority 50) | Zoho inbound |
| TXT | @ | zoho-verification=zb... | Zoho domain verify |
| TXT | @ | v=spf1 include:zoho.com include:sendgrid.net ~all | SPF |
| TXT | zmail._domainkey | v=DKIM1; k=rsa; p=... | Zoho DKIM |
| CNAME | em1234 | u12345.wl.sendgrid.net | SendGrid auth |
| CNAME | s1._domainkey | s1.domainkey.u12345.wl.sendgrid.net | SendGrid DKIM |
| CNAME | s2._domainkey | s2.domainkey.u12345.wl.sendgrid.net | SendGrid DKIM |
| TXT | _dmarc | v=DMARC1; p=reject; rua=mailto:admin@... | DMARC |

---

## Appendix B: Emergency Rollback

If critical issues occur:

1. **Revert MX records** to previous provider
2. **Keep SPF** with SendGrid (transactional still works)
3. **Contact SendGrid support** if deliverability issues
4. **Check Zoho admin** for bounced emails during migration

**Rollback Command Reference:**
```bash
# Check current MX
dig MX catalyze.app +short

# If using Cloudflare, revert via API:
curl -X PATCH "https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  --data '{"content":"old-mx.provider.com","priority":10}'
```

---

## Appendix C: Contact Information

| Service | Support URL | Response Time |
|---------|-------------|---------------|
| SendGrid | support.sendgrid.com | 24-48 hours |
| Zoho Mail | zoho.com/mail/help | 24 hours |
| Railway | railway.app/help | Discord community |

---

**Document Maintained By:** Catalyze Engineering  
**Last Updated:** December 11, 2025  
**Next Review:** January 11, 2026
