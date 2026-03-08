#!/usr/bin/env python3
"""
EOD flow: run portfolio snapshot, then daily P&L report.

Run at or after market close (e.g. cron). Optional: add cancel unfilled
orders and/or git commit of portfolio + report (not implemented by default).
"""

import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent


def main() -> int:
    logger.info("=== EOD FLOW ===")
    # 1. Snapshot current portfolio (requires IB Gateway/TWS running)
    r1 = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "portfolio_snapshot.py")],
        cwd=SCRIPTS_DIR,
    )
    if r1.returncode != 0:
        logger.error("Portfolio snapshot failed (exit %d)", r1.returncode)
        return r1.returncode
    # 2. Generate daily report (compares to portfolio_previous.json, then copies current → previous)
    r2 = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "daily_report.py")],
        cwd=SCRIPTS_DIR,
    )
    if r2.returncode != 0:
        logger.error("Daily report failed (exit %d)", r2.returncode)
        return r2.returncode
    logger.info("EOD flow complete: snapshot + report")
    # Optional (uncomment or add when needed):
    # - Cancel unfilled stop/TP orders via IB
    # - git add trading/portfolio.json trading/portfolio_previous.json trading/logs/daily_report_*.md && git commit -m "EOD snapshot and report"
    return 0


if __name__ == "__main__":
    sys.exit(main())
