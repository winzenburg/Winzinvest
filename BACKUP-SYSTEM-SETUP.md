# Backup & Git Sync System Setup Guide

**Status:** ⏳ Awaiting password confirmation  
**Date:** February 21, 2026  
**Components:**
1. Nightly workspace backup + encryption + Google Drive upload
2. Git auto-sync across all home directory repositories
3. Automated cleanup of 30-day-old backups
4. Comprehensive logging and Telegram notifications

---

## Part 1: RCLONE INSTALLATION & GOOGLE DRIVE SETUP

### What is rclone?

rclone is a command-line tool for syncing files to cloud storage (Google Drive, S3, OneDrive, etc). It's the standard way to automate backups on macOS.

**Installation (macOS):**

```bash
# Using Homebrew (recommended)
brew install rclone

# Or direct download
curl https://rclone.org/install.sh | bash
```

**Verify installation:**
```bash
rclone --version
```

### Configure Google Drive Access

Once rclone is installed, you need to authenticate with your Google account:

```bash
rclone config
```

**Steps:**
1. Select `n` for "New remote"
2. Name: `google-drive` (this matches our backup script)
3. Type: `google cloud storage` or `drive` (Google Drive)
4. Leave client_id and client_secret blank (use rclone's built-in)
5. Choose scope: `1` for full access
6. Edit advanced config: `n` (no)
7. Use auto config: `y` (yes) — Opens browser for Google auth
8. **Approve access** in the browser window
9. Configure as team drive: `n` (no)
10. Confirm configuration

**Verify setup:**
```bash
rclone ls google-drive:
```

Should list your Google Drive contents.

### Create Backup Folder

In Google Drive web interface:
1. Go to https://drive.google.com
2. Create folder: `OpenClaw Backups`
3. Get folder ID from URL: `https://drive.google.com/drive/folders/[FOLDER_ID]`
4. Save folder ID for later

**Or via rclone:**
```bash
rclone mkdir google-drive:"OpenClaw Backups"
```

---

## Part 2: PASSWORD MANAGEMENT (SECURITY)

### Two Options

**Option A: macOS Keychain (Recommended)**
- Password stored securely in Keychain
- Script retrieves it automatically
- More secure, requires setup
- Backup script code already supports this

**Option B: Environment Variable**
- Store in `~/.openclaw/.env` file (not tracked by git)
- Simpler but requires more care
- Less secure

**Option C: No Encryption**
- Skip encryption, store unencrypted backups
- Faster, relies on Google Drive's security
- Simplest setup

### Setup Keychain (Recommended)

Once you provide your password, I'll run:

```bash
security add-generic-password \
  -s "OpenClaw" \
  -a "backup-password" \
  -w "YOUR_PASSWORD_HERE" \
  ~/Library/Keychains/login.keychain-db
```

This stores the password securely. Script retrieves it with:
```bash
security find-generic-password -w -s "OpenClaw" -a "backup-password"
```

**Security note:** Keychain password is used for openssl encryption:
```bash
openssl enc -aes-256-cbc -salt -in backup.tar.gz -out backup.tar.gz.enc -k "PASSWORD"
```

The encrypted file is then uploaded to Google Drive. Only you can decrypt it with your password.

---

## Part 3: BACKUP SCRIPT CONFIGURATION

### What the backup script does (nightly at midnight MT):

```
1. Compress ~/.openclaw/workspace/ → workspace_TIMESTAMP.tar.gz
2. Encrypt with openssl + your password → workspace_TIMESTAMP.tar.gz.enc
3. Upload to Google Drive: "OpenClaw Backups" folder
4. Delete backups older than 30 days
5. Log to backup_status.md
6. Send Telegram: filename, size, link
```

### File structure:

```
~/.backups/openclaw/
├── openclaw-workspace_2026-02-21_000000.tar.gz.enc  (encrypted)
├── openclaw-workspace_2026-02-20_000000.tar.gz.enc  (encrypted)
└── ... [last 30 days]

Google Drive/OpenClaw Backups/
├── openclaw-workspace_2026-02-21_000000.tar.gz.enc
├── openclaw-workspace_2026-02-20_000000.tar.gz.enc
└── ... [synced from local]
```

### Restore a backup:

```bash
# List available backups
ls -la ~/.backups/openclaw/

# Decrypt a backup
openssl enc -aes-256-cbc -d -in workspace_2026-02-21_000000.tar.gz.enc -out workspace.tar.gz -k "YOUR_PASSWORD"

# Extract
tar -xzf workspace.tar.gz -C ~

# Verify
ls -la ~/.openclaw/workspace/
```

---

## Part 4: GIT AUTO-SYNC SCRIPT

### What the git-sync script does (nightly at 12:15 AM MT, after backup):

```
1. Scan home directory for all .git repositories
2. For each repo with uncommitted/unpushed changes:
   - git add -A
   - git commit -m "Auto-sync: [timestamp]"
   - git push
3. Log results to backup_status.md
4. Report via Telegram (success/failures)
```

### Repos scanned:

```
~/projects/
~/workspace/
~/code/
~/.openclaw/workspace/
[any folder with .git directory]
```

### What gets synced:

✅ Modified files  
✅ New files  
✅ Deleted files  
⏭️ Uncommitted deletions (only if explicitly added)

### Safety features:

- ⚠️ Stops if conflicts detected (requires manual intervention)
- ⚠️ Reports auth failures (SSH key, credentials)
- ⚠️ Skips repos with no changes
- ⚠️ Logs all failures for manual review

### Example Telegram report:

```
🔄 Git Auto-Sync Report

Timestamp: Feb 21, 2026 12:15 AM MT

Summary:
✅ Success: 3
❌ Failed: 0
⏭️ Skipped (no changes): 12
📊 Total repos scanned: 15

[No failures]
```

---

## Part 5: LAUNCHAGENT SETUP (Automation)

Once you confirm password handling, I'll create two LaunchAgent files:

### 1. Backup LaunchAgent

**File:** `~/Library/LaunchAgents/ai.openclaw.backup.plist`

**Schedule:** Nightly at 00:00 (midnight MT)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>ai.openclaw.backup</string>
  <key>Program</key>
  <string>/usr/local/bin/node</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/node</string>
    <string>/Users/pinchy/.openclaw/workspace/scripts/backup-workspace.mjs</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>0</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardErrorPath</key>
  <string>/Users/pinchy/.openclaw/logs/backup.err</string>
  <key>StandardOutPath</key>
  <string>/Users/pinchy/.openclaw/logs/backup.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HOME</key>
    <string>/Users/pinchy</string>
  </dict>
</dict>
</plist>
```

**Load it:**
```bash
launchctl load ~/Library/LaunchAgents/ai.openclaw.backup.plist
launchctl start ai.openclaw.backup  # Test immediately
```

### 2. Git-Sync LaunchAgent

**File:** `~/Library/LaunchAgents/ai.openclaw.git-sync.plist`

**Schedule:** Nightly at 00:15 (15 min after backup completes)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>ai.openclaw.git-sync</string>
  <key>Program</key>
  <string>/usr/local/bin/node</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/node</string>
    <string>/Users/pinchy/.openclaw/workspace/scripts/git-auto-sync.mjs</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>0</integer>
    <key>Minute</key>
    <integer>15</integer>
  </dict>
  <key>StandardErrorPath</key>
  <string>/Users/pinchy/.openclaw/logs/git-sync.err</string>
  <key>StandardOutPath</key>
  <string>/Users/pinchy/.openclaw/logs/git-sync.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin</string>
    <key>HOME</key>
    <string>/Users/pinchy</string>
  </dict>
</dict>
</plist>
```

**Load it:**
```bash
launchctl load ~/Library/LaunchAgents/ai.openclaw.git-sync.plist
launchctl start ai.openclaw.git-sync  # Test immediately
```

---

## Part 6: LOGGING & MONITORING

### Backup Status Log

**File:** `workspace/backup_status.md`

Updated after every backup and git-sync run with:
- Timestamp
- Status (success/failure)
- File size
- Google Drive link
- Any errors

### Script Logs

**Directory:** `~/.openclaw/logs/`

Created by LaunchAgent:
- `backup.log` — Backup script stdout
- `backup.err` — Backup script errors
- `git-sync.log` — Git-sync script stdout
- `git-sync.err` — Git-sync script errors

**View recent logs:**
```bash
tail -100 ~/.openclaw/logs/backup.log
tail -100 ~/.openclaw/logs/git-sync.log
```

### Telegram Notifications

After each run, you'll receive:
- Backup: Size, timestamp, Google Drive link
- Git-sync: Repos scanned, success count, any failures

---

## Testing Checklist

Once setup is complete:

- [ ] rclone installed: `rclone --version`
- [ ] Google Drive authenticated: `rclone ls google-drive:`
- [ ] Backup folder created: `rclone ls google-drive:"OpenClaw Backups"`
- [ ] Password in Keychain: `security find-generic-password -w -s "OpenClaw" -a "backup-password"`
- [ ] Manual backup test: `node scripts/backup-workspace.mjs`
- [ ] Verify encrypted file: `ls -lah ~/.backups/openclaw/*.enc`
- [ ] Verify Google Drive upload: Check "OpenClaw Backups" folder
- [ ] Manual git-sync test: `node scripts/git-auto-sync.mjs`
- [ ] Check backup_status.md updated
- [ ] LaunchAgents loaded: `launchctl list | grep openclaw`
- [ ] Test Telegram notifications received

---

## Troubleshooting

### rclone: "command not found"
```bash
# Make sure it's installed
brew install rclone

# Check path
which rclone
```

### Google Drive auth fails
```bash
# Re-authenticate
rclone config

# Test connection
rclone ls google-drive:
```

### Backup fails with "Permission denied"
```bash
# Check Keychain access
security find-generic-password -w -s "OpenClaw" -a "backup-password"

# If empty, password not stored correctly
# Run setup again
```

### Git-sync conflicts
```bash
# Manual resolution required
cd [repo-with-conflict]
git status
# Resolve conflicts manually
git add .
git commit -m "Manual conflict resolution"
git push
```

### LaunchAgent not running
```bash
# Check if loaded
launchctl list | grep openclaw

# If not loaded, load it
launchctl load ~/Library/LaunchAgents/ai.openclaw.backup.plist

# Check error logs
tail ~/.openclaw/logs/backup.err
```

---

## Security Considerations

✅ Passwords stored in Keychain (not plaintext files)  
✅ Backups encrypted with AES-256-CBC (military-grade)  
✅ Google Drive files encrypted locally before upload  
✅ Git operations use existing SSH keys  
✅ LaunchAgent runs in user context (no root needed)  
✅ Logs don't contain passwords or credentials  

---

## Next Steps

1. **Confirm password handling approach**
   - Option A: Keychain encryption (recommended)
   - Option B: Environment variable
   - Option C: No encryption

2. **Provide backup password** (one time only)
   - I'll store securely in Keychain
   - Script will retrieve automatically

3. **Install rclone**
   ```bash
   brew install rclone
   ```

4. **Authenticate Google Drive**
   ```bash
   rclone config
   ```

5. **I'll create LaunchAgents** and load them

6. **We'll test both systems** immediately

---

**Status:** Awaiting your password handling preference and backup password.

Ready to proceed? Reply on Telegram with your preference! 🔐
