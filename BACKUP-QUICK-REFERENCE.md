# Backup & Git Auto-Sync — Quick Reference

## One-Sentence Summary

**Nightly automation that encrypts and backs up your workspace to Google Drive, and auto-syncs all your Git repos.**

---

## The Basics

### What Gets Backed Up?
`~/.openclaw/workspace/` → Compressed, encrypted, uploaded to Google Drive

### What Gets Synced?
All Git repositories in your home directory → Auto-committed and auto-pushed

### When?
- **Backup:** Midnight (00:00 MT) every night
- **Git-sync:** 12:15 AM (00:15 MT) every night
- Both scheduled via macOS LaunchAgent (automatic)

### How Secure?
- Encrypted with AES-256-CBC (military-grade)
- Password stored in macOS Keychain (not files)
- Only you can decrypt
- Google Drive handles cloud security

---

## Key Files

| File | Purpose |
|------|---------|
| `backup_status.md` | Log of all backups and git-syncs |
| `scripts/backup-workspace.mjs` | Does the backup |
| `scripts/git-auto-sync.mjs` | Does the git-sync |
| `BACKUP-SYSTEM-SETUP.md` | Full setup guide |
| `BACKUP-AND-GIT-SYNC-READY.md` | Deployment checklist |

---

## How to Restore

### Decrypt and restore a backup

```bash
# 1. List available backups
ls -la ~/.backups/openclaw/

# 2. Decrypt
openssl enc -aes-256-cbc -d \
  -in ~/.backups/openclaw/backup_FILE_NAME.tar.gz.enc \
  -out workspace.tar.gz

# 3. Extract
tar -xzf workspace.tar.gz -C ~

# 4. Verify
ls -la ~/.openclaw/workspace/
```

### Download from Google Drive

```bash
# 1. List backups on Google Drive
rclone ls google-drive:"OpenClaw Backups"

# 2. Download
rclone copy google-drive:"OpenClaw Backups"/backup_FILE_NAME.tar.gz.enc ~/.backups/openclaw/

# 3. Decrypt and extract (see above)
```

---

## Manual Triggers

### Run backup right now
```bash
node ~/.openclaw/workspace/scripts/backup-workspace.mjs
```

### Run git-sync right now
```bash
node ~/.openclaw/workspace/scripts/git-auto-sync.mjs
```

### Check backup logs
```bash
tail backup_status.md
tail -100 ~/.openclaw/logs/backup.log
```

### Check git-sync logs
```bash
tail -100 ~/.openclaw/logs/git-sync.log
```

---

## Status Check

### Is backup running?
```bash
launchctl list | grep ai.openclaw.backup
```

### Is git-sync running?
```bash
launchctl list | grep ai.openclaw.git-sync
```

### Is rclone connected?
```bash
rclone ls google-drive:"OpenClaw Backups"
```

### Is password in Keychain?
```bash
security find-generic-password -w -s "OpenClaw" -a "backup-password"
```

---

## Notifications

You'll receive Telegram messages:

**After backup (00:10 MT):**
```
✅ Backup Status
Time: Feb 22, 2026 12:05 AM MT
Status: Success
Size: 245.32 MB
File: openclaw-workspace_2026-02-21_000000.tar.gz.enc
Google Drive: [Link]
```

