# Resend Email Integration — Complete

**Status:** ✅ READY FOR ACTIVATION  
**Date:** Feb 22, 2026, 11:36 PM MT  
**Provider:** Resend  
**Format:** Multipart (HTML + plaintext)  

---

## What's Built

### 1. Email Provider Interface (`email-provider.mjs`)
- Abstract interface for swapping providers later
- Resend implementation included
- Idempotency tracking (prevent double-sends)
- Configuration helpers

### 2. Email Formatter Updates (`email-formatter.mjs`)
- Added `sendEmail()` function
- Multipart email (HTML + plaintext)
- Idempotency key generation
- Plaintext fallback for non-HTML clients

### 3. Content Factory Integration
- `content-factory-kinlet.mjs`: Sends email after generation
- `content-factory-linkedin.mjs`: Sends email after generation
- Both track email delivery status + message IDs

### 4. Configuration Template (`.env.example`)
- Shows all required environment variables
- Documented defaults
- Safe to check into git (redacted secrets)

---

## Configuration (What You Need to Do Feb 23)

### Step 1: Get Resend API Key (5 min)

1. Go to https://resend.com/api-keys
2. Create new API key
3. Copy the key (format: `re_xxxxxxxxxxxxxxxxxxxxx`)
4. Add to your `.env`:

```bash
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxx
```

### Step 2: Set Email Addresses (1 min)

```bash
# In .env:
FROM_EMAIL=notifications@yourdomain.com  # or noreply@example.com for dev
TO_EMAIL=ryanwinzenburg@gmail.com        # recipient
REPLY_TO_EMAIL=ryanwinzenburg@gmail.com  # where replies go
```

### Step 3: Verify Domain (Optional, Improves Deliverability)

For production, verify a domain in Resend:
1. Add SPF record
2. Add DKIM record
3. Add DMARC policy (basic: `v=DMARC1; p=none;`)

For now, `noreply@example.com` works for testing.

### Step 4: Load Environment (Feb 23 AM)

```bash
# Option A: Add to ~/.zshrc or ~/.bash_profile
export RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxx
export FROM_EMAIL=notifications@yourdomain.com
export TO_EMAIL=ryanwinzenburg@gmail.com

# Option B: Or set in launchd environment via .plist file
```

---

## How It Works

### Generation → Email Flow

```
User: Content: Kinlet Managing burnout
    ↓
content-factory-kinlet.mjs generates pillar + spokes
    ↓
Creates emailSummary object
    ↓
Calls sendEmail('kinlet', emailSummary)
    ↓
email-formatter.mjs checks idempotency (prevent double-sends)
    ↓
Builds multipart email (HTML + plaintext)
    ↓
Calls provider.send() with Resend API key
    ↓
Resend API returns message ID
    ↓
Logs to .sent-log.json (idempotency tracking)
    ↓
Returns success/error to orchestrator
```

### Idempotency (Double-Send Prevention)

If the same content is generated twice:
1. Generate idempotency key: `email-kinlet-managing-burnout-1703275200`
2. Check `.sent-log.json` for this key
3. If found: Skip sending, use cached message ID
4. If not found: Send normally, log result

**Benefit:** If content factory job retries, you won't get duplicate emails.

---

## Email Structure

### Multipart Format (Both HTML + Plaintext)

Modern email clients show HTML version (styled, formatted).
Older clients + text-only readers get plaintext.

**Example HTML:**
```html
<div class="container">
  <h1>Kinlet Content Drafts</h1>
  <p>Topic: Managing caregiver burnout</p>
  <div class="preview">...</div>
  <div class="actions">
    <button>/approve_kinlet</button>
    <button>/revise_kinlet</button>
  </div>
</div>
```

**Example Plaintext:**
```
Kinlet Content Drafts

Topic: Managing caregiver burnout
Pillar: 1,500 words

PREVIEW:
[first 200 chars]

YOUR OPTIONS:
/approve_kinlet
/revise_kinlet [feedback]
/discard_kinlet
```

### Headers + Metadata

Every email includes:
- `X-App: OpenClaw` (your system marker)
- `X-Content-Stream: kinlet|linkedin` (which stream)
- `X-Priority: normal` (delivery priority)
- Tags: `['kinlet', 'content-factory']` (Resend dashboard filtering)

---

## Error Handling

### Missing RESEND_API_KEY
```
[RESEND] Warning: RESEND_API_KEY not set. Email sending will fail.
Result: {success: false, error: 'RESEND_API_KEY not configured'}
```

**Fix:** Set `RESEND_API_KEY` in `.env` and reload environment.

### Network Error
```
[RESEND] Exception: getaddrinfo ENOTFOUND api.resend.com
Result: {success: false, error: 'Network error'}
```

**Fix:** Check internet connection, verify API key format.

