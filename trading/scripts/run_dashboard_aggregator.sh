#!/bin/bash
# Run dashboard data aggregator
# Add to crontab: */5 * * * * /path/to/run_dashboard_aggregator.sh

cd "$(dirname "$0")"
PYTHONPATH="." python3 dashboard_data_aggregator.py >> ../logs/dashboard_aggregator.log 2>&1
