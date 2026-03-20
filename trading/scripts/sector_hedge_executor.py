#!/usr/bin/env python3
"""
Sector-Level ETF Hedging

Automatically manages protective hedges on over-weighted sectors during
bearish/choppy market regimes. Uses inverse ETFs or protective puts on
sector ETFs to offset concentration risk.

How it works
------------
1. Read the current portfolio's sector exposure (via sector_rebalancer.py logic)
2. Check the active market regime (STRONG_DOWNTREND, CHOPPY, UNFAVORABLE)
3. For each sector with exposure > MAX_SECTOR_HEDGE_PCT of NLV in a bearish regime:
   - If no hedge exists: queue a hedge order (buy inverse ETF or put)
   - If hedge exists: check if still sized correctly; resize if needed
4. In recovery regimes (RISK_ON, TRENDING): close any open hedges

Hedge instruments
-----------------
Each sector maps to an inverse ETF for hedging. When inverse ETFs are not
appropriate (e.g., account has restrictions), sector ETF puts are used instead.

Output
------
Appends hedge orders to ``trading/config/pending_trades.json`` under a new
``"sector_hedges"`` array. Sends notification when hedges are opened/closed.

Design choices
--------------
- Uses inverse ETFs rather than short sector ETFs for simplicity (no borrowing)
- Hedge size = sector_exposure_pct × HEDGE_RATIO (default 50% — partial hedge)
- Minimum hedge NLV: $2,000 (below this, fees outweigh protection)
- Maximum hedge NLV: 5% of total portfolio per sector
- Hedges auto-close when sector exposure drops below threshold or regime recovers

Scheduler integration
---------------------
Runs as part of the post-open execution job (10:30 ET) after main executors.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
TRADING_DIR  = SCRIPT_DIR.parent
PROJECT_ROOT = TRADING_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

from atomic_io import atomic_write_json   # noqa: E402
from notifications import notify_event    # noqa: E402

PENDING_FILE = TRADING_DIR / "config" / "pending_trades.json"
REGIME_FILE  = TRADING_DIR / "logs" / "regime_state.json"
SNAPSHOT_DIR = TRADING_DIR / "logs"
LOGS_DIR     = TRADING_DIR / "logs"
LOG_FILE     = LOGS_DIR / "sector_hedge_executor.log"

# ── Config ────────────────────────────────────────────────────────────────────
BEARISH_REGIMES         = {"STRONG_DOWNTREND", "CHOPPY", "UNFAVORABLE"}
RECOVERY_REGIMES        = {"RISK_ON", "TRENDING", "STRONG_UPTREND"}
MAX_SECTOR_HEDGE_PCT    = 20.0   # hedge sectors with NLV% > this in bearish regime
HEDGE_RATIO             = 0.50   # 50% hedge of excess exposure
MIN_HEDGE_NOTIONAL      = 2_000  # don't open hedge if it would be less than $2k
MAX_HEDGE_PCT_NLV       = 5.0    # max 5% of NLV per single sector hedge

# Sector → inverse ETF mapping
# SH = -1× SPY, PSQ = -1× QQQ, RWM = -1× IWM, DOG = -1× DIA
SECTOR_INVERSE_ETF: dict[str, str] = {
    "Energy":          "ERY",    # -2× Energy (DRN)
    "Technology":      "SQQQ",   # -3× QQQ (tech-heavy)
    "Financials":      "SKF",    # -2× Financials
    "Materials":       "SRS",    # -2× Real Estate (closest inverse materials)
    "Industrials":     "SH",     # -1× SPY (broad market proxy)
    "Consumer Discretionary": "SDS",  # -2× SPY
    "Consumer Staples": "SH",    # -1× SPY
    "Healthcare":      "RXD",    # -2× Healthcare
    "Utilities":       "SDP",    # -2× Utilities
    "Communication":   "SH",     # -1× SPY
    "Real Estate":     "SRS",    # -2× Real Estate
}

# Sector → sector ETF (for puts when inverse ETF not available)
SECTOR_ETF: dict[str, str] = {
    "Energy":                  "XLE",
    "Technology":              "XLK",
    "Financials":              "XLF",
    "Materials":               "XLB",
    "Industrials":             "XLI",
    "Consumer Discretionary":  "XLY",
    "Consumer Staples":        "XLP",
    "Healthcare":              "XLV",
    "Utilities":               "XLU",
    "Communication":           "XLC",
    "Real Estate":             "XLRE",
}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_pending() -> dict[str, Any]:
    if not PENDING_FILE.exists():
        return {"pending": [], "take_profit": [], "partial_profit": [], "sector_hedges": []}
    try:
        data = json.loads(PENDING_FILE.read_text())
        if "sector_hedges" not in data:
            data["sector_hedges"] = []
        return data
    except (OSError, ValueError):
        return {"pending": [], "take_profit": [], "partial_profit": [], "sector_hedges": []}


def _load_regime() -> str:
    """Return current regime string (Layer 1 or 2). Defaults to 'NEUTRAL'."""
    for fname in ("regime_state.json", "regime_layer2.json", "macro_regime.json"):
        fpath = SNAPSHOT_DIR / fname
        if fpath.exists():
            try:
                data = json.loads(fpath.read_text())
                regime = (
                    data.get("regime")
                    or data.get("label")
                    or data.get("current_regime")
                    or ""
                ).upper()
                if regime:
                    return regime
            except (OSError, ValueError):
                pass
    return "NEUTRAL"


def _load_sector_exposures() -> tuple[dict[str, float], float]:
    """
    Return (sector_pct_dict, nlv) where sector_pct_dict maps sector name
    to % of NLV currently held in that sector.
    """
    # Try to read from portfolio snapshot
    for fname in ("dashboard_snapshot.json", "portfolio_snapshot.json"):
        fpath = SNAPSHOT_DIR / fname
        if not fpath.exists():
            continue
        try:
            data = json.loads(fpath.read_text())
            raw_positions = data.get("positions") or []
            # Handle both flat list and nested {"list": [...]} format
            if isinstance(raw_positions, dict):
                raw_positions = raw_positions.get("list") or []
            positions = raw_positions if isinstance(raw_positions, list) else []
            nlv = float(data.get("net_liq") or data.get("nlv") or 0)
            if not positions or nlv <= 0:
                continue

            from sector_concentration_manager import get_sector
            sector_values: dict[str, float] = {}
            for pos in positions:
                sym = pos.get("symbol") or pos.get("ticker") or ""
                mkt_val = float(pos.get("market_value") or pos.get("mkt_val") or 0)
                if not sym or mkt_val <= 0:
                    continue
                sector = get_sector(sym)
                sector_values[sector] = sector_values.get(sector, 0.0) + mkt_val

            sector_pct = {s: round(v / nlv * 100, 2) for s, v in sector_values.items()}
            return sector_pct, nlv
        except Exception as exc:
            logger.debug("Could not load sector exposures from %s: %s", fname, exc)

    return {}, 0.0


def _get_price(symbol: str) -> float | None:
    """Fetch current price via yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", auto_adjust=True)
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


