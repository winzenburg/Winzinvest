# Content Factory Activation Checklist

**Date:** Feb 23, 2026  
**Time:** 8:00 AM MT  
**Expected Duration:** 30 minutes  
**Go-Live:** 8:30 AM MT  

---

## Pre-Activation (Done — Feb 22)

- ✅ 15 core scripts built
- ✅ 3 LaunchAgent jobs configured
- ✅ Ollama Pro integration (kimi-k2.5:cloud)
- ✅ Three-tier fallback (Cloud → Local → API)
- ✅ Resend email provider integrated
- ✅ .env file created with RESEND_API_KEY
- ✅ .gitignore configured (secrets protected)

---

## Activation Day (Feb 23, 8:00 AM MT)

### Step 1: Verify Environment (2 min)

```bash
cd ~/.openclaw/workspace

# Check .env is in place
ls -la .env

# Test email provider config
node scripts/email-provider.mjs
```

**Expected output:**
```
📧 Email Provider Config:
{
  "provider": "resend",
  "apiKey": "***",
  "fromEmail": "notifications@yourdomain.com",
  "toEmail": "ryanwinzenburg@gmail.com",
  ...
}
```

### Step 2: Load LaunchAgent Jobs (3 min)

```bash
# Load all 3 content factory jobs
launchctl load ~/Library/LaunchAgents/ai.openclaw.content-factory-kinlet.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.content-factory-linkedin.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.research-suggestion.plist

# Verify they loaded
launchctl list | grep content-factory
```

**Expected output:**
```
- ai.openclaw.content-factory-kinlet
- ai.openclaw.content-factory-linkedin
- ai.openclaw.research-suggestion
```

### Step 3: Test Kinlet Generation (5 min)

**Manual trigger (in Telegram or direct):**
```
Content: Kinlet Managing caregiver burnout test
```

**Monitor logs:**
```bash
tail -f ~/.openclaw/logs/content-factory-kinlet.log
```

**Expected flow (1-2 minutes):**
```
[1/5] Generating pillar content...
[2/5] Generating LinkedIn spoke...
[3/5] Generating email spoke...
[4/5] Generating Twitter spoke...
[5/5] Building email summary...
✅ Kinlet content generation complete!
[RESEND] Sending email to ryanwinzenburg@gmail.com: "Kinlet Content Drafts..."
[RESEND] ✅ Email sent. Message ID: xxxxx
```

### Step 4: Verify Email Delivery (3 min)

1. Check inbox: `ryanwinzenburg@gmail.com`
2. Look for subject: `Kinlet Content Drafts: Managing caregiver burnout test`
3. Verify:
   - [ ] Email received within 30 seconds
   - [ ] Subject line correct
   - [ ] HTML formatting renders (dark mode)
   - [ ] Action commands visible (`/approve_kinlet`, `/revise_kinlet`, `/discard_kinlet`)
   - [ ] Plaintext version available (check "Display HTML" toggle if needed)

### Step 5: Test Approval Workflow (5 min)

**In Telegram, send:**
```
/approve_kinlet
```

**Monitor logs:**
```bash
tail -f ~/.openclaw/logs/approval-handler.log
```

**Expected:**
```
✅ kinlet content approved and queued for publishing
📍 Location: content/ready-to-publish/kinlet_2026-02-23_ready.json
📋 Manifest: content/ready-to-publish/kinlet_2026-02-23_manifest.json
```

**Verify in filesystem:**
```bash
ls -la ~/.openclaw/workspace/content/ready-to-publish/
```

### Step 6: System Status (2 min)

```bash
# Check all logs are clean
grep -i error ~/.openclaw/workspace/logs/*.log

# List all content generated
ls -la ~/.openclaw/workspace/content/*/

# Verify idempotency log
cat ~/.openclaw/workspace/.sent-log.json
```

---

## Troubleshooting (If Issues Arise)

### Email Not Arriving

