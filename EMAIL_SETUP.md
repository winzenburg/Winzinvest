# OpenClaw Email System Setup Guide

## Overview

This guide covers the complete email delivery system for OpenClaw, including:
- **Morning Brief** - Daily market briefing at 7:00 AM MT
- **Daily Portfolio Report** - Trading portfolio summary at 4:00 PM MT  
- **Regime Alerts** - Instant notifications for market regime changes

All email delivery is powered by **Resend**, a modern email API service.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Variables](#environment-variables)
3. [File Structure](#file-structure)
4. [Setup Instructions](#setup-instructions)
5. [Configuration Files](#configuration-files)
6. [Troubleshooting](#troubleshooting)
7. [Testing](#testing)
8. [Production Checklist](#production-checklist)

---

## Quick Start

```bash
# 1. Get a Resend API key from https://resend.com/api-keys
# 2. Run the interactive setup
cd ~/.openclaw/workspace
bash scripts/setup-email-config.sh

# 3. Verify everything works
bash scripts/validate-email-setup.sh

# 4. Done! Email system is ready
```

**Expected result:** Emails sent at scheduled times (7 AM, 4 PM MT, and on regime changes).

---

## Environment Variables

### Required Variables

| Variable | Purpose | Source | Format |
|----------|---------|--------|--------|
| `RESEND_API_KEY` | Email API key | Resend dashboard | `re_*` |
| `FROM_EMAIL` | Sender address | Your domain | `user@domain.com` |
| `TO_EMAIL` | Recipient address | Your email | `user@example.com` |
| `TELEGRAM_BOT_TOKEN` | Telegram alerts | BotFather | Token string |
| `TELEGRAM_CHAT_ID` | Telegram recipient | Telegram API | Numeric ID |

### Loading Priority

Variables are loaded in this order (first match wins):

1. **`~/.openclaw/workspace/.env`** (workspace-level config)
2. **`~/.openclaw/workspace/trading/.env`** (trading-specific overrides)
3. **System environment variables**

This allows flexibility:
- Shared variables in workspace `.env`
- Trading-specific overrides in `trading/.env`
- System environment for sensitive data

### Logging

When a script loads environment variables, it logs:

```
[INFO] Loaded RESEND_API_KEY from ~/.openclaw/workspace/.env
[INFO] Loaded FROM_EMAIL from ~/.openclaw/workspace/.env
[INFO] Loaded TO_EMAIL from system environment
```

Check logs to verify correct loading order.

---

## File Structure

```
~/.openclaw/workspace/
├── .env                              # Workspace config (workspace-level)
├── .env.template                    # Template for setup
├── logs/
│   └── morning-brief.log           # Morning brief execution log
├── scripts/
│   ├── morning-brief.mjs           # Morning brief generator
│   ├── setup-email-config.sh       # Interactive setup script
│   └── validate-email-setup.sh     # Validation & health check
├── EMAIL_SETUP.md                  # This file
└── Library/LaunchAgents/
    └── ai.openclaw.morning-brief.plist

trading/
├── .env                             # Trading config (trading-specific)
├── .env.template                   # Template
├── logs/
│   └── daily_report.log           # Daily report log
├── scripts/
│   ├── email_helper.py            # Universal email module
│   ├── daily_portfolio_report.py  # Daily report script
│   ├── regime_alert.py            # Regime alerts
│   └── send_daily_report.sh       # Shell wrapper
└── Library/LaunchAgents/
    └── com.pinchy.trading.daily-report.plist
```

---

## Setup Instructions

### Step 1: Get Resend API Key

1. Visit **https://resend.com**
2. Sign up or log in
3. Go to **API Keys** section
4. Create a new API key
5. Copy the key (starts with `re_`)

**⚠️ Keep this key secure!** Never commit to version control.

### Step 2: Verify Sender Domain

In Resend dashboard:
1. Go to **Domains**
2. Add your domain (e.g., `notifications@pinchy.dev`)
3. Follow verification steps (DNS records)
4. Wait for verification (can take minutes to hours)

**Note:** Until verified, use Resend's test domain `onboarding@resend.dev`

### Step 3: Run Setup Script

```bash
cd ~/.openclaw/workspace
bash scripts/setup-email-config.sh
```

The script will:
- Prompt for API key, FROM_EMAIL, TO_EMAIL
- Create/update `.env` files
- Update launchd plist files
- Test email delivery
- Reload launchd jobs

### Step 4: Verify Configuration

```bash
bash scripts/validate-email-setup.sh
```

This checks:
- ✓ `.env` files exist
- ✓ Required variables are set
- ✓ Python dependencies installed
- ✓ LaunchAgent jobs are loaded
- ✓ Email delivery works (optional test)

### Step 5: Monitor Logs

Watch for the next scheduled job:

```bash
# Morning brief at 7:00 AM MT
tail -f logs/morning-brief.log

# Daily report at 4:00 PM MT
tail -f trading/logs/daily_report.log
```

Expected log entries:
```
[2026-02-26 07:00:00] [INFO] [LOAD] RESEND_API_KEY from ~/.openclaw/workspace/.env
[2026-02-26 07:00:00] [INFO] [SEND] Email sent successfully (ID: ...)
```

---

## Configuration Files

### .env File Format

```bash
# Email delivery
RESEND_API_KEY=re_your_api_key_here
FROM_EMAIL=notifications@pinchy.dev
TO_EMAIL=ryanwinzenburg@gmail.com

# Telegram alerts (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# System
WORKSPACE_DIR=/Users/pinchy/.openclaw/workspace
```

**Load order for each variable:**
1. Check `.env` file
2. Check `trading/.env` file  
3. Check system environment
4. Use default value (if available)

### LaunchAgent Configuration

Plists now include EnvironmentVariables section:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>RESEND_API_KEY</key>
    <string>re_...</string>
    <key>FROM_EMAIL</key>
    <string>notifications@pinchy.dev</string>
    <key>TO_EMAIL</key>
    <string>ryanwinzenburg@gmail.com</string>
</dict>
```

This ensures environment variables are available when launchd runs jobs.

---

## Email Delivery System

### Email Helper Module

`trading/scripts/email_helper.py` provides universal email functions:

```python
from email_helper import load_email_config, send_email, validate_email_config

# Load configuration
config = load_email_config()

# Validate (optional)
is_valid, msg = validate_email_config(config)

# Send email
success = send_email(
    subject="Hello World",
    html_body="<p>Email body</p>",
    config=config
)
```

### Usage in Scripts

**Python:**
```python
from email_helper import send_email

send_email(
    subject="Daily Report",
    html_body="<p>Your report</p>",
    to_email="recipient@example.com"
)
```

**Node.js:**
Send via Resend API directly (use RESEND_API_KEY environment variable):
```javascript
const payload = {
  from: process.env.FROM_EMAIL,
  to: process.env.TO_EMAIL,
  subject: "Morning Brief",
  html: "<p>...</p>"
};

// POST to https://api.resend.com/emails
```

### Error Handling

All email functions include graceful degradation:
- Missing API key → logs warning, continues
- Network error → retries with timeout, logs error
- Invalid email → logs error, returns false

Scripts **do not crash** if email fails. They log errors and continue.

---

## Troubleshooting

### Email Not Sending

**Check 1: API Key**
```bash
grep RESEND_API_KEY ~/.openclaw/workspace/.env
```
Should start with `re_`

**Check 2: Logs**
```bash
tail -f logs/morning-brief.log | grep EMAIL
```

Look for entries like:
```
[EMAIL] ✗ HTTP 401: Unauthorized
[EMAIL] ✗ RESEND_API_KEY not set
[EMAIL] ✗ Connection error
```

**Check 3: Domain Verification**
In Resend dashboard, verify FROM_EMAIL domain is verified (green checkmark).

**Check 4: LaunchAgent**
```bash
# Check if job is loaded
launchctl list | grep morning-brief

# Check environment variables
launchctl getenv RESEND_API_KEY

# Check plist syntax
plutil -lint ~/Library/LaunchAgents/ai.openclaw.morning-brief.plist
```

### Variables Not Loaded

**Check 1: File Permissions**
```bash
ls -la ~/.openclaw/workspace/.env
# Should be readable by your user
```

**Check 2: File Location**
```bash
ls -la ~/.openclaw/workspace/.env
ls -la ~/.openclaw/workspace/trading/.env
```

**Check 3: Logs**
```bash
tail logs/morning-brief.log | grep "\[LOAD\]"
```

Should show which files were loaded.

**Check 4: Reload LaunchAgent**
```bash
launchctl unload ~/Library/LaunchAgents/ai.openclaw.morning-brief.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.morning-brief.plist
```

### Python Import Error

If you see `ModuleNotFoundError: No module named 'email_helper'`:

1. Check script location:
   ```bash
   ls trading/scripts/email_helper.py
   ```

2. Check Python path:
   ```bash
   cd trading/scripts
   python3 -c "import email_helper"
   ```

3. Install dependencies:
   ```bash
   pip3 install python-dotenv requests ib-insync
   ```

### Timezone Issues

OpenClaw uses Mountain Time (America/Denver) for scheduling.

**Verify timezone:**
```bash
# Check system timezone
date
# Should show MT or MDT

# Check launchd timezone
plutil -p ~/Library/LaunchAgents/ai.openclaw.morning-brief.plist | grep -A 2 TimeZone
```

---

## Testing

### Manual Test 1: Load Configuration

```bash
cd ~/.openclaw/workspace/trading/scripts
python3 email_helper.py --validate
```

Expected output:
```
[INFO] [LOAD] RESEND_API_KEY from ~/.openclaw/workspace/.env
[INFO] [VALIDATE] Email configuration is complete and valid
```

### Manual Test 2: Send Test Email

```bash
cd ~/.openclaw/workspace/trading/scripts
python3 email_helper.py --test
```

Expected output:
```
[INFO] [TEST] Starting email delivery test...
[INFO] [SEND] Sending email to ryanwinzenburg@gmail.com...
[INFO] [SEND] ✓ Email sent successfully (ID: ...)
[INFO] [TEST] ✓ Test email delivered successfully
```

### Manual Test 3: Run Scripts Manually

**Morning Brief:**
```bash
cd ~/.openclaw/workspace
node scripts/morning-brief.mjs
```

**Daily Report:**
```bash
cd ~/.openclaw/workspace/trading
python3 scripts/daily_portfolio_report.py
```

**Regime Alert:**
```bash
cd ~/.openclaw/workspace/trading
python3 scripts/regime_alert.py --force
```

### Manual Test 4: Check LaunchAgent

```bash
# List loaded jobs
launchctl list | grep openclaw

# Check next run time
launchctl list ai.openclaw.morning-brief

# Run immediately (for testing)
launchctl start ai.openclaw.morning-brief
```

---

## Production Checklist

Before going live:

- [ ] Resend account created and API key obtained
- [ ] Sender domain verified in Resend
- [ ] `.env` file created with all required variables
- [ ] `setup-email-config.sh` ran successfully
- [ ] `validate-email-setup.sh` passes all checks
- [ ] Test email received successfully
- [ ] Morning brief test ran without errors
- [ ] Daily report test ran without errors
- [ ] Regime alert test ran without errors
- [ ] LaunchAgent plists are loaded (`launchctl list`)
- [ ] Logs are being written to correct locations
- [ ] Backup of original `.env` and plist files

### Pre-Production Tests

Run these before deploying:

```bash
# 1. Validate setup
bash scripts/validate-email-setup.sh

# 2. Test email delivery
cd trading/scripts && python3 email_helper.py --test

# 3. Test morning brief
node scripts/morning-brief.mjs 2>&1 | tee ~/test-morning-brief.log

# 4. Test daily report  
python3 trading/scripts/daily_portfolio_report.py 2>&1 | tee ~/test-daily-report.log

# 5. Check logs
tail -20 logs/morning-brief.log
tail -20 trading/logs/daily_report.log
```

All tests should complete with `✓` or `[SUCCESS]` markers.

---

## Monitoring & Maintenance

### Monthly Validation

```bash
# Run monthly (add to calendar reminder)
bash scripts/validate-email-setup.sh
```

This checks:
- API key still valid
- Domain still verified
- Environment variables configured
- LaunchAgent jobs still loaded

### Log Rotation

Setup log rotation to prevent disk fill:

```bash
# Create rotation config
cat > /etc/newsyslog.d/openclaw.conf << 'EOF'
/Users/pinchy/.openclaw/workspace/logs/*log    root:wheel  640 5 1000 * Z
/Users/pinchy/.openclaw/workspace/trading/logs/*log root:wheel 640 5 1000 * Z
EOF
```

### Backup

Backup critical files:

```bash
# Backup .env files
cp ~/.openclaw/workspace/.env ~/.openclaw/workspace/.env.backup
cp ~/.openclaw/workspace/trading/.env ~/.openclaw/workspace/trading/.env.backup

# Backup plists
cp ~/Library/LaunchAgents/ai.openclaw.morning-brief.plist ~/backup/
cp ~/Library/LaunchAgents/com.pinchy.trading.daily-report.plist ~/backup/
```

---

## Advanced Configuration

### Custom Email Templates

Edit the HTML generation in each script:

**Morning Brief** (scripts/morning-brief.mjs):
```javascript
const html = `
  <html>
    <body>Your custom template here</body>
  </html>
`;
```

**Daily Report** (trading/scripts/daily_portfolio_report.py):
```python
html_content = """
  <html>
    <body>Your custom HTML here</body>
  </html>
"""
```

### Multiple Recipients

Modify scripts to send to multiple emails:

```python
recipients = ['email1@example.com', 'email2@example.com']
for recipient in recipients:
    send_email(subject, html_body, to_email=recipient, config=config)
```

### Conditional Sending

Only send if certain conditions are met:

```python
# Only send if portfolio has positions
if portfolio_data['position_count'] > 0:
    send_email(subject, html_body, config=config)
```

---

## Support & Debugging

### Enable Debug Logging

```bash
# Set log level (in .env)
LOG_LEVEL=DEBUG

# Or pass via environment
LOG_LEVEL=DEBUG python3 scripts/daily_portfolio_report.py
```

### Check Script Permissions

```bash
# Scripts should be executable
chmod +x scripts/morning-brief.mjs
chmod +x scripts/setup-email-config.sh
chmod +x scripts/validate-email-setup.sh
```

### Manual LaunchAgent Management

```bash
# Load a job
launchctl load ~/Library/LaunchAgents/ai.openclaw.morning-brief.plist

# Unload a job
launchctl unload ~/Library/LaunchAgents/ai.openclaw.morning-brief.plist

# Force immediate run
launchctl start ai.openclaw.morning-brief

# Check job output
log show --predicate 'process == "launchd"' --last 1h
```

---

## References

- **Resend Docs:** https://resend.com/docs
- **launchd Guide:** https://www.manpagez.com/man/5/launchd.plist/
- **Environment Variables:** `.env.template` in workspace

---

## Summary

The email system is now configured for:
- ✅ Reliable environment variable loading
- ✅ Multiple email channels (morning brief, daily report, regime alerts)
- ✅ Robust error handling and logging
- ✅ LaunchAgent integration for scheduled delivery
- ✅ Easy setup and validation scripts
- ✅ Production-ready with monitoring

Questions or issues? Check logs first, then follow troubleshooting guide above.
