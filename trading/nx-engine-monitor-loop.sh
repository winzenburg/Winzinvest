#!/bin/bash
# NX Trade Engine Monitor Loop
# Runs every 5 minutes during trading hours (7:30 AM - 2:00 PM MT, Mon-Fri)

SCRIPT="/Users/pinchy/.openclaw/workspace/trading/nx-engine-monitor-v2.mjs"
LOG="/Users/pinchy/.openclaw/workspace/logs/nx-engine-monitor-loop.log"

echo "$(date): NX Trade Engine Monitor Loop starting..." >> $LOG

while true; do
  # Get current time
  HOUR=$(date +%H)
  MIN=$(date +%M)
  DOW=$(date +%u)  # 1-7 (Monday-Sunday)
  
  # Check if within trading hours (7:30 AM - 2:00 PM MT) and Mon-Fri
  if [ $DOW -ge 1 ] && [ $DOW -le 5 ]; then
    if [ $HOUR -ge 7 ] && [ $HOUR -le 14 ]; then
      # Skip 7:00-7:29 (before market open)
      if [ $HOUR -eq 7 ] && [ $MIN -lt 30 ]; then
        echo "$(date): Before market open. Skipping..." >> $LOG
      else
        echo "$(date): Running monitor..." >> $LOG
        node $SCRIPT >> $LOG 2>&1
      fi
    else
      echo "$(date): Outside trading hours. Sleeping..." >> $LOG
    fi
  else
    echo "$(date): Weekend. Sleeping..." >> $LOG
  fi
  
  # Sleep 5 minutes
  sleep 300
done
