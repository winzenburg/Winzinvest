# Context7 Integration Guide

**Purpose:** Keep development environment updated with latest documentation for security and stability.

**Critical:** Context7 is for **development ONLY** - never deployed to production VPS.

---

## What is Context7?

Context7 is a documentation context management tool that keeps AI assistants (like Cursor) updated with the latest:
- API documentation
- Security advisories
- Best practices
- Framework updates

For a real-money trading system, this ensures every code suggestion is validated against current security guidelines and API versions.

---

## Strategic Integration

### ✅ Where Context7 IS Used

1. **Cursor IDE** (your development environment)
   - Provides AI assistant with latest docs
   - Alerts on security vulnerabilities
   - Suggests secure coding patterns

2. **Pre-commit checks** (optional)
   - Validates code against security advisories
   - Checks dependency versions
   - Warns about deprecated APIs

3. **Documentation generation**
   - Keeps deployment guides current
   - Updates API reference docs
   - Maintains security checklist

### ❌ Where Context7 is NOT Used

1. **Production VPS**
   - No external dependencies in trading execution
   - Minimal attack surface
   - Isolated from external APIs

2. **Trading scripts**
   - No runtime documentation fetching
   - No network calls to Context7
   - Pure execution logic only

3. **Vercel frontend** (production)
   - No Context7 API calls
   - No doc fetching at runtime
   - Static builds only

---

## Configuration

The `.context7.yml` file defines:

### Documentation Sources (Prioritized)

**TIER 1 - Critical (Check Daily):**
- Python security advisories (CVEs)
- Docker security scanning
- AWS security best practices

**TIER 2 - High (Check Weekly):**
- AWS Lightsail documentation
- IBKR TWS API updates
- FastAPI security patterns
- Docker best practices

**TIER 3 - Medium (Check Monthly):**
- Next.js updates
- Vercel deployment changes
- Monitoring tools

**TIER 4 - Internal (Always Include):**
- `deployment/*.md` files
- `.cursor/rules/*.mdc` files
- Trading strategy docs

### Alert Levels

**Critical** (Immediate action):
- Security vulnerabilities in `ib-insync`, `fastapi`, `uvicorn`
- IBKR API breaking changes
- AWS Lightsail service disruptions
- **Channel:** Telegram alert (reuse existing bot)

**High** (Review within 24h):
- Docker security advisories
- Python dependency security fixes
- **Channel:** Cursor notification

**Medium** (Review weekly):
- Framework updates
- Non-security dependency updates
- **Channel:** Weekly digest

---

## Setup Instructions

### 1. Enable Context7 in Cursor (Recommended)

If Cursor has built-in Context7 support:

1. Open Cursor Settings
2. Navigate to **Extensions** → **Context7**
3. Enable **Auto-refresh documentation**
4. Set refresh interval: **Daily** for critical, **Weekly** for others
5. Point to `.context7.yml` in project root

### 2. Manual Context7 CLI (Alternative)

If using standalone Context7:

```bash
# Install Context7 CLI
npm install -g context7

# Or with pip
pip install context7

# Authenticate (if required)
context7 login

# Initialize in project
cd ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control
context7 init  # This creates .context7.yml (already done)

# Fetch latest docs
context7 sync

# Watch for updates (runs in background)
context7 watch --interval daily
```

### 3. Telegram Integration (Optional)

To get alerts via Telegram (reusing your existing bot):

Add to `.context7.yml`:

```yaml
alerts:
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}  # From .env
    chat_id: ${TELEGRAM_CHAT_ID}      # From .env
    filter: [critical, high]
```

Then alerts like "ib-insync CVE-2024-XXXX" go straight to Telegram.

---

## Security Best Practices

### 1. Never Deploy Context7 to VPS

**Correct deployment structure:**

```
Mac (development)          VPS (production)
─────────────────          ────────────────
✅ Context7 enabled        ❌ No Context7
✅ .context7.yml           ❌ Excluded in rsync
✅ AI assistant updated    ✅ Pure execution only
```

**In `deploy-to-vps.sh`, exclude:**

```bash
rsync -avz --delete \
  --exclude=".context7.yml" \
  --exclude="context7/" \
  ...
```

### 2. Credentials Management

Context7 config references env vars but never stores them:

```yaml
# Good: Reference env vars
telegram:
  bot_token: ${TELEGRAM_BOT_TOKEN}

# Bad: Hardcode credentials
telegram:
  bot_token: "123456:ABC..."  # ❌ Never do this
```

### 3. Documentation Scope

Only fetch docs relevant to your stack:

```yaml
# ✅ Fetch these - you use them
- FastAPI
- ib_insync
- AWS Lightsail

# ❌ Don't fetch these - irrelevant
- Ruby on Rails
- Angular
- WordPress
```

This minimizes external API calls and keeps context lean.

---

## Usage in Development

### When Writing Code

1. **Check security before suggesting**
   - Cursor automatically references latest CVE databases
   - Warns if suggesting vulnerable code patterns
   - Validates against IBKR API best practices

