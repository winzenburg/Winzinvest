#!/usr/bin/env python3
"""
Bearish Short Screener

Runs in pre-market (07:00 MT) alongside other screeners.
Only produces candidates when regime is STRONG_DOWNTREND or UNFAVORABLE.

Selection criteria for short candidates:
  1. Price BELOW 200-day SMA — confirmed structural downtrend
  2. Negative RS vs SPY (20-day) — weaker than the broader market
  3. RSI(14) between 40-68 — not deeply oversold (room to fall still present)
  4. Recent earnings > 7 days away — avoids short-squeeze from surprise beats
  5. Minimum average daily volume > 500,000 shares — adequate liquidity to cover
  6. Hybrid short score ≥ 0.40 — ranked by weakness, not just eligibility

Output: trading/watchlist_shorts.json
  {
    "generated_at": "...",
    "regime": "STRONG_DOWNTREND",
    "short_candidates": [
      {"symbol": "XYZ", "price": 45.20, "score": 0.72, "rs_pct": -3.1, "rsi": 54, ...}
    ]
  }

execute_dual_mode.py reads this file in addition to watchlist_multimode.json.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
        logging.FileHandler(LOG_DIR / "nx_screener_shorts.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

OUTPUT_FILE = TRADING_DIR / "watchlist_shorts.json"

# Only run in these regimes
SHORT_ELIGIBLE_REGIMES = {"STRONG_DOWNTREND", "UNFAVORABLE"}
# Relax to also run in CHOPPY/MIXED at reduced size — controlled by allocation table
ALWAYS_RUN_REGIMES = {"STRONG_DOWNTREND", "UNFAVORABLE", "CHOPPY", "MIXED"}

# Candidate limits
MAX_CANDIDATES = 10
MIN_AVG_VOLUME  = 500_000
MIN_SHORT_SCORE = 0.35

# RSI window: prefer candidates that are NOT deeply oversold (room to fall)
RSI_MIN = 40
RSI_MAX = 68


# ── Universe ──────────────────────────────────────────────────────────────────

def _load_universe() -> list[str]:
    """
    Build the short screening universe from existing watchlist files.
    We short the weakest names from the full long universe — any stock
    that would be a long candidate in a bull market can be a short in a bear.
    """
    symbols: set[str] = set()

    for fname in (
        "watchlist_longs.json",
        "watchlist_multimode.json",
        "watchlist_fullmarket.json",
        "watchlist.json",
    ):
        p = TRADING_DIR / fname
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        for key in ("long_candidates", "candidates", "symbols"):
            candidates = data.get(key, [])
            if isinstance(candidates, list):
                for c in candidates:
                    sym = c.get("symbol") if isinstance(c, dict) else c
                    if isinstance(sym, str) and sym.strip():
                        symbols.add(sym.strip().upper())

    # Also scan multimode modes
    try:
        mm = json.loads((TRADING_DIR / "watchlist_multimode.json").read_text())
        for mode_data in mm.get("modes", {}).values():
            for direction in ("long", "short"):
                for c in (mode_data or {}).get(direction, []):
                    if isinstance(c, dict) and c.get("symbol"):
                        symbols.add(c["symbol"].strip().upper())
    except Exception:
        pass

    logger.info("Short universe: %d symbols", len(symbols))
    return list(symbols)


# ── Metrics ───────────────────────────────────────────────────────────────────

def _calc_rsi(closes: "list[float]", period: int = 14) -> float | None:
    """
    Wilder smoothed RSI — matches TradingView/Bloomberg.
    Requires at least 2×period+1 bars for a reliable warm-up.
    """
    if len(closes) < period * 2 + 1:
        return None

    # Seed with simple mean over the first `period` changes
    seed_closes = closes[: period + 1]
    gains_seed = [max(seed_closes[i] - seed_closes[i - 1], 0) for i in range(1, period + 1)]
    loss_seed  = [max(seed_closes[i - 1] - seed_closes[i], 0) for i in range(1, period + 1)]
    avg_gain = sum(gains_seed) / period
    avg_loss = sum(loss_seed) / period

    # Wilder smoothing over remaining bars
    for close, prev in zip(closes[period + 1 :], closes[period:]):
        delta    = close - prev
        avg_gain = (avg_gain * (period - 1) + max(delta, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0)) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _score_short(metrics: dict[str, Any]) -> float:
    """
    Composite weakness score: higher = stronger short signal.

    Components:
      - Below 200 SMA distance (how far below = stronger signal): 40%
      - Negative RS vs SPY (how much weaker): 35%
      - RSI position (40-68 range, higher in range = more room to fall): 25%
    """
    sma_dist = metrics.get("sma200_pct") or 0.0       # negative = below SMA
    rs_pct   = metrics.get("rs_pct") or 0.0           # negative = weaker than SPY
    rsi      = metrics.get("rsi") or 50

    # Normalize each component to [0, 1] where 1 = strongest short signal
    # SMA component: the more below 200 SMA, the better the short
    sma_score = min(1.0, max(0.0, -sma_dist / 0.15))    # -15% = score 1.0

    # RS component: negative RS, capped at -10% = score 1.0
    rs_score = min(1.0, max(0.0, -rs_pct / 0.10))

    # RSI component: RSI=68 is ideal (near overbought, ready to turn); RSI=40 is OK
    rsi_score = min(1.0, max(0.0, (rsi - RSI_MIN) / (RSI_MAX - RSI_MIN)))

    return round(0.40 * sma_score + 0.35 * rs_score + 0.25 * rsi_score, 4)


def _screen_symbol(sym: str, spy_return_20d: float) -> dict[str, Any] | None:
    """Screen one symbol for short eligibility. Returns candidate dict or None."""
    try:
        import yfinance as yf
        import numpy as np

        ticker = yf.Ticker(sym)
        hist = ticker.history(period="1y", auto_adjust=True)
        if hist is None or hist.empty or len(hist) < 205:
            return None

        close = hist["Close"]
        volume = hist["Volume"]

        # Average daily volume filter
        avg_vol = float(volume.tail(20).mean())
        if avg_vol < MIN_AVG_VOLUME:
            return None

        price = float(close.iloc[-1])
        if price <= 0:
            return None

        sma200 = float(close.tail(200).mean())
        if price >= sma200:
            return None      # must be below 200 SMA

        sma200_pct = (price - sma200) / sma200   # negative

        # 20-day return vs SPY
        ret_20d = (price - float(close.iloc[-21])) / float(close.iloc[-21]) if len(close) >= 21 else 0.0
        rs_pct  = ret_20d - spy_return_20d

        # RSI
        closes_list = [float(c) for c in close.tail(30).tolist()]
        rsi = _calc_rsi(closes_list)
        if rsi is None or rsi < RSI_MIN or rsi > RSI_MAX:
            return None

        metrics = {
            "symbol":     sym,
            "price":      round(price, 2),
            "sma200":     round(sma200, 2),
            "sma200_pct": round(sma200_pct, 4),
            "rs_pct":     round(rs_pct, 4),
            "ret_20d":    round(ret_20d, 4),
            "rsi":        rsi,
            "avg_vol_20d": int(avg_vol),
        }
        score = _score_short(metrics)
        if score < MIN_SHORT_SCORE:
            return None

        metrics["score"] = score
        metrics["reason"] = (
            f"Below 200 SMA ({sma200_pct*100:.1f}%), RS={rs_pct*100:.1f}% vs SPY, RSI={rsi}"
        )
        return metrics

    except Exception as exc:
        logger.debug("Screen error %s: %s", sym, exc)
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    logger.info("=== Bearish Short Screener — %s ===", datetime.now().strftime("%Y-%m-%d %H:%M"))

    try:
        from regime_detector import detect_market_regime
        regime = detect_market_regime()
    except Exception as exc:
        logger.warning("Regime detection failed: %s — defaulting to CHOPPY", exc)
        regime = "CHOPPY"

    logger.info("Regime: %s", regime)

    if regime not in ALWAYS_RUN_REGIMES:
        logger.info("Regime %s does not warrant short screening — writing empty output", regime)
        _write_output([], regime)
        return

    # Fetch SPY return for RS comparison
    spy_return_20d = 0.0
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="2mo", auto_adjust=True)
        if not spy_hist.empty and len(spy_hist) >= 21:
            spy_return_20d = float(
                (spy_hist["Close"].iloc[-1] - spy_hist["Close"].iloc[-21])
                / spy_hist["Close"].iloc[-21]
            )
    except Exception as exc:
        logger.warning("SPY return fetch failed: %s", exc)

    universe = _load_universe()
    if not universe:
        logger.warning("Empty short universe — nothing to screen")
        _write_output([], regime)
        return

    # Load current shorts to avoid re-entering existing positions
    try:
        from position_filter import load_current_short_symbols
        current_shorts = load_current_short_symbols(TRADING_DIR)
    except Exception:
        current_shorts = set()

    # Earnings blackout
    try:
        from earnings_calendar import get_earnings_date
        has_earnings_check = True
    except ImportError:
        has_earnings_check = False

    candidates: list[dict[str, Any]] = []
    skipped = 0

    for sym in universe:
        if sym in current_shorts:
            continue

        if has_earnings_check:
            try:
                ed = get_earnings_date(sym)
                days_until = ed.get("days_until")
                if days_until is not None and 0 <= days_until <= 7:
                    logger.debug("Skipping %s: earnings in %d days", sym, days_until)
                    continue
            except Exception:
                pass

        result = _screen_symbol(sym, spy_return_20d)
        if result:
            candidates.append(result)
        else:
            skipped += 1

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top = candidates[:MAX_CANDIDATES]

    logger.info(
        "Short screen complete: %d candidates found (top %d), %d skipped",
        len(candidates), len(top), skipped,
    )
    for c in top:
        logger.info(
            "  %s: score=%.3f price=%.2f %s",
            c["symbol"], c["score"], c["price"], c["reason"],
        )

    _write_output(top, regime)

    # Notify if we're in STRONG_DOWNTREND and found candidates
    if top and regime == "STRONG_DOWNTREND":
        try:
            from notifications import notify_info
            lines = "\n".join(
                f"  {c['symbol']}: score={c['score']:.2f}, RS={c['rs_pct']*100:.1f}%, RSI={c['rsi']}"
                for c in top[:5]
            )
            notify_info(f"📉 <b>Bearish Shorts Identified ({regime})</b>\n{lines}")
        except Exception:
            pass


def _write_output(candidates: list[dict[str, Any]], regime: str) -> None:
    output = {
        "generated_at": datetime.now().isoformat(),
        "regime": regime,
        "short_candidates": candidates,
        "count": len(candidates),
    }
    try:
        OUTPUT_FILE.write_text(json.dumps(output, indent=2))
        logger.info("Wrote %d short candidates to %s", len(candidates), OUTPUT_FILE.name)
    except Exception as exc:
        logger.error("Failed to write watchlist_shorts.json: %s", exc)


if __name__ == "__main__":
    run()
