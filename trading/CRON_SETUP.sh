#!/bin/bash
# Cron Job Setup for Trade Reconciliation System
# This script sets up daily reconciliation and backup jobs

# Configuration
WORKSPACE="/Users/pinchy/.openclaw/workspace"
TRADING_DIR="$WORKSPACE/trading"
LOGS_DIR="$TRADING_DIR/logs"
RECONCILIATION_HOUR="20"  # 8 PM
BACKUP_HOUR="21"          # 9 PM

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "Trade Reconciliation System - Cron Setup"
echo "=================================================="

# Check if running on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected: macOS (using launchd)"
    PLATFORM="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected: Linux (using crontab)"
    PLATFORM="linux"
else
    echo "Unknown OS: $OSTYPE"
    exit 1
fi

echo ""
echo "Workspace: $WORKSPACE"
echo "Platform: $PLATFORM"
echo ""

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"
echo "✅ Logs directory ready: $LOGS_DIR"

# ============================================================
# Setup for macOS (launchd)
# ============================================================

if [[ "$PLATFORM" == "macos" ]]; then
    
    # Create launch agent directory
    mkdir -p ~/Library/LaunchAgents
    
    # Create daily reconciliation job
    echo ""
    echo "Creating launchd job: Daily Reconciliation @ 8:00 PM..."
    
    cat > ~/Library/LaunchAgents/com.trading.daily-reconciliation.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.daily-reconciliation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/pinchy/.openclaw/workspace/trading/daily_reconciliation.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>20</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/cron_reconciliation.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/cron_reconciliation.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

    if [ -f ~/Library/LaunchAgents/com.trading.daily-reconciliation.plist ]; then
        echo -e "${GREEN}✅ Created reconciliation launchd job${NC}"
        launchctl load ~/Library/LaunchAgents/com.trading.daily-reconciliation.plist 2>/dev/null || launchctl unload ~/Library/LaunchAgents/com.trading.daily-reconciliation.plist 2>/dev/null; launchctl load ~/Library/LaunchAgents/com.trading.daily-reconciliation.plist
        echo -e "${GREEN}✅ Loaded reconciliation job${NC}"
    else
        echo -e "${RED}❌ Failed to create reconciliation job${NC}"
        exit 1
    fi
    
    # Create daily backup job
    echo ""
    echo "Creating launchd job: Daily Backup @ 9:00 PM..."
    
    cat > ~/Library/LaunchAgents/com.trading.daily-backup.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.daily-backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/pinchy/.openclaw/workspace/trading/cloud_backup.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>21</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/cron_backup.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/cron_backup.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

    if [ -f ~/Library/LaunchAgents/com.trading.daily-backup.plist ]; then
        echo -e "${GREEN}✅ Created backup launchd job${NC}"
        launchctl load ~/Library/LaunchAgents/com.trading.daily-backup.plist 2>/dev/null || launchctl unload ~/Library/LaunchAgents/com.trading.daily-backup.plist 2>/dev/null; launchctl load ~/Library/LaunchAgents/com.trading.daily-backup.plist
        echo -e "${GREEN}✅ Loaded backup job${NC}"
    else
        echo -e "${RED}❌ Failed to create backup job${NC}"
        exit 1
    fi

fi

# ============================================================
# Setup for Linux (crontab)
# ============================================================

if [[ "$PLATFORM" == "linux" ]]; then
    
    echo ""
    echo "Adding cron jobs..."
    
    # Check if cron jobs already exist
    if crontab -l 2>/dev/null | grep -q "daily_reconciliation.py"; then
        echo -e "${YELLOW}⚠️  Reconciliation job already in crontab${NC}"
    else
        # Add daily reconciliation job
        (crontab -l 2>/dev/null || echo ""; echo "0 $RECONCILIATION_HOUR * * * cd $WORKSPACE && /usr/bin/python3 trading/daily_reconciliation.py >> trading/logs/cron_reconciliation.log 2>&1") | crontab -
        echo -e "${GREEN}✅ Added reconciliation job (8:00 PM)${NC}"
    fi
    
    if crontab -l 2>/dev/null | grep -q "cloud_backup.py"; then
        echo -e "${YELLOW}⚠️  Backup job already in crontab${NC}"
    else
        # Add daily backup job
        (crontab -l 2>/dev/null || echo ""; echo "0 $BACKUP_HOUR * * * cd $WORKSPACE && /usr/bin/python3 trading/cloud_backup.py >> trading/logs/cron_backup.log 2>&1") | crontab -
        echo -e "${GREEN}✅ Added backup job (9:00 PM)${NC}"
    fi

fi

# ============================================================
# Verification
# ============================================================

echo ""
echo "=================================================="
echo "Verification"
echo "=================================================="

if [[ "$PLATFORM" == "macos" ]]; then
    echo "Checking launchd jobs..."
    echo ""
    
    if launchctl list | grep -q "com.trading.daily-reconciliation"; then
        echo -e "${GREEN}✅ Daily reconciliation job is loaded${NC}"
    else
        echo -e "${RED}❌ Daily reconciliation job is NOT loaded${NC}"
    fi
    
    if launchctl list | grep -q "com.trading.daily-backup"; then
        echo -e "${GREEN}✅ Daily backup job is loaded${NC}"
    else
        echo -e "${RED}❌ Daily backup job is NOT loaded${NC}"
    fi
    
    echo ""
    echo "Job files:"
    ls -lh ~/Library/LaunchAgents/com.trading.* 2>/dev/null
    
elif [[ "$PLATFORM" == "linux" ]]; then
    echo "Cron jobs:"
    echo ""
    crontab -l | grep trading
fi

# ============================================================
# Next Steps
# ============================================================

echo ""
echo "=================================================="
echo "Next Steps"
echo "=================================================="
echo ""
echo "1. Monitor the logs:"
echo "   tail -f $LOGS_DIR/cron_reconciliation.log"
echo "   tail -f $LOGS_DIR/cron_backup.log"
echo ""
echo "2. Test the jobs manually:"
echo "   python3 $TRADING_DIR/daily_reconciliation.py"
echo "   python3 $TRADING_DIR/cloud_backup.py"
echo ""
echo "3. Verify integration with trading system:"
echo "   python3 $TRADING_DIR/test_integration.py"
echo ""
echo "4. For help, see:"
echo "   - DISASTER_RECOVERY_RUNBOOK.md"
echo "   - INTEGRATION_PATCHES.md"
echo ""

if [[ "$PLATFORM" == "macos" ]]; then
    echo "5. To remove jobs later:"
    echo "   launchctl unload ~/Library/LaunchAgents/com.trading.daily-reconciliation.plist"
    echo "   launchctl unload ~/Library/LaunchAgents/com.trading.daily-backup.plist"
fi

echo ""
echo -e "${GREEN}✅ Cron setup complete!${NC}"