### Invalid API Key
```
[RESEND] Error 401: Invalid API Key
Result: {success: false, error: 'HTTP 401: Invalid API Key'}
```

**Fix:** Verify API key format (should start with `re_`), regenerate if needed.

### Missing Required Fields
```
Result: {success: false, error: 'Missing required: to, subject, and (html or text)'}
```

**Fix:** Ensure email-formatter is building complete `emailSummary` object.

---

## Testing (Feb 23 AM)

### Test 1: Check Configuration

```bash
cd ~/.openclaw/workspace
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
  "replyTo": "ryanwinzenburg@gmail.com"
}

🧪 Testing email send (this will fail without RESEND_API_KEY)...
```

### Test 2: Run Content Generation (Live Test)

```bash
# Manual trigger
Content: Kinlet Test topic for email

# Wait 30 seconds...

# Check logs
tail -f ~/.openclaw/logs/content-factory-kinlet.log

# Should see:
[RESEND] Sending email to ryanwinzenburg@gmail.com: "Kinlet Content Drafts: Test topic..."
[RESEND] ✅ Email sent. Message ID: xxxxx
```

### Test 3: Check Inbox

- Check `ryanwinzenburg@gmail.com`
- Look for subject: "Kinlet Content Drafts: Test topic..."
- Verify both HTML and plaintext render
- Verify action buttons/commands visible

---

## Switching Providers (Future)

To swap from Resend to SES or Postmark:

1. Create new provider class in `email-provider.mjs`:
```javascript
export class SESProvider extends EmailProvider {
  async send(options) { /* SES API call */ }
}
```

2. Update factory:
```javascript
export function createEmailProvider(type = 'resend') {
  case 'ses': return new SESProvider();
}
```

3. Set environment:
```bash
EMAIL_PROVIDER=ses
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
```

No changes needed to `content-factory-*.mjs` or `email-formatter.mjs`.

---

## Monitoring + Logging

### Idempotency Log

Location: `~/.openclaw/workspace/.sent-log.json`

```json
{
  "sent": {
    "email-kinlet-managing-burnout-1703275200": {
      "messageId": "123e4567-e89b-12d3-a456-426614174000",
      "timestamp": "2026-02-23T15:30:00Z"
    }
  }
}
```

Check this if you suspect double-sends.

### Resend Dashboard

After API key is active:
1. Go to https://resend.com/emails
2. View all emails sent
3. Check delivery status, bounce rates, opens (if tracking enabled)
4. Filter by tags: `kinlet`, `linkedin`, `content-factory`

---

## Best Practices

### 1. Always Use Multipart
- HTML for rich formatting
- Plaintext for accessibility + fallback

### 2. Keep Subject Consistent
- Prefix: `[Kinlet]`, `[LinkedIn]`
- Include topic or date
- Example: `[Kinlet] Content Drafts: Managing burnout`

### 3. Include Reply-To
- Users can hit "Reply" in email client
- Reply goes to your specified email (not API sender)

### 4. Tag Everything
- Makes filtering in Resend dashboard easy
- Helps debugging: "show me all kinlet emails from Feb 23"

### 5. Monitor Error Rate
- Check logs for failed sends
- Review Resend dashboard for bounces
- High bounce rate = issue with recipient email

---

## FAQ

**Q: Will emails go to spam?**  
A: Unlikely if you:
- Verify domain in Resend (SPF/DKIM/DMARC)
- Use consistent FROM email
- Keep unsubscribe headers (Resend handles this)

**Q: Can I schedule emails?**  
A: Not with current setup (sends immediately). To schedule:
- Queue job in database
- Run cron to check queue + send at scheduled time
- Or use a service like Bull Queue

**Q: What if Resend API is down?**  
A: Email send fails with error. Content is still generated + saved. You can retry manually later.

**Q: How much does Resend cost?**  
A: Free tier: 100 emails/day. You'll be fine. Paid: $20/month for unlimited.

**Q: Can I use Resend for marketing emails?**  
A: Not recommended (they're transactional-only). Use Mailchimp/Postmark for newsletters.

---

## Status Checklist (Feb 23, 8:00 AM)

- [ ] `RESEND_API_KEY` added to `.env`
- [ ] `FROM_EMAIL` set (notifications@yourdomain.com or noreply@example.com)
- [ ] `TO_EMAIL` = ryanwinzenburg@gmail.com
- [ ] Test: `node email-provider.mjs` runs
- [ ] Generate test content: `Content: Kinlet Test topic`
- [ ] Email arrives in inbox
- [ ] HTML + plaintext both render
- [ ] Message ID logged in `.sent-log.json`

---

**Integration complete. Ready for activation Feb 23.**

*Last updated: Feb 22, 2026, 11:36 PM MT*
