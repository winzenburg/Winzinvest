#!/usr/bin/env python3
"""
Overnight SOD capture — set start-of-day equity at overnight market open (4:00 AM ET).

Runs at 2:00 AM MT (4:00 AM ET) so daily P&L includes overnight moves.
Reads NLV from portfolio.json (written by portfolio_snapshot.py) and updates
sod_equity.json + daily_loss.json. Run portfolio_snapshot.py first to ensure
fresh data from IB.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "overnight_sod_capture.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / "logs"
PORTFOLIO_JSON = TRADING_DIR / "portfolio.json"
SOD_EQUITY_FILE = LOGS_DIR / "sod_equity.json"
DAILY_LOSS_FILE = LOGS_DIR / "daily_loss.json"


def capture_overnight_sod() -> bool:
    """Read NLV from portfolio.json and set SOD equity for the day."""
    if not PORTFOLIO_JSON.exists():
        logger.warning("portfolio.json not found — run portfolio_snapshot.py first")
        return False

    try:
        data = json.loads(PORTFOLIO_JSON.read_text())
    except (OSError, ValueError) as e:
        logger.error("Failed to read portfolio.json: %s", e)
        return False

    summary = data.get("summary") or {}
    nlv = summary.get("net_liquidation")
    if nlv is None:
        logger.warning("portfolio.json has no net_liquidation")
        return False

    try:
        equity = float(nlv)
    except (TypeError, ValueError):
        logger.error("Invalid net_liquidation: %s", nlv)
        return False

    if equity <= 0:
        logger.warning("Net liquidation is non-positive (%.2f) — skipping SOD capture", equity)
        return False

    today = datetime.now().date().isoformat()
    now = datetime.now().isoformat()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    sod_record = {
        "equity": round(equity, 2),
        "date": today,
        "account": "",
        "updated_at": now,
    }
    try:
        SOD_EQUITY_FILE.write_text(json.dumps(sod_record, indent=2))
        logger.info("SOD equity set to %.2f at overnight open (4:00 AM ET)", equity)
    except OSError as e:
        logger.error("Failed to write sod_equity.json: %s", e)
        return False

    daily_loss_record = {
        "date": today,
        "loss": 0.0,
        "sod_equity": round(equity, 2),
        "current_equity": round(equity, 2),
        "updated_at": now,
    }
    try:
        DAILY_LOSS_FILE.write_text(json.dumps(daily_loss_record, indent=2))
        logger.info("daily_loss.json updated — daily P&L will include overnight moves")
    except OSError as e:
        logger.error("Failed to write daily_loss.json: %s", e)
        return False

    return True


if __name__ == "__main__":
    success = capture_overnight_sod()
    exit(0 if success else 1)
