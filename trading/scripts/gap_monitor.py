#!/usr/bin/env python3
"""
Gap Monitor — runs at 9:32 AM ET (2 min after open).

Checks every long stock position for an opening gap versus the prior close.
Sends an alert when a position gaps beyond the configured thresholds.

Gap severity levels
-------------------
  CRITICAL  gap ≥ 3% down  (or position is within 1 ATR of its stop after the gap)
  WARNING   gap ≥ 1.5% down
  UP        gap ≥ 2% up    (informational — potential assignment / take-profit alert)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

LOG_DIR = TRADING_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "gap_monitor.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

PENDING_FILE = TRADING_DIR / "config" / "pending_trades.json"

# Gap thresholds
GAP_DOWN_CRITICAL_PCT = 3.0   # % below prior close → CRITICAL alert
GAP_DOWN_WARN_PCT     = 1.5   # % below prior close → WARNING alert
GAP_UP_NOTIFY_PCT     = 2.0   # % above prior close → informational UP alert
NEAR_STOP_ATR_MULT    = 1.0   # escalate to CRITICAL if within 1× ATR of stop after gap

IB_HOST   = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT   = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 131


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_stops() -> dict[str, float]:
    if not PENDING_FILE.exists():
        return {}
    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    stops: dict[str, float] = {}
    for trade in data.get("pending", []):
        for cond in trade.get("trigger", {}).get("conditions", []):
            if cond.get("type") == "price_below":
                sym = str(cond.get("symbol", "")).upper()
                price = cond.get("price")
                if sym and price is not None:
                    stops[sym] = float(price)
    return stops


def _get_ib_positions() -> dict[str, dict]:
    try:
        import logging as _l
        from ib_insync import IB
        _l.getLogger("ib_insync").setLevel(_l.CRITICAL)
    except ImportError:
        logger.error("ib_insync not installed")
        return {}

    ib = IB()
    for port in [IB_PORT, 4001, 7496, 7497]:
        try:
            ib.connect(IB_HOST, port, clientId=CLIENT_ID, timeout=15)
            break
        except Exception:
            continue

    if not ib.isConnected():
        logger.warning("Cannot connect to IBKR — using snapshot prices only")
        return {}

    result: dict[str, dict] = {}
    try:
        for p in ib.positions():
            c = p.contract
            if c.secType == "STK" and p.position > 0:
                result[c.symbol.upper()] = {
                    "qty": int(p.position),
                    "avg_cost": float(p.avgCost),
                }
    finally:
        ib.disconnect()
    return result


def _fetch_gap_data(symbols: list[str]) -> dict[str, dict]:
    """Return {sym: {open, prev_close, atr}} for each symbol."""
    import yfinance as yf

    result: dict[str, dict] = {}
    for sym in symbols:
        try:
            hist = yf.download(sym, period="20d", progress=False, auto_adjust=True)
            if hist.empty or len(hist) < 2:
                continue

            close_col = hist["Close"]
            open_col  = hist["Open"]
            high_col  = hist["High"]
            low_col   = hist["Low"]

            # Handle multi-level columns from yfinance
            if hasattr(close_col, "columns"):
                close_col = close_col.iloc[:, 0]
                open_col  = open_col.iloc[:, 0]
                high_col  = high_col.iloc[:, 0]
                low_col   = low_col.iloc[:, 0]

            prev_close = float(close_col.iloc[-2])
            today_open = float(open_col.iloc[-1])

            # 14-period ATR
            tr_list = []
            closes = close_col.values
            highs  = high_col.values
            lows   = low_col.values
            for i in range(1, len(closes)):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i]  - closes[i - 1]),
                )
                tr_list.append(tr)
            atr = float(sum(tr_list[-14:]) / min(len(tr_list), 14)) if tr_list else 0.0

            result[sym] = {
                "open":       round(today_open, 2),
                "prev_close": round(prev_close, 2),
                "atr":        round(atr, 2),
            }
        except Exception as exc:
            logger.debug("Gap data fetch failed for %s: %s", sym, exc)
    return result


# ── main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    logger.info("=== Gap Monitor — %s ===", datetime.now().strftime("%Y-%m-%d %H:%M"))

    positions = _get_ib_positions()
    if not positions:
        # Fall back to snapshot
        snap_file = TRADING_DIR / "logs" / "dashboard_snapshot.json"
        if snap_file.exists():
            snap = json.loads(snap_file.read_text(encoding="utf-8"))
            positions_data = snap.get("positions", {})
            pos_list = positions_data.get("list", []) if isinstance(positions_data, dict) else []
            for pos in pos_list:
                sym = str(pos.get("symbol", "")).upper()
                qty = pos.get("quantity", 0)
                if qty and qty > 0:
                    positions[sym] = {"qty": int(qty), "avg_cost": float(pos.get("avg_cost", 0))}

    if not positions:
        logger.warning("No positions found — nothing to monitor")
        return

    symbols   = list(positions.keys())
    gap_data  = _fetch_gap_data(symbols)
    stops     = _load_stops()

    criticals: list[str] = []
    warnings:  list[str] = []
    ups:       list[str] = []

    for sym, pos in positions.items():
        gd = gap_data.get(sym)
        if not gd:
            continue

        prev_close = gd["prev_close"]
        today_open = gd["open"]
        atr        = gd["atr"]
        stop       = stops.get(sym)

        if prev_close <= 0:
            continue

        gap_pct = (today_open - prev_close) / prev_close * 100
        gap_amt = today_open - prev_close

        if gap_pct <= -GAP_DOWN_CRITICAL_PCT:
            severity = "CRITICAL"
        elif stop and atr and (today_open - stop) <= (NEAR_STOP_ATR_MULT * atr):
            # Gapped down less than 3% but is now within 1 ATR of the stop
            severity = "CRITICAL" if gap_pct < 0 else None
        elif gap_pct <= -GAP_DOWN_WARN_PCT:
            severity = "WARNING"
        elif gap_pct >= GAP_UP_NOTIFY_PCT:
            severity = "UP"
        else:
            severity = None

        if severity is None:
            logger.info("  %s: gap %.1f%% (open=$%.2f, prev=$%.2f) — OK",
                        sym, gap_pct, today_open, prev_close)
            continue

        stop_str = f" | stop=${stop:.2f}" if stop else ""
        dist_to_stop: Optional[str] = None
        if stop:
            dist = today_open - stop
            dist_to_stop = f"{dist:+.2f} ({dist/prev_close*100:+.1f}%) from stop"

        line = (
            f"<b>{sym}</b> {'+' if gap_pct > 0 else ''}{gap_pct:.1f}%  "
            f"open=${today_open:.2f} vs prev=${prev_close:.2f} (Δ{gap_amt:+.2f})"
            f"{stop_str}"
        )
        if dist_to_stop:
            line += f"\n  → {dist_to_stop}"

        if severity == "CRITICAL":
            criticals.append(line)
            logger.warning("  CRITICAL GAP: %s", line.replace("<b>", "").replace("</b>", ""))
        elif severity == "WARNING":
            warnings.append(line)
            logger.warning("  WARNING GAP:  %s", line.replace("<b>", "").replace("</b>", ""))
        elif severity == "UP":
            ups.append(line)
            logger.info("  GAP UP:       %s", line.replace("<b>", "").replace("</b>", ""))

    if not (criticals or warnings or ups):
        logger.info("No significant gaps detected — all positions opened cleanly.")
        return

    # ── Build notification ────────────────────────────────────────────────────
    from notifications import notify_critical, notify_info

    if criticals:
        body = "🚨 <b>CRITICAL GAPS — check stops immediately</b>\n\n"
        body += "\n\n".join(criticals)
        if warnings:
            body += "\n\n⚠️ <b>Also warning:</b>\n" + "\n".join(warnings)
        notify_critical("Gap Alert — Critical", body)
        logger.info("Sent CRITICAL gap notification (%d position(s))", len(criticals))

    elif warnings:
        body = "⚠️ <b>Gap Warning</b>\n\n" + "\n\n".join(warnings)
        notify_info(body)
        logger.info("Sent WARNING gap notification (%d position(s))", len(warnings))

    if ups:
        body = "📈 <b>Gap Up Alert</b>\n\n" + "\n\n".join(ups)
        notify_info(body)
        logger.info("Sent GAP UP notification (%d position(s))", len(ups))


if __name__ == "__main__":
    run()
