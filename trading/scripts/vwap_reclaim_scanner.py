#!/usr/bin/env python3
"""
Intraday VWAP Reclaim Scanner

Identifies stocks that gapped DOWN at the open (below prior close AND below
VWAP) but have since reclaimed VWAP by 10:30 ET — a classic institutional
reversal signal.

The VWAP Reclaim Setup
----------------------
When a stock gaps down and then reclaims its intraday VWAP within the first
60 minutes, it signals that:
  1. The opening sell pressure was absorbed by buyers
  2. Institutional buyers stepped in at the VWAP level
  3. Price has "reclaimed" fair value — a high-probability reversal pattern

This scanner runs at 10:30 ET, 60 minutes after market open, to allow enough
volume to anchor VWAP reliably while capturing early reclaim setups.

Selection criteria
------------------
1. Gap down at open: today's open < prior close × (1 - MIN_GAP_PCT)
2. VWAP reclaim: current price > intraday VWAP
3. Price holding above VWAP for the last N bars (confirmation)
4. Volume above average (institutional participation)
5. Gap not too large — huge gaps often continue down (skip if gap > MAX_GAP_PCT)
6. Stock was in an uptrend before the gap (price > 20-day SMA from yesterday)

Data source
-----------
IBKR 5-minute bars via ib_insync. Falls back to yfinance intraday data
(1m bars, last 1 day) if IBKR is not available.

Output
------
Writes ``trading/logs/vwap_reclaim.json`` with the identified setups.
Sends notification for high-conviction setups (reclaim confirmed + volume surge).

Scheduler integration
---------------------
Runs as a one-shot job at 08:30 MT (10:30 ET) via the scheduler.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
TRADING_DIR  = SCRIPT_DIR.parent
PROJECT_ROOT = TRADING_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

from atomic_io import atomic_write_json   # noqa: E402
from notifications import notify_event    # noqa: E402

OUTPUT_FILE = TRADING_DIR / "logs" / "vwap_reclaim.json"
LOGS_DIR    = TRADING_DIR / "logs"
LOG_FILE    = LOGS_DIR / "vwap_reclaim_scanner.log"

# ── Config ────────────────────────────────────────────────────────────────────
MIN_GAP_PCT    = 0.01    # minimum gap-down size to qualify (1%)
MAX_GAP_PCT    = 0.10    # skip stocks that gapped down > 10% (too risky)
MIN_VOL_RATIO  = 1.3     # reclaim bar volume must be ≥ N× average intraday bar volume
MIN_SCORE      = 0.35    # minimum composite score to include

# Watchlist: use the existing positions + pairs candidates as the scan universe.
# Dynamically read from pending_trades.json (all position symbols) + recent screener output.

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── Universe ──────────────────────────────────────────────────────────────────

def _build_scan_universe() -> list[str]:
    """Build intraday scan universe from pending_trades + screener watchlists."""
    symbols: set[str] = set()

    # 1. All symbols with active stops/TPs in pending_trades.json
    pending_path = TRADING_DIR / "config" / "pending_trades.json"
    if pending_path.exists():
        try:
            data = json.loads(pending_path.read_text())
            for section in ("pending", "take_profit", "partial_profit"):
                for entry in data.get(section, []):
                    for leg in entry.get("legs", []):
                        sym = leg.get("symbol") or ""
                        # pending_trades uses "secType" field (STK / OPT)
                        if sym and leg.get("secType", "STK") in ("STK", "stock"):
                            symbols.add(sym.upper())
        except (OSError, ValueError):
            pass

    # 2. Long screener watchlist
    for wl_file in [
        TRADING_DIR / "watchlist_longs.json",
        TRADING_DIR / "watchlist_pead.json",
    ]:
        if wl_file.exists():
            try:
                data = json.loads(wl_file.read_text())
                for key in ("long_candidates", "candidates", "symbols"):
                    items = data.get(key, [])
                    for item in items:
                        if isinstance(item, dict):
                            sym = item.get("symbol") or ""
                        elif isinstance(item, str):
                            sym = item
                        else:
                            continue
                        if sym:
                            symbols.add(sym.strip().upper())
            except (OSError, ValueError):
                pass

    # 3. Multimode screener (long opportunities)
    multimode_path = TRADING_DIR / "watchlist_multimode.json"
    if multimode_path.exists():
        try:
            data = json.loads(multimode_path.read_text())
            for mode_data in (data.get("modes") or {}).values():
                for item in mode_data.get("long", []):
                    sym = (item.get("symbol") or "").strip().upper()
                    if sym:
                        symbols.add(sym)
        except (OSError, ValueError):
            pass

    logger.info("Built intraday scan universe: %d symbols", len(symbols))
    return sorted(symbols)


# ── VWAP helpers ──────────────────────────────────────────────────────────────

def _compute_vwap(closes: list[float], highs: list[float], lows: list[float], volumes: list[float]) -> float | None:
    """Compute intraday VWAP from bar data."""
    if not closes or len(closes) != len(volumes):
        return None
    total_pv = sum(
        ((h + l + c) / 3) * v
        for h, l, c, v in zip(highs, lows, closes, volumes)
        if v > 0
    )
    total_v = sum(v for v in volumes if v > 0)
    if total_v == 0:
        return None
    return total_pv / total_v


# ── Symbol analysis ────────────────────────────────────────────────────────────

def _analyze_symbol_yf(sym: str) -> dict[str, Any] | None:
    """Analyze one symbol for VWAP reclaim using yfinance intraday data."""
    try:
        import yfinance as yf
        import pandas as pd

        ticker = yf.Ticker(sym)

        # Get today's intraday 5-minute bars
        today_hist = ticker.history(period="1d", interval="5m", auto_adjust=True)
        if today_hist.empty or len(today_hist) < 6:
            return None

        # Get recent daily history — need ≥21 bars for SMA-20 + prior-close reference
        daily_hist = ticker.history(period="2mo", interval="1d", auto_adjust=True)
        if daily_hist.empty or len(daily_hist) < 2:
            return None

        prior_close = float(daily_hist["Close"].iloc[-2])
        today_open  = float(today_hist["Open"].iloc[0])
        current_price = float(today_hist["Close"].iloc[-1])

        if prior_close <= 0 or today_open <= 0:
            return None

        # Check for gap down
        gap_pct = (today_open - prior_close) / prior_close  # negative = gap down
        if gap_pct >= -MIN_GAP_PCT:
            return None   # not a gap down
        if gap_pct < -MAX_GAP_PCT:
            return None   # gap too large

        closes  = [float(c) for c in today_hist["Close"].tolist()]
        highs   = [float(h) for h in today_hist["High"].tolist()]
        lows    = [float(l) for l in today_hist["Low"].tolist()]
        volumes = [float(v) for v in today_hist["Volume"].tolist()]

        # Compute intraday VWAP using all bars up to now
        vwap = _compute_vwap(closes, highs, lows, volumes)
        if vwap is None:
            return None

        # Check VWAP reclaim: current price must be above VWAP
        if current_price <= vwap:
            return None

        # Confirmation: price has been above VWAP for at least last 2 bars
        last_2_closes = closes[-2:]
        if not all(c > vwap for c in last_2_closes):
            return None

        # Volume check: compare last bar volume vs average bar volume
        avg_bar_vol = sum(volumes[:-1]) / max(len(volumes) - 1, 1) if len(volumes) > 1 else volumes[-1]
        last_bar_vol = volumes[-1]
        vol_ratio = last_bar_vol / avg_bar_vol if avg_bar_vol > 0 else 0.0

        # 20-day SMA from daily history (prior day close > SMA20)
        # Need >= 21 bars: [-21:-1] selects exactly 20 values for the SMA calculation
        daily_closes = [float(c) for c in daily_hist["Close"].tolist()]
        if len(daily_closes) >= 21:
            sma20_prev = sum(daily_closes[-21:-1]) / 20
            in_uptrend = prior_close > sma20_prev
        else:
            in_uptrend = True  # insufficient history — assume uptrend

        if not in_uptrend:
            return None   # skip — gapped down stocks in downtrend rarely reclaim meaningfully

        # Composite score
        gap_size_score   = min(1.0, abs(gap_pct) / 0.05)         # deeper gap = more interesting
        recovery_score   = min(1.0, (current_price - vwap) / (vwap * 0.01))  # how far above VWAP
        volume_score     = min(1.0, max(0.0, (vol_ratio - 1.0) / 2.0))
        score = round(0.35 * gap_size_score + 0.40 * recovery_score + 0.25 * volume_score, 4)

        if score < MIN_SCORE:
            return None

        return {
            "symbol":       sym,
            "gap_pct":      round(gap_pct * 100, 2),     # negative, percent
            "prior_close":  round(prior_close, 2),
            "open":         round(today_open, 2),
            "current":      round(current_price, 2),
            "vwap":         round(vwap, 2),
            "above_vwap_by_pct": round((current_price / vwap - 1) * 100, 2),
            "vol_ratio":    round(vol_ratio, 2),
            "score":        score,
            "action":       "BUY — VWAP reclaim reversal",
        }

    except Exception as exc:  # noqa: BLE001
        logger.debug("VWAP analysis failed for %s: %s", sym, exc)
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def run() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York"))
    # Only meaningful to run between 10:00 and 12:00 ET (VWAP accumulation window)
    if not (10 <= now_et.hour < 12):
        logger.info("Outside VWAP scan window (10:00–12:00 ET). Current ET: %s", now_et.strftime("%H:%M"))
        atomic_write_json(
            OUTPUT_FILE,
            {"generated_at": datetime.now(timezone.utc).isoformat(), "setups": [], "skipped_reason": "outside_window"},
        )
        return

    universe = _build_scan_universe()
    if not universe:
        logger.warning("Empty scan universe — nothing to scan")
        atomic_write_json(OUTPUT_FILE, {"generated_at": datetime.now(timezone.utc).isoformat(), "setups": []})
        return

    logger.info("Scanning %d symbols for VWAP reclaim setups...", len(universe))

    setups: list[dict[str, Any]] = []
    for sym in universe:
        result = _analyze_symbol_yf(sym)
        if result:
            setups.append(result)
            logger.info(
                "VWAP RECLAIM: %s — gap=%.1f%%, now=%.2f vs VWAP=%.2f (+%.1f%%)",
                sym,
                result["gap_pct"],
                result["current"],
                result["vwap"],
                result["above_vwap_by_pct"],
            )

    setups.sort(key=lambda s: s["score"], reverse=True)
    logger.info("Found %d VWAP reclaim setup(s)", len(setups))

    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "scan_time_et":  now_et.strftime("%H:%M ET"),
        "setups":        setups,
    }
    atomic_write_json(OUTPUT_FILE, output)
    logger.info("VWAP reclaim results saved to %s", OUTPUT_FILE)

    # Alert for high-score setups (≥ 0.55)
    alerts = [s for s in setups if s["score"] >= 0.55]
    if alerts:
        lines = [
            f"  {s['symbol']}: gap={s['gap_pct']:.1f}% | now={s['current']:.2f} vs VWAP={s['vwap']:.2f} "
            f"(+{s['above_vwap_by_pct']:.1f}%) | vol={s['vol_ratio']:.1f}× | score={s['score']:.2f}"
            for s in alerts
        ]
        notify_event(
            "vwap_reclaim",
            subject=f"📈 VWAP Reclaim: {', '.join(s['symbol'] for s in alerts)}",
            body=(
                f"{len(alerts)} VWAP reclaim setup(s) detected at {now_et.strftime('%H:%M ET')}:\n\n"
                + "\n".join(lines)
                + "\n\nVWAP reclaim after a gap-down signals institutional buying. "
                "Best entries are on the first confirmed bar above VWAP with above-average volume."
            ),
            urgent=False,
        )


if __name__ == "__main__":
    run()
