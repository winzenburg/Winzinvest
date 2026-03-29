# Credential Rotation Guide — Immediate Action Required

## Summary

The following credentials were found in git-tracked files (`.env.feedhive`, `trading/.env.paper`) 
that were pushed to GitHub. All have been **removed from git history** as of 2026-03-29, 
but they were publicly accessible and must be rotated immediately.

---

## Affected Credentials

### 1. Telegram Bot Token
**Location:** `trading/.env.paper` (removed from git)  
**Value exposed:** `8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ`

**Rotation steps:**
1. Go to [https://t.me/BotFather](https://t.me/BotFather)
2. Send command: `/mybots`
3. Select your Mission Control bot
4. Select `API Token` → `Revoke current token`
5. Copy the new token
6. Update `trading/.env` with: `TELEGRAM_BOT_TOKEN=<new_token>`
7. Restart the scheduler and agents:
   ```bash
   pkill -f "scheduler.py"
   pkill -f "agents.*run_all"
   cd trading/scripts
   nohup python3 scheduler.py >> ../logs/scheduler.log 2>&1 &
   cd agents && nohup python3 run_all.py >> ../../logs/agents.log 2>&1 &
   ```

**Impact if not rotated:** Anyone with this token can send messages to your Telegram chat and read your bot's message history.

---

### 2. TradingView Webhook Secret
**Location:** `trading/.env.paper` (removed from git)  
**Value exposed:** `c0141c8b1dcdb5df112fba5fe9b86cd0331d772579036dae`

**Rotation steps:**
1. Generate a new secret:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update `trading/.env` with: `TV_WEBHOOK_SECRET=<new_secret>`
3. Update the secret in **every TradingView alert** that sends webhooks to your system:
   - Go to TradingView → Alerts
   - Edit each webhook alert
   - Update the `secret` field in the JSON payload
   - Save the alert

**Impact if not rotated:** An attacker could send fake trading signals to your webhook endpoint.

**Note:** Webhook listener is not currently running in production (no webhook server deployed), 
so this is lower priority, but should still be rotated before activating webhooks.

---

### 3. Dashboard API Key
**Location:** `trading/.env.paper` (removed from git)  
**Value exposed:** `5e3aaab9cf9738b34926df0fc8eac10015ac450cb50b331931850e15b5e396a2`

**Rotation steps:**
1. Generate a new API key:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
2. Update `trading/.env` with: `DASHBOARD_API_KEY=<new_key>`
3. Update any external clients that call protected dashboard endpoints (kill-switch, etc.)
4. No restart required — the dashboard API reads `.env` on every request

**Impact if not rotated:** An attacker could toggle your kill switch remotely via the API.

---

### 4. Resend API Key
**Location:** `trading/.env.paper` (removed from git)  
**Value exposed:** `re_UjAL42UD_N8hqtA5k5G8w7HUxxx2nFwCv`

**Rotation steps:**
1. Go to [https://resend.com/api-keys](https://resend.com/api-keys)
2. Delete the compromised key (starts with `re_UjAL42UD`)
3. Create a new API key: `+ API Key` → name it `Mission Control` → copy the key
4. Update `trading/.env` with: `RESEND_API_KEY=<new_key>`
5. No restart required — email scripts load `.env` on execution

**Impact if not rotated:** An attacker could send emails from your `FROM_EMAIL` address, 
potentially phishing you or spamming recipients.

---

### 5. FRED API Key
**Location:** `trading/.env.paper` (removed from git)  
**Value exposed:** `497af95a07e4fdea9f826e18a4fc054e`

**Rotation steps:**
1. Go to [https://fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
2. Log in with your FRED account
3. Go to `My Account` → `API Keys`
4. Delete the old key
5. Request a new API key
6. Update `trading/.env` with: `FRED_API_KEY=<new_key>`

**Impact if not rotated:** Low — FRED API is read-only and has generous rate limits. 
An attacker could exhaust your API quota, but cannot access account data.

**Priority:** Medium (less critical than Telegram/Dashboard keys).

---

### 6. MacroVoices Password
**Location:** `trading/.env.paper` (removed from git)  
**Value exposed:** `4W!ll1st0n`

**Rotation steps:**
1. Go to [https://www.macrovoices.com](https://www.macrovoices.com)
2. Log in with your account
3. Change password (account settings)
4. Update `trading/.env` with: `MACROVOICES_PASSWORD=<new_password>`

**Impact if not rotated:** An attacker could access your MacroVoices subscription content.

**Priority:** Low (read-only content access, no financial impact).

---

### 7. Marketaux API Key
**Location:** `trading/.env.paper` (removed from git)  
**Value exposed:** `sTU1E8aF65wF7XQKS4unTnOadCIDTh9RD0U4oUmN`

**Rotation steps:**
1. Go to [https://www.marketaux.com/account/api-keys](https://www.marketaux.com/account/api-keys)
2. Log in with your account
3. Revoke the old API key
4. Generate a new API key
5. Update `trading/.env` with: `MARKETAUX_API_KEY=<new_key>`

**Impact if not rotated:** An attacker could exhaust your 100 requests/day quota, 
preventing sentiment analysis. Read-only API — no data modification risk.

**Priority:** Medium.

---

### 8. FeedHive API Key
**Location:** `.env.feedhive` (removed from git)  
**Value exposed:** `fh_-HaFPR3x5h0POUNfx-ml3tmTza8TWQE87mI2F2F8`

**Rotation steps:**
1. Go to [https://app.feedhive.com/settings/api](https://app.feedhive.com/settings/api) (or similar)
2. Revoke the old API key
3. Generate a new API key
4. Update `.env.feedhive` with: `FEEDHIVE_API_KEY=<new_key>`

**Impact if not rotated:** An attacker could post to your social media accounts via FeedHive.

**Priority:** High (write access to social accounts).

---

## Rotation Priority Order

Execute in this order based on risk:

1. **CRITICAL (do first):**
   - Telegram Bot Token
   - Dashboard API Key
   - FeedHive API Key

2. **HIGH (do today):**
   - TradingView Webhook Secret
   - Resend API Key

3. **MEDIUM (do this week):**
   - Marketaux API Key
   - FRED API Key

4. **LOW (do when convenient):**
   - MacroVoices Password

---

## Post-Rotation Verification

After rotating all critical credentials:

1. Test Telegram:
   ```bash
   cd trading/scripts
   python3 -c "
   from notifications import send_telegram
   send_telegram('✅ Credential rotation complete — Telegram working')
   "
   ```

2. Test Dashboard API:
   ```bash
   curl -H "X-API-Key: $(grep DASHBOARD_API_KEY trading/.env | cut -d= -f2)" \
        https://winzinvest.com/api/kill-switch
   ```

3. Check scheduler log for errors after restart:
   ```bash
   tail -50 trading/logs/scheduler.log | grep -i error
   ```

4. Test email (optional):
   ```bash
   cd trading/scripts
   python3 daily_options_email.py --test
   ```

---

## GitHub Security

The git history has been cleaned, but consider these additional steps:

### Enable GitHub Secret Scanning

1. Go to your GitHub repo → Settings → Code security and analysis
2. Enable `Secret scanning`
3. Enable `Push protection` — blocks commits containing secrets

### Review Repository Access

1. Go to Settings → Collaborators and teams
2. Remove any unused access grants
3. Review deploy keys and GitHub Actions permissions

### Force-Push Warning

**DO NOT** force-push the cleaned history to GitHub until you've completed 
credential rotation. Once you force-push, the old history becomes inaccessible, 
but the credentials in it are already exposed. Rotate first, then clean GitHub.

When ready to clean GitHub:
```bash
git push origin --force --all
git push origin --force --tags
```

⚠️ This will rewrite history on GitHub. Coordinate with any collaborators first.

---

## Prevention

Add this to your `.zshrc` or `.bashrc`:

```bash
# Git pre-commit hook reminder
alias gc='git commit'
alias gca='git commit -a'

# Always check what you're about to commit
git-safe() {
    echo "Files to be committed:"
    git diff --staged --name-only
    echo ""
    read "response?Proceed with commit? (y/n) "
    if [[ "$response" =~ ^[Yy]$ ]]; then
        git commit "$@"
    else
        echo "Commit aborted"
    fi
}
```

Use `git-safe` instead of `git commit` for commits that might include config files.

---

## Questions?

If any rotation step fails or you need clarification, stop and verify before proceeding. 
When in doubt, generate a new credential rather than reusing an old one.

**Time estimate:** 20-30 minutes for all rotations + testing.
