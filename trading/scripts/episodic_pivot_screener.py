#!/usr/bin/env python3
"""
Episodic Pivot (EP) Screener — Kristjan Kullamägi (Market Wizards: The Next Generation).

Episodic Pivots are the highest-probability setup in Kullamägi's arsenal:
  - A stock gaps up significantly on massive volume due to a FUNDAMENTAL catalyst
    (earnings beat, guidance raise, product launch, M&A, FDA approval, etc.)
  - The stock consolidates near the gap-up high for 1–5 days while volume dries up
  - Entry is triggered on the first RVOL surge + breakout above the consolidation range

Key features of a true EP setup:
  1. Catalyst gap: day-over-day gap ≥ GAP_MIN_PCT (default 8%)
  2. Volume confirmation: gap-day volume ≥ RVOL_THRESHOLD × avg volume (default 4×)
  3. Consolidation window: 1–5 trading days since the gap
  4. Breakout trigger: current session volume ≥ BREAKOUT_RVOL × avg (default 2×)
     AND price within BREAKOUT_RANGE_PCT of gap-day high
  5. Quality gate: RS (relative strength vs SPY) ≥ RS_MIN_PCT (default 65th percentile)

This screener does NOT execute trades. It outputs candidates to:
  logs/ep_candidates_YYYYMMDD.json — for review and optional auto-execution
  Telegram notification with top candidates

Auto-execution (enabled by risk.json → ep_screener.auto_execute = true) routes
candidates through execute_longs.py's standard pipeline including conviction scoring,
budget checks, and position sizing.

Runs at market open and again at mid-session via scheduler.
clientId: none (screener only — no IB connection needed)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf
import pandas as pd

from paths import TRADING_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ep_screener] %(levelname)s — %(message)s",
)
logger = logging.getLogger("ep_screener")

# ---------------------------------------------------------------------------
# Config defaults — all overridable via risk.json → ep_screener
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG = {
    "enabled": True,
    "universe_file": "watchlists/symbols_with_prices.csv",
    "gap_min_pct": 8.0,               # minimum gap % to qualify as an EP
    "rvol_threshold": 4.0,            # min RVOL on the gap day
    "consolidation_days_max": 5,      # max days since the gap to still be eligible
    "breakout_rvol_min": 2.0,         # min RVOL on today's session for breakout trigger
    "breakout_range_pct": 3.0,        # price must be within X% of gap-day high
    "rs_min_pct": 65.0,               # min RS percentile vs SPY (lower = exclude weak stocks)
    "max_candidates": 10,             # max EPs to surface per run
    "auto_execute": False,            # set true to pipe into execute_longs
    "output_file": "logs/ep_candidates_{date}.json",
    "lookback_days": 90,              # yfinance lookback to find recent gaps
}


def _load_config() -> dict:
    cfg = dict(_DEFAULT_CONFIG)
    try:
        risk = json.loads((TRADING_DIR / "risk.json").read_text())
        cfg.update(risk.get("ep_screener", {}))
    except Exception:
        pass
    return cfg


# ---------------------------------------------------------------------------
# Universe loader
# ---------------------------------------------------------------------------

def _load_universe(cfg: dict) -> list[str]:
    universe_path = TRADING_DIR / cfg.get("universe_file", "watchlists/symbols_with_prices.csv")
    if not universe_path.exists():
        logger.warning("Universe file not found: %s — falling back to S&P 100", universe_path)
        return [
            "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "BRK.B", "JPM",
            "V", "UNH", "MA", "HD", "PG", "JNJ", "AVGO", "MRK", "ABBV", "CVX", "LLY",
            "KO", "PEP", "COST", "TMO", "CSCO", "WMT", "MCD", "ABT", "ACN", "DHR",
            "NEE", "CRM", "PM", "CMCSA", "VZ", "NFLX", "INTC", "AMD", "QCOM", "TXN",
            "HON", "UNP", "RTX", "GS", "CAT", "IBM", "AMGN", "BA", "BLK", "SPGI",
        ]
    try:
        df = pd.read_csv(universe_path)
        # Accept both "symbol" and "Symbol" column names
        col = next((c for c in df.columns if c.lower() == "symbol"), None)
        if col:
            return df[col].dropna().astype(str).str.upper().tolist()
        return df.iloc[:, 0].dropna().astype(str).str.upper().tolist()
    except Exception as exc:
        logger.error("Universe load failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# RS vs SPY
# ---------------------------------------------------------------------------

def _rs_vs_spy(sym_close: pd.Series, spy_close: pd.Series, window: int = 63) -> float:
    """Return relative strength (sym / SPY ratio) normalized to [0, 1] over the window."""
    try:
        ratio = sym_close / spy_close
        ratio = ratio.dropna()
        if len(ratio) < 10:
            return 0.5
        current = float(ratio.iloc[-1])
        rolling = ratio.rolling(window, min_periods=10)
        lo = float(rolling.min().iloc[-1])
        hi = float(rolling.max().iloc[-1])
        if hi <= lo:
            return 0.5
        return max(0.0, min(1.0, (current - lo) / (hi - lo)))
    except Exception:
        return 0.5


# ---------------------------------------------------------------------------
# Core EP detection
# ---------------------------------------------------------------------------

def _detect_ep(
    symbol: str,
    df: pd.DataFrame,
    spy_close: pd.Series,
    cfg: dict,
    today: datetime,
) -> Optional[dict]:
    """Return an EP candidate dict if the symbol meets all criteria, else None."""
    gap_min = float(cfg["gap_min_pct"]) / 100
    rvol_threshold = float(cfg["rvol_threshold"])
    consolidation_max = int(cfg["consolidation_days_max"])
    breakout_rvol = float(cfg["breakout_rvol_min"])
    breakout_range = float(cfg["breakout_range_pct"]) / 100
    rs_min = float(cfg["rs_min_pct"]) / 100

    if df.empty or len(df) < 30:
        return None

    # Align with SPY
    common_idx = df.index.intersection(spy_close.index)
    if len(common_idx) < 20:
        return None
    df_aligned = df.loc[common_idx]
    spy_aligned = spy_close.loc[common_idx]

    close = df_aligned["Close"]
    volume = df_aligned["Volume"]
    high = df_aligned["High"]
    open_price = df_aligned["Open"]

    # Flatten any multi-level columns remaining from yfinance
    def _squeeze(s: pd.Series | pd.DataFrame) -> pd.Series:
        if isinstance(s, pd.DataFrame):
            return s.iloc[:, 0]
        return s

    close = _squeeze(close)
    volume = _squeeze(volume)
    high = _squeeze(high)
    open_price = _squeeze(open_price)

    # Compute average daily volume (50-day)
    avg_vol_50 = volume.rolling(50, min_periods=20).mean()

    # Search backwards from today for a qualifying gap
    lookback = int(cfg.get("lookback_days", 90))
    recent = df_aligned.iloc[-lookback:]
    recent_close = close.iloc[-lookback:]
    recent_vol = volume.iloc[-lookback:]
    recent_high = high.iloc[-lookback:]
    recent_open = open_price.iloc[-lookback:]

    ep_idx = None
    ep_date = None
    ep_gap_pct = 0.0
    ep_high = 0.0
    ep_rvol = 0.0

    for i in range(1, len(recent) - 1):
        prev_close = float(recent_close.iloc[i - 1])
        curr_open = float(recent_open.iloc[i])
        curr_high = float(recent_high.iloc[i])
        curr_vol = float(recent_vol.iloc[i])

        if prev_close <= 0:
            continue

        gap_pct = (curr_open - prev_close) / prev_close
        if gap_pct < gap_min:
            continue

        avg_vol = float(avg_vol_50.iloc[i])
        if avg_vol <= 0:
            continue
        rvol = curr_vol / avg_vol

        if rvol < rvol_threshold:
            continue

        # Valid EP gap found — record the MOST RECENT one
        ep_idx = i
        ep_date = recent.index[i]
        ep_gap_pct = gap_pct
        ep_high = curr_high
        ep_rvol = rvol

    if ep_idx is None:
        return None

    # Check consolidation window: gap must be within last N trading days
    today_idx = len(recent) - 1
    days_since_gap = today_idx - ep_idx

    if days_since_gap > consolidation_max or days_since_gap < 1:
        return None   # too old or gap just happened (need 1 day to form consolidation)

    # Check today's breakout conditions
    today_close = float(recent_close.iloc[-1])
    today_vol = float(recent_vol.iloc[-1])
    today_avg_vol = float(avg_vol_50.iloc[-1])
    today_rvol = today_vol / today_avg_vol if today_avg_vol > 0 else 0.0

    if today_rvol < breakout_rvol:
        return None   # insufficient volume surge today

    if abs(today_close - ep_high) / ep_high > breakout_range:
        return None   # price too far from consolidation high

    # RS quality gate
    rs = _rs_vs_spy(close, spy_aligned, window=63)
    if rs < rs_min:
        return None   # weak relative strength

    return {
        "symbol": symbol,
        "ep_date": ep_date.strftime("%Y-%m-%d") if hasattr(ep_date, "strftime") else str(ep_date),
        "days_since_gap": days_since_gap,
        "gap_pct": round(ep_gap_pct * 100, 1),
        "ep_rvol": round(ep_rvol, 1),
        "ep_high": round(ep_high, 2),
        "current_price": round(today_close, 2),
        "today_rvol": round(today_rvol, 1),
        "rs_percentile": round(rs * 100, 1),
        "setup": "EPISODIC_PIVOT",
        # Fields for execute_longs.py compatibility
        "score": round(min(1.0, (rs + min(today_rvol / 10, 0.5)) / 1.5), 3),
        "momentum": round(ep_gap_pct, 3),
        "strategy": "ep_screener",
        "side": "LONG",
    }


# ---------------------------------------------------------------------------
# Main screener run
# ---------------------------------------------------------------------------

def run(dry_run: bool = False) -> list[dict]:
    """Scan the universe for Episodic Pivot setups.  Returns list of candidates."""
    cfg = _load_config()
    if not cfg.get("enabled", True):
        logger.info("EP screener disabled (risk.json → ep_screener.enabled=false)")
        return []

    today = datetime.now()
    lookback_period = f"{int(cfg.get('lookback_days', 90)) + 60}d"   # extra buffer

    universe = _load_universe(cfg)
    if not universe:
        logger.error("Empty universe — EP screener cannot run")
        return []

    logger.info("EP screener: scanning %d symbols over %s lookback", len(universe), lookback_period)

    # Download SPY for RS calculation
    try:
        spy_raw = yf.download("SPY", period=lookback_period, progress=False)
        if isinstance(spy_raw.columns, pd.MultiIndex):
            spy_raw.columns = spy_raw.columns.get_level_values(0)
        spy_close = spy_raw["Close"].squeeze().dropna()
    except Exception as exc:
        logger.error("Could not download SPY data: %s", exc)
        return []

    # Screen in batches to avoid rate limits
    candidates: list[dict] = []
    batch_size = 50
    for batch_start in range(0, len(universe), batch_size):
        batch = universe[batch_start: batch_start + batch_size]
        try:
            raw = yf.download(batch, period=lookback_period, progress=False, group_by="ticker")
        except Exception as exc:
            logger.warning("Batch download failed (batch %d): %s", batch_start // batch_size, exc)
            continue

        for symbol in batch:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if symbol not in raw.columns.get_level_values(0):
                        continue
                    df = raw[symbol].dropna(how="all")
                else:
                    df = raw.copy()

                if df is None or df.empty or len(df) < 30:
                    continue

                candidate = _detect_ep(symbol, df, spy_close, cfg, today)
                if candidate is not None:
                    candidates.append(candidate)
                    logger.info(
                        "EP FOUND: %s | gap_date=%s days_ago=%d gap=+%.1f%% RVOL=%.1f× today_RVOL=%.1f× RS=%.0f%%",
                        symbol,
                        candidate["ep_date"],
                        candidate["days_since_gap"],
                        candidate["gap_pct"],
                        candidate["ep_rvol"],
                        candidate["today_rvol"],
                        candidate["rs_percentile"],
                    )
            except Exception as exc:
                logger.debug("EP check error for %s: %s", symbol, exc)

    # Sort by strength: RVOL × RS
    candidates.sort(
        key=lambda c: c["today_rvol"] * c["rs_percentile"],
        reverse=True,
    )
    max_candidates = int(cfg.get("max_candidates", 10))
    candidates = candidates[:max_candidates]

    # Write output file
    date_str = today.strftime("%Y%m%d")
    output_rel = cfg.get("output_file", "logs/ep_candidates_{date}.json").format(date=date_str)
    output_path = TRADING_DIR / output_rel
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "generated": today.isoformat(),
        "count": len(candidates),
        "candidates": candidates,
    }, indent=2))
    logger.info("EP screener complete: %d candidates → %s", len(candidates), output_path)

    # Telegram notification
    if candidates:
        try:
            from notifications import notify_info
            lines = [f"🔺 <b>Episodic Pivots Found — {date_str}</b>"]
            for c in candidates[:5]:
                lines.append(
                    f"• <b>{c['symbol']}</b> | gap +{c['gap_pct']:.1f}% {c['days_since_gap']}d ago "
                    f"| RVOL {c['today_rvol']:.1f}× | RS {c['rs_percentile']:.0f}%ile"
                )
            notify_info("\n".join(lines))
        except Exception:
            pass

    # Auto-execute if configured
    if cfg.get("auto_execute") and candidates and not dry_run:
        _pipe_to_execute_longs(candidates, output_path)

    return candidates


def _pipe_to_execute_longs(candidates: list[dict], candidates_file: Path) -> None:
    """Write candidates to long_candidates.json so execute_longs.py picks them up next run.

    The candidates dict already has the fields expected by execute_longs (symbol, score,
    momentum, strategy, side), augmented with ep-specific context fields that are ignored
    by the executor but available for logging.
    """
    target = TRADING_DIR / "logs" / "long_candidates_ep.json"
    try:
        target.write_text(json.dumps(candidates, indent=2))
        logger.info("EP candidates written to %s for auto-execution", target)
    except Exception as exc:
        logger.error("Could not write EP candidates for auto-execution: %s", exc)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Episodic Pivot screener")
    parser.add_argument("--dry-run", action="store_true", help="Scan without auto-executing")
    parser.add_argument("--symbol", help="Screen a single symbol (debug)")
    args = parser.parse_args()

    if args.symbol:
        # Single-symbol debug mode
        cfg = _load_config()
        try:
            spy_raw = yf.download("SPY", period="120d", progress=False)
            if isinstance(spy_raw.columns, pd.MultiIndex):
                spy_raw.columns = spy_raw.columns.get_level_values(0)
            spy_close = spy_raw["Close"].squeeze().dropna()
            df = yf.download(args.symbol, period="120d", progress=False)
            result = _detect_ep(args.symbol.upper(), df, spy_close, cfg, datetime.now())
            if result:
                print(json.dumps(result, indent=2))
            else:
                print(f"No EP setup found for {args.symbol.upper()}")
        except Exception as exc:
            print(f"Error: {exc}")
    else:
        results = run(dry_run=args.dry_run)
        print(f"\nEP Screener: {len(results)} candidate(s) found")
        for c in results:
            print(
                f"  {c['symbol']:8s} | gap +{c['gap_pct']:5.1f}% {c['days_since_gap']}d ago "
                f"| RVOL {c['today_rvol']:.1f}x | RS {c['rs_percentile']:.0f}th pctile"
            )
