#!/bin/bash
# Pause all trading (activates kill switch)
cd "$(dirname "$0")/.."
touch .pause
echo "🛑 Trading PAUSED"
echo "All new trade approvals will be blocked."
echo "To resume: run ./scripts/resume_trading.sh"
