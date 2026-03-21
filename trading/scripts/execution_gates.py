#!/usr/bin/env python3
"""
Unified risk gates run before placing an order.

Five gates: Daily Limit, Sector Concentration, Gap Risk, Regime, Position Size.
Used by execute_candidates (and optionally execute_dual_mode) before placeOrder.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sector_gates import check_sector_concentration

if TYPE_CHECKING:
    from broker_protocols import BrokerClient

logger = logging.getLogger(__name__)

try:
    from paths import TRADING_DIR as _TRADING_DIR
except ImportError:
    _TRADING_DIR = Path(__file__).resolve().parent.parent

KILL_SWITCH_PATH: str = str(_TRADING_DIR / "kill_switch.json")


def check_kill_switch(path: Optional[str] = None) -> bool:
    """Return True if execution is allowed (kill switch inactive or missing).

    Reads a JSON file with ``{"active": true/false, ...}``.
    Missing file or parse errors default to **inactive** (allow execution).
    """
    ks_path = Path(path) if path else Path(KILL_SWITCH_PATH)
    if not ks_path.exists():
        return True
    try:
        data = json.loads(ks_path.read_text())
        if isinstance(data, dict) and data.get("active") is True:
            logger.warning("[GATE] Kill switch ACTIVE: %s", data.get("reason", ""))
            return False
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.debug("Kill switch file unreadable (allowing): %s", exc)
    return True


def check_gap_risk_window(minutes_before_close: int = 60) -> bool:
    """
    Return False if within minutes_before_close of market close (4 PM ET).
    Avoids placing orders in the gap-risk window near close.
    """
    try:
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        now = datetime.now(et)
    except ImportError:
        # Python < 3.9: assume local time is ET (or set TZ); otherwise gate may be wrong
        now = datetime.now()
    close_today = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now >= close_today:
        logger.warning("[GATE] Gap risk: market closed or past close")
        return False
    mins_to_close = (close_today - now).total_seconds() / 60
    if mins_to_close < minutes_before_close:
        logger.warning("[GATE] Gap risk: %.0f min to close (min %d)", mins_to_close, minutes_before_close)
        return False
    return True


def check_regime_for_short() -> bool:
    """
    Return False if regime blocks new shorts.

    Backtesting showed that entering new shorts during STRONG_UPTREND
    (fighting the trend) and STRONG_DOWNTREND (stocks already oversold,
    bounce risk) both produce negative expectancy. Only CHOPPY and MIXED
    regimes have a viable short edge.
    """
    from regime_detector import detect_market_regime
    regime = detect_market_regime()
    if regime == "STRONG_UPTREND":
        logger.warning("[GATE] Regime: no new shorts in STRONG_UPTREND")
        return False
    if regime == "STRONG_DOWNTREND":
        logger.warning("[GATE] Regime: no new shorts in STRONG_DOWNTREND (oversold bounce risk)")
        return False
    if regime == "UNFAVORABLE":
        logger.warning("[GATE] Regime: UNFAVORABLE — mostly cash, blocking new shorts")
        return False
    return True


def check_position_sizing(
    notional: float,
    account_equity: float,
    max_notional_pct: float = 0.5,
) -> bool:
    """
    Return False if notional would exceed max_notional_pct of account equity.
    Spec: avoid single position > 50% of buying power.
    """
    if account_equity <= 0:
        return True
    limit = account_equity * max_notional_pct
    if notional > limit:
        logger.warning(
            "[GATE] Position size: notional %.0f > %.0f (%.0f%% of equity)",
            notional, limit, 100 * max_notional_pct,
        )
        return False
    return True


def check_position_concentration(
    symbol: str,
    new_notional: float,
    account_equity: float,
    ib: Optional[BrokerClient] = None,
    max_position_pct: float = 0.05,
) -> bool:
    """Return False if the resulting position would exceed max_position_pct of NLV.

    Prevents any single name from growing beyond the target allocation (default 5%).
    Checks existing holdings in the same symbol and adds the proposed notional.
    An existing position that already exceeds the cap will also block additions.
    """
    if account_equity <= 0:
        return True
    limit = account_equity * max_position_pct
    try:
        existing = 0.0
        if ib is not None:
            for item in ib.portfolio():
                if getattr(item.contract, "secType", "") != "STK":
                    continue
                if getattr(item.contract, "symbol", "") == symbol:
                    existing += abs(float(item.marketValue))
        else:
            # No live IB connection — fall back to snapshot file for existing exposure
            try:
                from paths import TRADING_DIR as _td
                import json as _json
                snap_path = _td / "logs" / "dashboard_snapshot.json"
                if snap_path.exists():
                    snap = _json.loads(snap_path.read_text())
                    pos_list = snap.get("positions", [])
                    if isinstance(pos_list, dict):
                        pos_list = pos_list.get("list", [])
                    for p in pos_list:
                        if p.get("symbol", "").upper() == symbol.upper():
                            existing += abs(p.get("market_value", 0))
            except Exception:
                pass

        combined = existing + abs(new_notional)

        # Block the trade if the existing position alone already exceeds the cap
        if existing > limit:
            logger.warning(
                "[GATE] Position concentration: %s already at $%.0f (%.1f%% of NLV, limit %.0f%%) — "
                "trim before adding more",
                symbol, existing, existing / account_equity * 100, max_position_pct * 100,
            )
            return False

        if combined > limit:
            logger.warning(
                "[GATE] Position concentration: %s would reach $%.0f (%.1f%% of NLV, limit %.0f%%)",
                symbol, combined, combined / account_equity * 100, max_position_pct * 100,
            )
            return False
    except Exception as exc:
        logger.debug("Position concentration check failed (allowing): %s", exc)
    return True


def check_portfolio_heat(
    account_equity: float,
    max_heat_pct: float = 0.08,
) -> bool:
    """Return False if total open risk across all positions exceeds max_heat_pct of equity.

    Portfolio heat = sum of (entry_price - stop_price) * qty for each open trade.
    This is the maximum dollar amount the portfolio can lose if every stop is hit
    simultaneously. Default cap: 8% of equity.
    """
    if account_equity <= 0:
        return True
    try:
        from trade_log_db import get_open_trades
        open_trades = get_open_trades()
    except Exception:
        return True

    total_risk = 0.0
    for t in open_trades:
        entry = t.get("entry_price") or t.get("price") or 0
        stop = t.get("stop_price") or 0
        qty = t.get("qty") or 0
        if not entry or not stop or not qty:
            continue
        entry, stop, qty = float(entry), float(stop), int(qty)
        side = (t.get("side") or "").upper()
        if side in ("SELL", "SHORT"):
            risk_per_share = stop - entry
        else:
            risk_per_share = entry - stop
        total_risk += max(0.0, risk_per_share) * qty

    heat_pct = total_risk / account_equity if account_equity > 0 else 0
    if heat_pct >= max_heat_pct:
        logger.warning(
            "[GATE] Portfolio heat: $%.0f at risk (%.1f%% of $%.0f equity, limit %.1f%%)",
            total_risk, heat_pct * 100, account_equity, max_heat_pct * 100,
        )
        return False
    return True


def check_all_gates(
    signal_type: str,
    symbol: str,
    notional: float,
    daily_loss: float,
    account_equity: float,
    daily_loss_limit_pct: float,
    sector_exposure: Dict[str, float],
    total_notional: float,
    max_sector_pct: float,
    minutes_before_close: int = 60,
    max_notional_pct_of_equity: float = 0.5,
    ib: Optional[BrokerClient] = None,
    account_equity_effective: Optional[float] = None,
) -> Tuple[bool, List[str]]:
    """
    Run all five gates. Return (True, []) if all pass, else (False, list of failed gate names).
    signal_type is 'SHORT' or 'LONG'. Regime gate uses IBKR when ib is provided and connected.

    account_equity: Net liquidation (for daily loss limit and portfolio heat).
    account_equity_effective: If set, used for position size and total notional cap (e.g. IBKR buying power).
    """
    failed: List[str] = []
    effective = account_equity_effective if account_equity_effective is not None and account_equity_effective > 0 else account_equity

    # 1. Daily limit (uses net equity)
    if account_equity > 0 and daily_loss >= account_equity * daily_loss_limit_pct:
        failed.append("Daily Limit")

    # 2. Sector concentration
    if not check_sector_concentration(
        sector_exposure, total_notional, symbol, signal_type, notional, max_sector_pct
    ):
        failed.append("Sector Concentration")

    # 3. Gap risk
    if not check_gap_risk_window(minutes_before_close):
        failed.append("Gap Risk")

    # 4. Regime (for shorts only)
    if signal_type == "SHORT" and not check_regime_for_short():
        failed.append("Regime")

    # 5. Position size (uses effective equity / buying power)
    if not check_position_sizing(notional, effective, max_notional_pct_of_equity):
        failed.append("Position Size")

    # 6. Total notional cap (uses effective equity / buying power)
    try:
        from risk_config import get_max_total_notional_pct
        from paths import TRADING_DIR as workspace
        max_notional_pct = get_max_total_notional_pct(workspace)
        if effective > 0 and (total_notional + notional) / effective > max_notional_pct:
            failed.append("Total Notional Cap")
    except ImportError:
        pass

    # 6b. Per-position concentration cap (max 5% of NLV per name)
    if not check_position_concentration(symbol, notional, account_equity, ib=ib, max_position_pct=0.05):
        failed.append("Position Concentration")

    # 7. Portfolio heat (uses net equity)
    if not check_portfolio_heat(account_equity, max_heat_pct=0.08):
        failed.append("Portfolio Heat")

    # 7. Losing streak cooldown
    try:
        from streak_tracker import is_on_cooldown
        if is_on_cooldown():
            failed.append("Losing Streak Cooldown")
    except ImportError:
        pass

    # 8. Correlation with existing positions
    try:
        from correlation_gate import check_correlation
        if not check_correlation(symbol, ib=ib):
            failed.append("Correlation")
    except ImportError:
        pass

    if failed:
        try:
            from audit_logger import log_gate_rejection
            log_gate_rejection(
                symbol=symbol,
                signal_type=signal_type,
                failed_gates=failed,
                context={
                    "notional": notional,
                    "daily_loss": daily_loss,
                    "account_equity": account_equity,
                    "account_equity_effective": effective,
                    "total_notional": total_notional,
                    "sector_exposure": sector_exposure,
                },
            )
        except ImportError:
            pass
        return False, failed
    return True, []
