#!/usr/bin/env python3
"""
Save current portfolio and account summary to trading/portfolio.json.

Run on demand or at EOD. Uses IB clientId=111 (fallback 112, 113). Summary includes
short_notional, long_notional, net_liquidation, and per-position list.
"""

import asyncio
import json
import logging
import os
import tempfile
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

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))

PORTFOLIO_JSON = TRADING_DIR / "portfolio.json"


def _option_description(contract: Any) -> str:
    """Build a short description e.g. AAPL Mar26 230 P from option contract."""
    if not contract or getattr(contract, "secType", "") != "OPT":
        return ""
    sym = getattr(contract, "symbol", "") or ""
    exp = getattr(contract, "lastTradeDateOrContractMonth", "") or ""
    strike = getattr(contract, "strike", 0) or 0
    right = getattr(contract, "right", "") or ""
    if exp and len(exp) >= 6:
        try:
            y = exp[:4]
            m = int(exp[4:6])
            months = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
            exp_str = f"{months[m - 1]}{y[2:]}" if 1 <= m <= 12 else exp
        except (ValueError, IndexError):
            exp_str = exp
    else:
        exp_str = exp
    return f"{sym} {exp_str} {strike} {right}".strip()


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
    try:
        avg_cost = round(float(getattr(item, "averageCost", 0) or 0), 4)
    except (TypeError, ValueError):
        avg_cost = 0.0
    try:
        unrealized_pnl = round(float(getattr(item, "unrealizedPNL", 0) or 0), 2)
    except (TypeError, ValueError):
        unrealized_pnl = 0.0
    try:
        realized_pnl = round(float(getattr(item, "realizedPNL", 0) or 0), 2)
    except (TypeError, ValueError):
        realized_pnl = 0.0

    out: Dict[str, Any] = {
        "symbol": str(symbol),
        "secType": str(sec_type),
        "position": pos_int,
        "marketValue": round(mv, 2),
        "marketPrice": round(mp, 2),
        "averageCost": avg_cost,
        "unrealizedPNL": unrealized_pnl,
        "realizedPNL": realized_pnl,
    }
    if str(sec_type).upper() == "OPT":
        out["description"] = _option_description(contract)
        out["localSymbol"] = str(getattr(contract, "localSymbol", "") or "")
    return out


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
    connected = False
    for client_id in (111, 112, 113, 114, 115, 116, 117, 118, 119):
        try:
            await ib.connectAsync(IB_HOST, IB_PORT, clientId=client_id, timeout=15)
            logger.info("Connected with clientId=%s", client_id)
            connected = True
            break
        except (asyncio.TimeoutError, Exception) as e:
            if ib.isConnected():
                logger.warning(
                    "ClientId %s: sync timed out but TCP connected — proceeding with available data",
                    client_id,
                )
                connected = True
                break
            if ib.client and getattr(ib.client, '_socket', None):
                ib.disconnect()
            logger.warning("ClientId %s failed: %s, trying next...", client_id, e)
    if not connected:
        logger.error("Connection failed with all client ids")
        return False

    try:
        positions: List[Dict[str, Any]] = []
        short_notional = 0.0
        long_notional = 0.0

        # Allow IB to push portfolio/account data (streams automatically after connect)
        await asyncio.sleep(3)

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

        # Sanity check: if we got zero positions AND no NLV, the sync likely didn't
        # complete — skip writing to avoid overwriting a good snapshot with empty data
        if not positions and net_liquidation is None:
            logger.error(
                "Aborting snapshot write: zero positions and no NLV — IB sync likely incomplete"
            )
            return False

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
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=str(TRADING_DIR))
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(snapshot, f, indent=2)
            os.replace(tmp_path, str(PORTFOLIO_JSON))
        except OSError:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        logger.info("Wrote %s (positions=%d, short=%.2f long=%.2f)", PORTFOLIO_JSON, len(positions), short_notional, long_notional)
        return True
    finally:
        ib.disconnect()


if __name__ == "__main__":
    import sys
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
