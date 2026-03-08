#!/bin/bash
# Daily Screener (All Modes) - Runs at 8:00 AM MT
# Calls nx_screener_production.py (which is now multimode)

cd ~/.openclaw/workspace

# Run all three modes
python3 trading/scripts/nx_screener_production.py --mode all

# Log completion
echo "[$(date)] Daily screener completed" >> trading/logs/daily_screener.log
