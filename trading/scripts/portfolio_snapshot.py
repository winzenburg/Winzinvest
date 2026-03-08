#!/usr/bin/env python3
"""
Save current portfolio and account summary to trading/portfolio.json.

Run on demand or at EOD. Uses IB clientId=105. Summary includes
short_notional, long_notional, net_liquidation, and per-position list.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ib_insync import IB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "portfolio_snapshot.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from paths import TRADING_DIR
PORTFOLIO_JSON = TRADING_DIR / "portfolio.json"


def _serialize_position(item: Any) -> Dict[str, Any]:
    """Build a JSON-serializable dict from a portfolio item."""
    contract = getattr(item, "contract", None)
    symbol = getattr(contract, "symbol", "") if contract else ""
    sec_type = getattr(contract, "secType", "") if contract else ""
    position = getattr(item, "position", 0)
    try:
        pos_int = int(position)
    except (TypeError, ValueError):
        pos_int = 0
    try:
        mv = float(getattr(item, "marketValue", 0) or 0)
    except (TypeError, ValueError):
        mv = 0.0
    try:
        mp = float(getattr(item, "marketPrice", 0) or 0)
    except (TypeError, ValueError):
        mp = 0.0
    return {
        "symbol": str(symbol),
        "secType": str(sec_type),
        "position": pos_int,
        "marketValue": round(mv, 2),
        "marketPrice": round(mp, 2),
    }


def _get_account_summary(ib: IB) -> Dict[str, float]:
    """Fetch NetLiquidation and TotalCashValue from account summary."""
    out: Dict[str, float] = {}
    try:
        for av in ib.accountValues():
            if av.tag in ("NetLiquidation", "TotalCashValue", "GrossPositionValue") and av.currency == "USD":
                try:
                    out[av.tag] = float(av.value)
                except (TypeError, ValueError):
                    pass
    except Exception as e:
        logger.warning("Could not fetch account summary: %s", e)
    return out


async def run() -> bool:
    """Connect to IB, build snapshot, write portfolio.json."""
    logger.info("=== PORTFOLIO SNAPSHOT ===")
    ib = IB()
    try:
        await ib.connectAsync("127.0.0.1", 4002, clientId=105)
    except Exception as e:
        logger.error("Connection failed: %s", e)
        return False

    try:
        positions: List[Dict[str, Any]] = []
        short_notional = 0.0
        long_notional = 0.0
        try:
            for item in ib.portfolio():
                positions.append(_serialize_position(item))
                pos = getattr(item, "position", 0)
                val = getattr(item, "marketValue", 0) or 0
                try:
                    v = float(val)
                except (TypeError, ValueError):
                    continue
                if pos < 0:
                    short_notional += abs(v)
                elif pos > 0:
                    long_notional += v
        except Exception as e:
            logger.warning("Could not read portfolio: %s", e)

        account = _get_account_summary(ib)
        net_liquidation = account.get("NetLiquidation") or account.get("TotalCashValue")

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "short_notional": round(short_notional, 2),
                "long_notional": round(long_notional, 2),
                "net_liquidation": round(net_liquidation, 2) if net_liquidation is not None else None,
                "total_cash_value": round(account.get("TotalCashValue", 0), 2) if account.get("TotalCashValue") is not None else None,
            },
            "positions": positions,
        }

        TRADING_DIR.mkdir(parents=True, exist_ok=True)
        PORTFOLIO_JSON.write_text(json.dumps(snapshot, indent=2))
        logger.info("Wrote %s (positions=%d, short=%.2f long=%.2f)", PORTFOLIO_JSON, len(positions), short_notional, long_notional)
        return True
    finally:
        ib.disconnect()


if __name__ == "__main__":
    import sys
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
