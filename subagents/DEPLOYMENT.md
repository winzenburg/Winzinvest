# Subagent Deployment Guide

**Status**: Ready to Deploy  
**Created**: February 25, 2026  
**First Run Target**: GROUP 1 (Trading) — 8:00 AM MT

---

## Quick Start

### 1. Verify Prerequisites

```bash
# Check Ollama models are loaded
ollama list

# Expected output:
# qwen2.5:7b        4.7 GB   ✅
# llama3.1:8b       4.9 GB   ✅
# deepseek-coder:6.7b 3.8 GB ✅
```

### 2. Make Scripts Executable

```bash
chmod +x ~/.openclaw/scripts/group-*.sh
```

### 3. Create Cron Jobs (macOS)

```bash
# Create launch agents directory
mkdir -p ~/Library/LaunchAgents

# Copy this to ~/Library/LaunchAgents/com.openclaw.group1-scout.plist
cat > ~/Library/LaunchAgents/com.openclaw.group1-scout.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.group1-scout</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/pinchy/.openclaw/scripts/group-1-scout.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>14</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
    <key>StandardOutPath</key>
    <string>/tmp/group1-scout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/group1-scout.log</string>
</dict>
</plist>
EOF

# Load the launch agent
launchctl load ~/Library/LaunchAgents/com.openclaw.group1-scout.plist

# Verify it's loaded
launchctl list | grep group1-scout
```

### 4. Test GROUP 1 Manually

```bash
# Run the scout script directly
/Users/pinchy/.openclaw/scripts/group-1-scout.sh

# Check the output
cat /tmp/group1-scout-output.json

# Check the log
tail -20 /tmp/group1-scout.log
```

### 5. Monitor First Run

- **Expected completion**: < 2 minutes per scout
- **Expected cost**: $0.00 (local qwen2.5:7b only)
- **Success indicator**: `/tmp/group1-scout-output.json` contains valid JSON with findings, assumptions, risks, next_checks

---

## GROUP 2 & 3 Deployment (When Ready)

Once GROUP 1 is stable for 1 week:

### GROUP 2 (SAAS Metrics)

```bash
# Create scripts (stub for now)
touch ~/.openclaw/scripts/group-2-scout.sh
chmod +x ~/.openclaw/scripts/group-2-scout.sh

# Add launchctl entry for Mon/Wed/Fri 10:00 AM
# (See GROUP 1 example above for structure)
```

### GROUP 3 (Personal Brand)

```bash
# Create scripts (stub for now)
touch ~/.openclaw/scripts/group-3-scout.sh
chmod +x ~/.openclaw/scripts/group-3-scout.sh

# Add launchctl entry for Tue/Thu 3:00 PM
```

---

## Troubleshooting

| Issue | Diagnosis | Fix |
|-------|-----------|-----|
| Scout script not running | Check `launchctl list` | Reload with `launchctl load` |
| "Ollama not responding" | Ollama daemon down | `brew services restart ollama` |
| Invalid JSON output | Scout hallucination or timeout | Retry next cycle; check Ollama memory |
| Lock file stuck | Previous run crashed | `rm /tmp/group-*.lock` |
| High cost escalations | Too many Sonnet calls | Check scout confidence thresholds |

---

## Weekly Review

Every Friday 2:00 PM MT:

1. Check logs: `tail -100 /tmp/group1-scout.log`
2. Review cost: `grep "cost:" /tmp/group1-scout.log | tail -10`
3. Check escalations: `grep "Escalat" /tmp/group1-scout.log`
4. Update MEMORY.md with metrics

---

## Files Reference

| File | Purpose |
|------|---------|
| `GROUP_1_TRADING.md` | Trading scout specifications |
| `GROUP_2_SAAS.md` | SaaS metrics scout specifications |
| `GROUP_3_BRAND.md` | Personal brand scout specifications |
| `ORCHESTRATOR.md` | Overall architecture + safety constraints |
| `~/.openclaw/scripts/group-1-scout.sh` | GROUP 1 execution script |
| `DEPLOYMENT.md` | This file (deployment instructions) |

---

## Cost Tracking

**Monthly Budget**: $200  
**Alert Threshold**: $160 (80%)

Track weekly in `/tmp/group-cost-summary.txt`:

```
Week of Feb 24, 2026
GROUP 1: 2 runs x $0.00 = $0.00
GROUP 2: 0 runs
GROUP 3: 0 runs
Total: $0.00 / $200
Status: 🟢 Green
```