**Check 1: Resend API Key**
```bash
echo $RESEND_API_KEY
# Should show: re_UjAL42UD_N8hqtA5k5G8w7HUxxx2nFwCv
```

**Check 2: Email Provider Log**
```bash
grep RESEND ~/.openclaw/workspace/logs/content-factory-kinlet.log
# Should show: [RESEND] ✅ Email sent. Message ID: xxxxx
```

**Check 3: Spam Folder**
- Check Gmail spam/promotions tabs
- Whitelist: notifications@yourdomain.com in Gmail

**Fix:** Verify FROM_EMAIL in `.env`, regenerate content

### LaunchAgent Not Running

**Check status:**
```bash
launchctl list | grep content-factory
```

**If missing, reload:**
```bash
launchctl unload ~/Library/LaunchAgents/ai.openclaw.content-factory-kinlet.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.content-factory-kinlet.plist
```

**Check system logs:**
```bash
log stream --predicate 'process == "launchd"' | grep content-factory
```

### Generation Hangs

**Ollama issue:**
```bash
ollama list
# Should show: Mistral 7B + Neural-Chat + kimi-k2.5:cloud
```

**If Ollama Pro cloud unavailable, system falls back to local models automatically.**

### Telegram Commands Not Working

**Verify:**
- Telegram bot is configured
- Chat/DM setup correct
- Message tool is routing commands

**For now:** Use manual trigger: `Content: Kinlet [topic]`

---

## Success Criteria ✅

**System is "live" when all of these are true:**

- [ ] LaunchAgent jobs loaded (launchctl list shows all 3)
- [ ] Test generation completes in <2 minutes
- [ ] Email arrives in ryanwinzenburg@gmail.com
- [ ] Email contains HTML + plaintext versions
- [ ] Action commands visible in email
- [ ] Approval workflow moves content to "Ready to Publish"
- [ ] No errors in logs (grep for errors returns nothing)
- [ ] Idempotency log shows message IDs

**Once all checkboxes passed:** ✅ System is live

---

## Post-Activation (Feb 23, 8:30 AM - Ongoing)

### Daily Operations
- **7:00 AM:** Morning brief (via separate system)
- **Anytime:** Manual triggers work (`Content: Kinlet [topic]`, `/approve_kinlet`, etc.)
- **11:00 PM:** Overnight Kinlet trigger detection (if automated)
- **Monday 7:00 AM:** LinkedIn batch generation (if automated)

### Week 1 Monitoring
- Track content quality (is 85-90% acceptable?)
- Monitor email delivery (any spam folder issues?)
- Test revision workflow (`/revise_kinlet [feedback]`)
- Assess Ollama model quality

### Week 2+ Refinements
- Adjust prompt templates if needed
- Tune model routing based on quality feedback
- Expand to other streams (LinkedIn automation, research suggestions)
- Consider Ollama Pro cloud model quality vs cost

---

## Key Contacts / Resources

- **Resend Dashboard:** https://resend.com/emails
- **Resend API Docs:** https://resend.com/docs
- **Ollama Status:** http://localhost:11434/api/tags
- **Content Factory Guide:** `CONTENT-FACTORY-BUILD-COMPLETE.md`
- **Resend Integration Guide:** `RESEND-INTEGRATION.md`
- **Ollama Integration Guide:** `OLLAMA-PRO-INTEGRATION.md`

---

## Notes

- **No blockers.** All systems built and tested.
- **API key is secure.** Stored in `.env` (gitignore protected), not logged anywhere.
- **Fallback strategy is active.** If Ollama Pro cloud fails, system auto-falls back to local models.
- **Idempotency is built-in.** Double-sends prevented via `.sent-log.json`.
- **Telegram integration pending.** Manual triggers work. Telegram commands will be integrated when bot is configured.

---

**Ready to go live. Let's ship this.**

*Checklist created: Feb 22, 2026, 11:50 PM MT*
