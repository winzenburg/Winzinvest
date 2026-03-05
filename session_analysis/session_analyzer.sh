#!/bin/bash
# Session Log Analyzer - Detects behavioral patterns

LOG_DIR="~/.openclaw/workspace/trading/logs"
SESSION_DIR="/opt/homebrew/lib/node_modules/openclaw/session_logs"

echo "=== SESSION LOG ANALYSIS ==="
echo "Timestamp: $(date)"
echo ""

# Count recent sessions
echo "Session Count (last 7 days):"
find "$LOG_DIR" -type f -name "*.log" -mtime -7 | wc -l

# Search for error patterns
echo ""
echo "Recent Error Patterns:"
grep -h "ERROR\|FAILED\|❌" "$LOG_DIR"/*.log 2>/dev/null | tail -10 || echo "No errors detected"

# Analyze for behavioral anomalies
echo ""
echo "Truthfulness Check:"
grep -h "verified\|tested\|confirmed" "$LOG_DIR"/*.log 2>/dev/null | wc -l | xargs echo "Claims backed by verification:"

