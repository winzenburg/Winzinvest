"""
Delta-targeted strike selection for options.

Uses IB option chain data to find the strike closest to a target delta,
giving consistent probability of profit regardless of IV environment.
Falls back to percentage-based OTM selection when chain data is unavailable.
"""

import logging
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

TARGET_DELTA_CSP = 0.25
TARGET_DELTA_COVERED_CALL = 0.20


def select_strike_by_delta(
    ib: Any,
    symbol: str,
    right: str,
    expiration: str,
    target_delta: float = 0.25,
) -> Optional[float]:
    """
    Find the strike closest to target_delta from IB's option chain.
    right: "P" for puts, "C" for calls.
    expiration: YYYYMMDD string.
    Returns strike price or None.
    """
    if ib is None:
        return None
    try:
        from ib_insync import Stock, Option, util
    except ImportError:
        return None
    if not getattr(ib, "isConnected", lambda: False)():
        return None

    try:
        stock = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(stock)
        chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
        if not chains:
            return None

        smart_chain = None
        for chain in chains:
            if chain.exchange == "SMART":
                smart_chain = chain
                break
        if smart_chain is None:
            smart_chain = chains[0]

        if expiration not in smart_chain.expirations:
            closest_exp = min(
                smart_chain.expirations,
                key=lambda e: abs(int(e) - int(expiration)),
            )
            expiration = closest_exp

        strikes = sorted(smart_chain.strikes)
        if not strikes:
            return None

        best_strike: Optional[float] = None
        best_delta_diff = float("inf")

        batch_size = 20
        current_price = _get_price(ib, stock)
        if current_price is None or current_price <= 0:
            return None

        if right == "P":
            candidate_strikes = [s for s in strikes if s <= current_price][-batch_size:]
        else:
            candidate_strikes = [s for s in strikes if s >= current_price][:batch_size]

        if not candidate_strikes:
            return None

        contracts = [
            Option(symbol, expiration, s, right, "SMART") for s in candidate_strikes
        ]
        qualified = ib.qualifyContracts(*contracts)
        if not qualified:
            return None

        tickers = ib.reqTickers(*qualified)
        ib.sleep(1)

        for t in tickers:
            greeks = t.modelGreeks or t.lastGreeks
            if greeks is None or greeks.delta is None:
                continue
            delta = abs(float(greeks.delta))
            diff = abs(delta - target_delta)
            if diff < best_delta_diff:
                best_delta_diff = diff
                best_strike = float(t.contract.strike)

        if best_strike is not None:
            logger.info(
                "Delta strike for %s %s exp=%s: strike=%.2f (target_delta=%.2f)",
                symbol, right, expiration, best_strike, target_delta,
            )
        return best_strike
    except Exception as e:
        logger.debug("Delta strike selection failed for %s: %s", symbol, e)
        return None


def _get_price(ib: Any, stock: Any) -> Optional[float]:
    try:
        [ticker] = ib.reqTickers(stock)
        ib.sleep(0.5)
        if ticker.last and ticker.last > 0:
            return float(ticker.last)
        if ticker.close and ticker.close > 0:
            return float(ticker.close)
    except Exception:
        pass
    return None