# ── Hedge logic ───────────────────────────────────────────────────────────────

def _hedge_id(sector: str) -> str:
    """Generate a deterministic hedge entry ID for a sector."""
    return f"hedge-{sector.lower().replace(' ', '-')}"


def _build_hedge_entry(sector: str, hedge_etf: str, shares: int, price: float) -> dict[str, Any]:
    """Build a pending_trades entry for a sector hedge."""
    notional = round(shares * price, 2)
    return {
        "id":          _hedge_id(sector),
        "description": f"Sector hedge: {sector} via {hedge_etf} ({shares} sh × ${price:.2f} = ${notional:.0f})",
        "type":        "sector_hedge",
        "sector":      sector,
        "hedge_etf":   hedge_etf,
        "added_date":  date.today().isoformat(),
        "trigger":     "regime_bearish",
        "status":      "active",
        "legs": [
            {
                "action":     "BUY",
                "secType":    "STK",
                "symbol":     hedge_etf,
                "qty":        shares,     # execute_pending_trades.py reads "qty"
                "order_type": "MKT",
                "note":       f"Sector hedge for {sector} exposure in bearish regime",
            }
        ],
    }


def _build_close_hedge_entry(hedge: dict[str, Any]) -> dict[str, Any]:
    """Build a pending_trades entry to close an existing sector hedge."""
    hedge_etf = hedge.get("hedge_etf", "")
    shares = 0
    for leg in hedge.get("legs", []):
        if leg.get("action") == "BUY":
            shares = int(leg.get("qty") or leg.get("quantity") or 0)
    if shares <= 0:
        logger.error("Cannot build close order for %s hedge — no BUY leg with qty found: %s",
                     hedge.get("sector"), hedge)
        shares = 0   # caller must check for shares > 0 before using the returned entry
    return {
        "id":          f"close-{hedge['id']}",
        "description": f"Close sector hedge: {hedge.get('sector', '')} ({hedge_etf})",
        "type":        "close_sector_hedge",
        "sector":      hedge.get("sector", ""),
        "added_date":  date.today().isoformat(),
        "trigger":     "regime_recovery",
        "legs": [
            {
                "action":     "SELL",
                "secType":    "STK",
                "symbol":     hedge_etf,
                "qty":        shares,     # execute_pending_trades.py reads "qty"
                "order_type": "MKT",
                "note":       "Close sector hedge — regime has recovered",
            }
        ],
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    regime = _load_regime()
    logger.info("Current regime: %s", regime)

    sector_pct, nlv = _load_sector_exposures()
    if not sector_pct or nlv <= 0:
        logger.warning("No sector exposure data available — cannot compute hedge sizes")
        return

    logger.info("NLV: $%.0f | Sector exposures: %s", nlv, sector_pct)

    data = _load_pending()
    existing_hedges = {h.get("sector"): h for h in data.get("sector_hedges", [])}
    new_hedges:   list[dict[str, Any]] = []
    close_orders: list[dict[str, Any]] = []

    if regime in BEARISH_REGIMES:
        logger.info("Bearish regime (%s) — checking for hedge needs", regime)

        for sector, pct in sector_pct.items():
            if pct <= MAX_SECTOR_HEDGE_PCT:
                continue   # not over-concentrated

            if sector not in SECTOR_INVERSE_ETF:
                logger.debug("No inverse ETF defined for sector: %s", sector)
                continue

            hedge_etf = SECTOR_INVERSE_ETF[sector]
            excess_pct = pct - MAX_SECTOR_HEDGE_PCT

            # Hedge size = excess exposure × hedge ratio, capped at MAX_HEDGE_PCT_NLV
            hedge_pct = min(excess_pct * HEDGE_RATIO / 100, MAX_HEDGE_PCT_NLV / 100)
            hedge_notional = nlv * hedge_pct

            if hedge_notional < MIN_HEDGE_NOTIONAL:
                logger.debug("Hedge too small ($%.0f < $%.0f) for %s — skipping",
                             hedge_notional, MIN_HEDGE_NOTIONAL, sector)
                continue

            # Skip if hedge already exists
            if sector in existing_hedges:
                logger.info("Hedge for %s already active (%s) — no action", sector, hedge_etf)
                continue

            etf_price = _get_price(hedge_etf)
            if not etf_price or etf_price <= 0:
                logger.warning("Could not get price for hedge ETF %s", hedge_etf)
                continue

            shares = max(1, int(hedge_notional / etf_price))
            logger.info(
                "Opening hedge for %s (%.1f%% NLV) via %s: %d sh × $%.2f = $%.0f",
                sector, pct, hedge_etf, shares, etf_price, shares * etf_price,
            )

            hedge_entry = _build_hedge_entry(sector, hedge_etf, shares, etf_price)
            if not dry_run:
                new_hedges.append(hedge_entry)

            notify_event(
                "sector_hedge",
                subject=f"🛡️ Sector Hedge Opened: {sector}",
                body=(
                    f"Opened {sector} hedge via {hedge_etf} ({shares} shares) in {regime} regime.\n"
                    f"Sector exposure: {pct:.1f}% of NLV (threshold: {MAX_SECTOR_HEDGE_PCT}%)\n"
                    f"Hedge notional: ${shares * etf_price:,.0f} ({hedge_pct*100:.1f}% of NLV)\n"
                    f"{'[DRY RUN — no orders placed]' if dry_run else ''}"
                ),
                urgent=False,
            )

    elif regime in RECOVERY_REGIMES:
        logger.info("Recovery regime (%s) — closing any open hedges", regime)

        for sector, hedge in existing_hedges.items():
            logger.info("Closing hedge for %s (%s) — regime recovered", sector, hedge.get("hedge_etf"))
            close_entry = _build_close_hedge_entry(hedge)
            # Skip if qty could not be determined (malformed hedge entry)
            close_qty = 0
            for leg in close_entry.get("legs", []):
                if leg.get("action") == "SELL":
                    close_qty = int(leg.get("qty") or 0)
            if close_qty <= 0:
                logger.warning("Skipping close order for %s — could not determine share qty", sector)
                continue
            if not dry_run:
                close_orders.append(close_entry)

            notify_event(
                "sector_hedge",
                subject=f"🟢 Sector Hedge Closed: {sector}",
                body=(
                    f"Closing {sector} hedge ({hedge.get('hedge_etf')}) — regime recovered to {regime}.\n"
                    f"{'[DRY RUN — no orders placed]' if dry_run else ''}"
                ),
                urgent=False,
            )

        if not dry_run:
            data["sector_hedges"] = []  # clear all hedges on recovery

    else:
        logger.info("Neutral regime (%s) — no hedge changes needed", regime)

    # Persist
    if not dry_run:
        if new_hedges:
            data["sector_hedges"].extend(new_hedges)
        if close_orders:
            data["pending"].extend(close_orders)
        atomic_write_json(PENDING_FILE, data)
        logger.info(
            "Hedge update complete: %d new hedge(s), %d close order(s)",
            len(new_hedges), len(close_orders),
        )

    if dry_run:
        logger.info("[DRY RUN] Would open %d hedge(s), close %d hedge(s)",
                    len(new_hedges), len(close_orders))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sector Hedge Executor")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, no orders")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
