#!/bin/bash
# Wrapper script to send daily portfolio report
# Loads environment and runs Python script

source ~/.openclaw/workspace/trading/.env

cd ~/.openclaw/workspace/trading

python3 scripts/daily_portfolio_report.py

exit $?
