#!/usr/bin/env python3
"""
Sync current short symbols to current_short_symbols.json for position filtering.

This is the "sync positions" step referenced in position_filter.py. Run before
nx_screener_production.py (or on a schedule) so the screener and executors
exclude existing shorts. Schema: {"symbols": ["AAPL", ...], "updated_at": "<iso>"}.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _trading_dir() -> Path:
    """Resolve trading directory from centralized paths config."""
    from paths import TRADING_DIR
    return TRADING_DIR


def _symbols_from_ib(host: str, port: int, client_id: int) -> set[str]:
    """Collect short stock symbols from IB positions. Returns empty set on failure."""
    try:
        from ib_insync import IB
    except ImportError:
        logger.debug("ib_insync not available")
        return set()
    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id, timeout=10)
    except Exception as e:
        logger.warning("IB connection failed: %s", e)
        return set()
    out: set[str] = set()
    try:
        for pos in ib.positions():
            contract = getattr(pos, "contract", None)
            position = getattr(pos, "position", 0)
            if contract is None:
                continue
            if getattr(contract, "secType", "") != "STK":
                continue
            if isinstance(position, (int, float)) and position < 0:
                symbol = getattr(contract, "symbol", "")
                if isinstance(symbol, str) and symbol.strip():
                    out.add(symbol.strip().upper())
    finally:
        try:
            ib.disconnect()
        except Exception:
            pass
    return out


def _symbols_from_log(log_path: Path) -> set[str]:
    """Collect symbols from SELL entries in append-only JSON-lines execution log."""
    out: set[str] = set()
    if not log_path.exists():
        return out
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Could not read execution log: %s", e)
        return out
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("action") != "SELL" and obj.get("type") != "SHORT":
            continue
        symbol = obj.get("symbol")
        if isinstance(symbol, str) and symbol.strip():
            out.add(symbol.strip().upper())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync current short symbols to current_short_symbols.json")
    parser.add_argument("--ib", action="store_true", help="Use IB only (skip log fallback)")
    parser.add_argument("--log", action="store_true", help="Use execution log only (skip IB)")
    parser.add_argument("--host", default="127.0.0.1", help="IB Gateway host")
    parser.add_argument("--port", type=int, default=4002, help="IB Gateway port")
    parser.add_argument("--client-id", type=int, default=104, help="IB client ID for sync")
    args = parser.parse_args()

    trading_dir = _trading_dir()
    out_path = trading_dir / "current_short_symbols.json"
    log_path = trading_dir / "logs" / "executions.json"

    symbols: set[str] = set()

    if not args.log:
        from_ib = _symbols_from_ib(args.host, args.port, args.client_id)
        if from_ib:
            symbols |= from_ib
            logger.info("IB: %d short symbol(s)", len(from_ib))
        elif args.ib:
            logger.warning("IB requested but connection failed; no symbols from IB")

    if not args.ib and (not symbols or args.log):
        from_log = _symbols_from_log(log_path)
        if from_log:
            symbols |= from_log
            logger.info("Log: %d short symbol(s) from executions", len(from_log))

    symbols_sorted = sorted(symbols)
    payload = {
        "symbols": symbols_sorted,
        "updated_at": datetime.now().isoformat(),
    }
    trading_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote %d symbol(s) to %s", len(symbols_sorted), out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