2. **API version awareness**
   - Context7 knows you're using `ib_insync==0.9.86`
   - Won't suggest APIs from newer versions
   - Flags deprecated methods in your version

3. **AWS deployment guidance**
   - Suggests current Lightsail firewall rules
   - References latest security group best practices
   - Validates systemd service configurations

### Pre-Commit Checks (Optional)

Enable git hooks in `.context7.yml`:

```yaml
git_hooks:
  pre_commit:
    - check_security_advisories
    - verify_dependency_versions
  enabled: true
```

Then before every commit:
```bash
git commit -m "..."
# Context7 runs automatically
# ✅ Passed security checks
# ⚠️  Warning: pandas 2.0.0 has CVE-2024-XXXX
# [Do you want to continue? Y/n]
```

---

## Monitoring & Maintenance

### Daily Tasks (Automated)

Context7 automatically:
- Checks Python security advisories
- Scans for IBKR API changes
- Monitors Docker CVEs

**No action needed** unless alert triggered.

### Weekly Review

Check Context7 dashboard:

```bash
context7 status
```

Output:
```
📊 Context7 Status Report
─────────────────────────
Security Alerts:    0 critical, 1 high
Documentation:      42 sources, all up-to-date
Last Sync:          2 hours ago

⚠️  High Priority Alert:
    - fastapi 0.110.0 → 0.111.0 (security fix)
    - Affects: /api/dashboard authentication
    - Action: Update requirements.txt

✅ All AWS Lightsail docs current
✅ IBKR API stable (no breaking changes)
```

### Monthly Audit

Review `.context7.yml`:
- Remove unused documentation sources
- Update priority levels based on recent issues
- Adjust alert thresholds if too noisy

---

## Troubleshooting

### Context7 Not Updating

```bash
# Check connection
context7 status

# Force refresh
context7 sync --force

# Check logs
context7 logs --tail 50
```

### Too Many Alerts

Edit `.context7.yml`:

```yaml
alerts:
  critical:
    threshold: high  # Was: medium
    channels:
      - telegram
  high:
    threshold: critical  # Was: high
```

This raises the bar for what triggers alerts.

### Cursor Not Seeing Updates

1. Restart Cursor
2. Run: `context7 sync`
3. Check Cursor settings → Context7 → Last refresh time
4. Manually reload: Cmd+Shift+P → "Reload Context7"

---

## Cost

**Context7 pricing** (as of 2024):
- Free tier: 10 documentation sources
- Pro: $10/month (unlimited sources, priority support)
- Enterprise: Custom pricing

**Our setup:**
- **19 external sources** → Requires Pro ($10/mo)
- **4 internal sources** → Included
- **Total:** $10/month

**Value:** Prevents a single security incident that could cost $1,000+ in losses or downtime.

---

## Updating the Configuration

To add a new documentation source:

1. Edit `.context7.yml`:

```yaml
sources:
  - name: New Framework
    url: https://docs.newframework.com/
    type: library
    priority: medium
    tags: [backend, api]
    cadence: monthly
```

2. Sync:

```bash
context7 sync
```

3. Test:

```bash
context7 query "How to authenticate with New Framework?"
```

---

## Integration with Existing Workflows

### With Git

```bash
# .git/hooks/pre-commit
#!/bin/bash
context7 check-security
```

### With GitHub Actions (Optional)

```yaml
# .github/workflows/security-check.yml
name: Security Check
on: [push, pull_request]

jobs:
  context7:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install Context7
        run: npm install -g context7
      - name: Check Security
        run: context7 check-security
```

### With Vercel Deployment

**Do NOT integrate** - Context7 is development-only.

Vercel builds are static and don't need runtime docs.

---

## FAQ

### Q: Will Context7 slow down my trading system?

**A:** No. Context7 runs on your Mac during development, not on the VPS. Zero production impact.

### Q: What if Context7 is down?

**A:** Your code continues working. Context7 is informational only - it doesn't block execution.

### Q: Can Context7 access my credentials?

**A:** No. The `.context7.yml` references env vars but doesn't read `.env` directly. It only fetches public documentation.

### Q: Should I commit `.context7.yml` to git?

**A:** Yes. It contains no secrets, just documentation URLs. Committing it allows team members to benefit from the same context.

### Q: Does this replace reading official docs?

**A:** No. Context7 supplements your knowledge by providing quick access and alerts. Always read official docs for critical changes.

---

## Summary

**Context7 Strategic Value:**

✅ **Security:** Immediate CVE alerts for trading dependencies  
✅ **Stability:** Validates code against latest API versions  
✅ **Efficiency:** AI assistant has current docs, fewer errors  
✅ **Compliance:** Maintains audit trail of security checks  

**Cost:** $10/month  
**Risk:** Zero (development only, no production impact)  
**ROI:** High (prevents costly security incidents)

**Next Step:** Enable Context7 in Cursor and run `context7 sync`

---

## Support

If you have questions about Context7 setup:

1. Check Context7 official docs: https://docs.context7.com
2. Review this guide's troubleshooting section
3. Run: `context7 help`