**After git-sync (00:30 MT):**
```
🔄 Git Auto-Sync Report
Repos scanned: 15
✅ Success: 4
❌ Failed: 0
⏭️ Skipped (no changes): 11
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "rclone: command not found" | `brew install rclone` |
| Google Drive auth fails | `rclone config` (re-authenticate) |
| Backup not running | `launchctl start ai.openclaw.backup` |
| Git conflicts | Resolve manually, then git push |
| Keychain access fails | Re-store password: `security add-generic-password ...` |

---

## Maintenance

### Monthly Tasks
- [ ] Review `backup_status.md` for errors
- [ ] Verify backups exist on Google Drive
- [ ] Test restore from a backup

### Quarterly Tasks
- [ ] Update rclone: `brew upgrade rclone`
- [ ] Verify Telegram notifications still working
- [ ] Check disk space: `du -sh ~/.backups/openclaw/`

### Yearly Tasks
- [ ] Rotate backup password (optional)
- [ ] Audit git repos (too many? too few?)
- [ ] Review retention policy (30 days adequate?)

---

## Storage Math

### Backup Size
- Compressed: ~250 MB per backup
- Encrypted: Same size + salt overhead
- 30 days × 250 MB = 7.5 GB local
- Google Drive: Unlimited (free tier has 15GB total)

### Git Repos
- Auto-sync adds ~50-100 MB per year (metadata)
- No storage impact on local machine

---

## Security Overview

✅ Encrypted at rest (AES-256-CBC)  
✅ Password in Keychain (not plaintext)  
✅ Secure in Google Drive (OAuth, no creds stored)  
✅ Git uses existing SSH keys  
✅ Runs as your user (no sudo needed)  
✅ Logs don't contain passwords  

---

## Advanced

### Change backup password
```bash
# Remove old password from Keychain
security delete-generic-password -s "OpenClaw" -a "backup-password"

# Add new password
security add-generic-password \
  -s "OpenClaw" \
  -a "backup-password" \
  -w "NEW_PASSWORD" \
  ~/Library/Keychains/login.keychain-db
```

### Exclude directories from backup
Edit `backup-workspace.mjs`, line: `tar -czf` command
```bash
# Add --exclude flags
tar -czf ... \
  --exclude=node_modules \
  --exclude=.next \
  --exclude=dist
```

### Change backup time
Edit LaunchAgent plist:
```xml
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key>
  <integer>23</integer>  <!-- 11 PM instead -->
  <key>Minute</key>
  <integer>0</integer>
</dict>
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/ai.openclaw.backup.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.backup.plist
```

### List all Google Drive backups
```bash
rclone ls google-drive:"OpenClaw Backups" -R
```

### Download all backups
```bash
rclone copy google-drive:"OpenClaw Backups" ~/.backups/openclaw/ --progress
```

---

## FAQ

**Q: Can I manually backup right now?**  
A: Yes! `node ~/.openclaw/workspace/scripts/backup-workspace.mjs`

**Q: What if backup fails?**  
A: Check `~/.openclaw/logs/backup.err` for error details. Most common: rclone auth expired (re-run `rclone config`)

**Q: Does backup compress first?**  
A: Yes. Compression ratio ~2:1, so 500 MB uncompressed → 250 MB compressed+encrypted

**Q: Can I restore just one file?**  
A: Yes. Decrypt backup, extract tar, grab the file. Or use tar with path filter: `tar -xzf workspace.tar.gz path/to/file`

**Q: What if git-sync fails on a repo?**  
A: Logged to `backup_status.md`. Usually conflicts (requires manual `git pull` + resolve) or auth issues (check SSH keys)

**Q: How long does backup take?**  
A: ~2-5 minutes (compress 500MB + encrypt + upload)

**Q: How long does git-sync take?**  
A: ~30 seconds to 2 minutes (depends on repos + network)

**Q: Can I use a different cloud provider?**  
A: Yes! rclone supports AWS S3, OneDrive, Dropbox, etc. Edit `backup-workspace.mjs` line: `CONFIG.rcloneRemote`

---

## Emergency Recovery

### If your Mac crashes:

1. Get new Mac with same Apple ID
2. Install rclone: `brew install rclone`
3. Authenticate Google Drive: `rclone config` (same account)
4. Download latest backup: `rclone copy google-drive:"OpenClaw Backups"/latest.tar.gz.enc .`
5. Decrypt: `openssl enc -aes-256-cbc -d -in latest.tar.gz.enc -out latest.tar.gz -k "PASSWORD"`
6. Extract: `tar -xzf latest.tar.gz -C ~`
7. You're restored!

---

## Support

Check these files for more info:
- `BACKUP-SYSTEM-SETUP.md` — Full setup guide
- `BACKUP-AND-GIT-SYNC-READY.md` — Deployment checklist
- `backup_status.md` — Historical logs

---

**Last Updated:** February 21, 2026  
**Status:** ✅ Ready to deploy

Questions? Check the full guides or reply on Telegram! 🚀
