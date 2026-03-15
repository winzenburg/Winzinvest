#!/bin/bash
# Mission Control - Autonomous Trading Setup
# Sets up background service for automated trading

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
WORKSPACE="/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control"
TRADING_DIR="$WORKSPACE/trading"
SCRIPTS_DIR="$TRADING_DIR/scripts"
LOGS_DIR="$TRADING_DIR/logs"
LAUNCHAGENTS_DIR="$HOME/Library/LaunchAgents"

echo "=================================================="
echo "Mission Control - Autonomous Trading Setup"
echo "=================================================="
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}❌ This script is for macOS only${NC}"
    exit 1
fi

echo -e "${BLUE}Workspace: $WORKSPACE${NC}"
echo -e "${BLUE}Scripts: $SCRIPTS_DIR${NC}"
echo -e "${BLUE}Logs: $LOGS_DIR${NC}"
echo ""

# Create logs directory
mkdir -p "$LOGS_DIR"
echo -e "${GREEN}✅ Logs directory ready${NC}"

# Create LaunchAgents directory
mkdir -p "$LAUNCHAGENTS_DIR"
echo -e "${GREEN}✅ LaunchAgents directory ready${NC}"
echo ""

# ============================================================
# Create Mission Control Scheduler Service
# ============================================================

echo "=================================================="
echo "Creating Mission Control Scheduler Service"
echo "=================================================="
echo ""

SERVICE_FILE="$LAUNCHAGENTS_DIR/com.missioncontrol.scheduler.plist"

cat > "$SERVICE_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.missioncontrol.scheduler</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPTS_DIR/scheduler.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>$SCRIPTS_DIR</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>StandardOutPath</key>
    <string>$LOGS_DIR/scheduler.log</string>
    
    <key>StandardErrorPath</key>
    <string>$LOGS_DIR/scheduler.err</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>PYTHONPATH</key>
        <string>$SCRIPTS_DIR</string>
    </dict>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

if [ -f "$SERVICE_FILE" ]; then
    echo -e "${GREEN}✅ Created scheduler service file${NC}"
else
    echo -e "${RED}❌ Failed to create service file${NC}"
    exit 1
fi

# ============================================================
# Load the Service
# ============================================================

echo ""
echo "=================================================="
echo "Loading Service"
echo "=================================================="
echo ""

# Unload if already loaded (in case of re-run)
launchctl unload "$SERVICE_FILE" 2>/dev/null || true
sleep 1

# Load the service
if launchctl load "$SERVICE_FILE"; then
    echo -e "${GREEN}✅ Service loaded successfully${NC}"
else
    echo -e "${RED}❌ Failed to load service${NC}"
    exit 1
fi

sleep 2

# ============================================================
# Verify Service is Running
# ============================================================

echo ""
echo "=================================================="
echo "Verification"
echo "=================================================="
echo ""

if launchctl list | grep -q "com.missioncontrol.scheduler"; then
    echo -e "${GREEN}✅ Mission Control scheduler is running${NC}"
    
    # Get PID
    PID=$(launchctl list | grep "com.missioncontrol.scheduler" | awk '{print $1}')
    if [ "$PID" != "-" ]; then
        echo -e "${GREEN}   PID: $PID${NC}"
    fi
else
    echo -e "${RED}❌ Service is NOT running${NC}"
    echo ""
    echo "Check error log:"
    echo "  tail -50 $LOGS_DIR/scheduler.err"
    exit 1
fi

# ============================================================
# Service Information
# ============================================================

echo ""
echo "=================================================="
echo "Service Information"
echo "=================================================="
echo ""
echo "Service Name: com.missioncontrol.scheduler"
echo "Service File: $SERVICE_FILE"
echo "Working Dir:  $SCRIPTS_DIR"
echo "Logs:"
echo "  Output: $LOGS_DIR/scheduler.log"
echo "  Errors: $LOGS_DIR/scheduler.err"
echo ""

# ============================================================
# Trading Schedule
# ============================================================

echo "=================================================="
echo "Trading Schedule (Mountain Time)"
echo "=================================================="
echo ""
echo "07:00 - Pre-market: Sync positions, run screeners"
echo "07:30 - Market open: Execute trades"
echo "08:00 - Mid-morning: Options executor"
echo "10:00 - Midday: Re-run screeners"
echo "10:15 - Midday: Re-run executors"
echo "12:00 - Afternoon: Options/pairs check"
echo "14:00 - Pre-close: Portfolio snapshot"
echo "14:30 - Post-close: Analytics"
echo "Every 60s: Risk monitoring"
echo ""

# ============================================================
# Management Commands
# ============================================================

echo "=================================================="
echo "Service Management Commands"
echo "=================================================="
echo ""
echo "View logs (live):"
echo "  tail -f $LOGS_DIR/scheduler.log"
echo ""
echo "View errors:"
echo "  tail -f $LOGS_DIR/scheduler.err"
echo ""
echo "Check service status:"
echo "  launchctl list | grep missioncontrol"
echo ""
echo "Stop service:"
echo "  launchctl unload $SERVICE_FILE"
echo ""
echo "Start service:"
echo "  launchctl load $SERVICE_FILE"
echo ""
echo "Restart service:"
echo "  launchctl unload $SERVICE_FILE && launchctl load $SERVICE_FILE"
echo ""
echo "Remove service completely:"
echo "  launchctl unload $SERVICE_FILE"
echo "  rm $SERVICE_FILE"
echo ""

# ============================================================
# Pre-Flight Checklist
# ============================================================

echo "=================================================="
echo "⚠️  PRE-FLIGHT CHECKLIST"
echo "=================================================="
echo ""
echo "Before Monday, make sure:"
echo ""
echo "[ ] 1. TWS or IB Gateway is running"
echo "[ ] 2. API permissions enabled in TWS/Gateway"
echo "[ ] 3. Correct account selected (paper vs live)"
echo "[ ] 4. Risk limits reviewed in trading/risk.json"
echo "[ ] 5. Test scripts manually first:"
echo "        cd $SCRIPTS_DIR"
echo "        python3 nx_screener_production.py --mode all"
echo "        python3 execute_mean_reversion.py"
echo "[ ] 6. Monitor logs on Monday morning"
echo "[ ] 7. Have kill switch ready (launchctl unload)"
echo ""

# ============================================================
# Quick Test
# ============================================================

echo "=================================================="
echo "Quick Test (Optional)"
echo "=================================================="
echo ""
echo "To test the scheduler now (dry-run mode):"
echo "  cd $SCRIPTS_DIR"
echo "  python3 scheduler.py --dry-run"
echo ""
echo "To test screeners manually:"
echo "  cd $SCRIPTS_DIR"
echo "  python3 nx_screener_production.py --mode all"
echo ""

# ============================================================
# Success
# ============================================================

echo "=================================================="
echo -e "${GREEN}✅ SETUP COMPLETE!${NC}"
echo "=================================================="
echo ""
echo "Mission Control is now running as a background service."
echo "It will:"
echo "  - Start automatically on boot"
echo "  - Run trading schedule during market hours"
echo "  - Restart automatically if it crashes"
echo "  - Log all activity to $LOGS_DIR"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Test everything manually before Monday!${NC}"
echo ""
echo "Next steps:"
echo "  1. Monitor logs: tail -f $LOGS_DIR/scheduler.log"
echo "  2. Test manually: cd $SCRIPTS_DIR && python3 scheduler.py --dry-run"
echo "  3. Verify IBKR connection"
echo "  4. Review risk limits"
echo ""
echo -e "${GREEN}Good luck trading! 📈${NC}"
echo ""
