#!/bin/bash

# Screener Cron Job - Runs every 15 minutes
# Checks market hours, runs screener, executes candidates

WORKSPACE="/Users/pinchy/.openclaw/workspace"
SCRIPTS_DIR="$WORKSPACE/trading/scripts"
LOG_DIR="$WORKSPACE/trading/logs"
CACHE_DIR="$WORKSPACE/trading/screener_cache"

# Create log directory if needed
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/screener_cron.log"

# Get current time in ET
CURRENT_HOUR=$(date -j -f "%z" "$(date)" "+%H" 2>/dev/null || date "+%H")
CURRENT_MIN=$(date "+%M")

# Check market hours (9:30 AM - 4:00 PM ET, excluding 11:30 AM - 2:00 PM)
# For now, simplified: run if between 9:30 AM and 4:00 PM ET

# Convert to minutes since midnight for easier comparison
CURRENT_TIME_MIN=$((10#$CURRENT_HOUR * 60 + 10#$CURRENT_MIN))

# 9:30 AM = 570 minutes, 11:30 AM = 690, 2:00 PM = 840, 4:00 PM = 960
if [ $CURRENT_TIME_MIN -lt 570 ] || [ $CURRENT_TIME_MIN -gt 960 ]; then
    echo "$(date): Outside market hours. Skipping." >> "$LOG_FILE"
    exit 0
fi

# Skip midday window (11:30 AM - 2:00 PM ET)
if [ $CURRENT_TIME_MIN -ge 690 ] && [ $CURRENT_TIME_MIN -lt 840 ]; then
    echo "$(date): Midday pause (11:30 AM - 2:00 PM). Skipping." >> "$LOG_FILE"
    exit 0
fi

echo "$(date): Running screener cycle..." >> "$LOG_FILE"

# Check if daily snapshot exists
SNAPSHOT_FILE="$CACHE_DIR/daily_snapshot.json"

if [ ! -f "$SNAPSHOT_FILE" ]; then
    echo "$(date): Snapshot missing. Fetching..." >> "$LOG_FILE"
    python3 "$SCRIPTS_DIR/daily_snapshot.py" >> "$LOG_FILE" 2>&1
fi

# Run screener
echo "$(date): Running AMS screener..." >> "$LOG_FILE"
python3 "$SCRIPTS_DIR/screener_from_snapshot.py" >> "$LOG_FILE" 2>&1

# Execute candidates (DUAL: both swing trades and options)
echo "$(date): Executing candidates (swing + options)..." >> "$LOG_FILE"
python3 "$SCRIPTS_DIR/dual_executor.py" >> "$LOG_FILE" 2>&1

echo "$(date): Screener cycle complete" >> "$LOG_FILE"
