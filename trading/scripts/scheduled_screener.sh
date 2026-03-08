#!/bin/bash

# Scheduled screener runner
# This script:
# 1. Checks if daily snapshot exists
# 2. If not, fetches it
# 3. Runs AMS screener
# 4. Executes candidates

WORKSPACE="/Users/pinchy/.openclaw/workspace"
SCRIPTS_DIR="$WORKSPACE/trading/scripts"
LOG_DIR="$WORKSPACE/trading/logs"
CACHE_DIR="$WORKSPACE/trading/screener_cache"
SNAPSHOT_FILE="$CACHE_DIR/daily_snapshot.json"

# Ensure directories exist
mkdir -p "$LOG_DIR" "$CACHE_DIR"

# Check if snapshot exists and is today's date
check_snapshot() {
    if [ ! -f "$SNAPSHOT_FILE" ]; then
        return 1
    fi
    
    # Check if file was created today
    file_date=$(stat -f "%Sm" -t "%Y%m%d" "$SNAPSHOT_FILE")
    today_date=$(date +"%Y%m%d")
    
    if [ "$file_date" != "$today_date" ]; then
        return 1
    fi
    
    return 0
}

# Fetch daily snapshot if needed
if ! check_snapshot; then
    echo "$(date): Fetching daily IBKR snapshot..."
    python3 "$SCRIPTS_DIR/daily_snapshot.py" >> "$LOG_DIR/scheduled_screener.log" 2>&1
fi

# Run screener
echo "$(date): Running AMS screener..."
python3 "$SCRIPTS_DIR/screener_from_snapshot.py" >> "$LOG_DIR/scheduled_screener.log" 2>&1

# Execute candidates (if needed)
# python3 "$SCRIPTS_DIR/execute_candidates.py" >> "$LOG_DIR/scheduled_screener.log" 2>&1

echo "$(date): Screener cycle complete"
