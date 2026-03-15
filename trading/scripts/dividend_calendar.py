#!/usr/bin/env python3
"""
Dividend Calendar
=================
Fetches upcoming ex-dividend dates for portfolio holdings via yfinance.
Used by auto_options_executor to avoid writing covered calls that expire
right before an ex-date (capturing the dividend is often worth more than
the call premium, especially on high-yield energy names).

Rules:
  1. If ex-date is within the option's expiration window AND the dividend
     yield on a per-share basis exceeds the call premium, skip the call.
  2. If ex-date is < 5 days before expiry, flag it — early assignment
     risk is high when dividends are in play.
  3. Cache results for 24h to avoid hammering yfinance.

Usage:
  from dividend_calendar import get_ex_dividend_info, should_skip_call_for_dividend
"""

import json
import logging
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "logs"
CACHE_FILE = CACHE_DIR / "dividend_cache.json"
CACHE_TTL_SECONDS = 86400


def _load_cache() -> Dict[str, Any]:
    try:
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text())
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        logger.debug("Could not save dividend cache: %s", e)


def get_ex_dividend_info(symbol: str) -> Dict[str, Any]:
    """Fetch ex-dividend date and yield for a symbol.

    Returns dict with keys:
      - ex_date: ISO date string or None
      - dividend_amount: per-share amount or 0
      - annual_yield_pct: trailing annual dividend yield or 0
      - cached: whether result came from cache
    """
    cache = _load_cache()
    cached_entry = cache.get(symbol)
    if cached_entry and time.time() - cached_entry.get("fetched_at", 0) < CACHE_TTL_SECONDS:
        return {**cached_entry, "cached": True}

    result: Dict[str, Any] = {
        "symbol": symbol,
        "ex_date": None,
        "dividend_amount": 0.0,
        "annual_yield_pct": 0.0,
        "fetched_at": time.time(),
    }

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        ex_date_ts = info.get("exDividendDate")
        if ex_date_ts:
            if isinstance(ex_date_ts, (int, float)):
                result["ex_date"] = datetime.fromtimestamp(ex_date_ts).date().isoformat()
            elif isinstance(ex_date_ts, str):
                result["ex_date"] = ex_date_ts[:10]

        div_rate = info.get("dividendRate", 0) or 0
        if div_rate > 0:
            result["dividend_amount"] = round(div_rate / 4, 4)

        div_yield = info.get("dividendYield", 0) or 0
        result["annual_yield_pct"] = round(div_yield * 100, 2)

    except Exception as e:
        logger.debug("Dividend lookup failed for %s: %s", symbol, e)

    cache[symbol] = result
    _save_cache(cache)
    return {**result, "cached": False}


def should_skip_call_for_dividend(
    symbol: str,
    call_expiry: str,
    premium_per_share: float,
    current_price: float,
) -> Dict[str, Any]:
    """Determine if a covered call should be skipped to capture a dividend.

    Args:
        symbol: Stock ticker
        call_expiry: Option expiry in YYYYMMDD format
        premium_per_share: Expected premium per share from selling the call
        current_price: Current stock price

    Returns dict:
        skip: bool — True if the call should be skipped
        reason: str — Explanation
        ex_date: str or None
        dividend_amount: float
    """
    info = get_ex_dividend_info(symbol)
    ex_date_str = info.get("ex_date")
    div_amount = info.get("dividend_amount", 0)

    result = {
        "skip": False,
        "reason": "",
        "ex_date": ex_date_str,
        "dividend_amount": div_amount,
        "annual_yield_pct": info.get("annual_yield_pct", 0),
    }

    if not ex_date_str or div_amount <= 0:
        return result

    try:
        ex_date = date.fromisoformat(ex_date_str)
        expiry_date = datetime.strptime(call_expiry[:8], "%Y%m%d").date()
    except (ValueError, TypeError):
        return result

    today = date.today()

    if not (today <= ex_date <= expiry_date):
        return result

    days_before_expiry = (expiry_date - ex_date).days

    if div_amount > premium_per_share * 0.7:
        result["skip"] = True
        result["reason"] = (
            f"Ex-div {ex_date_str} (${div_amount:.2f}/sh) exceeds 70% of call premium "
            f"(${premium_per_share:.2f}) — capture dividend instead"
        )
        return result

    if days_before_expiry <= 5:
        result["skip"] = True
        result["reason"] = (
            f"Ex-div {ex_date_str} is {days_before_expiry}d before expiry — "
            f"high early-assignment risk for ${div_amount:.2f}/sh dividend"
        )
        return result

    return result


def scan_portfolio_dividends(symbols: list[str]) -> list[Dict[str, Any]]:
    """Batch scan for upcoming dividends across portfolio holdings."""
    results = []
    for sym in symbols:
        info = get_ex_dividend_info(sym)
        if info.get("ex_date"):
            ex = date.fromisoformat(info["ex_date"])
            days_until = (ex - date.today()).days
            if 0 <= days_until <= 45:
                results.append({
                    "symbol": sym,
                    "ex_date": info["ex_date"],
                    "days_until": days_until,
                    "dividend_amount": info["dividend_amount"],
                    "annual_yield_pct": info["annual_yield_pct"],
                })
    results.sort(key=lambda r: r["days_until"])
    return results
