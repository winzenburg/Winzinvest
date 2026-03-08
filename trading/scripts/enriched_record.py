"""
Shared helper for building enriched trade records.

All executors call build_enriched_record() to produce a consistent dict with
entry-time metrics (regime, conviction, ATR, screening scores) alongside the
standard execution fields. The resulting dict is compatible with both
trade_log_db.insert_trade() and the JSONL execution log.
"""

from datetime import datetime
from typing import Any, Dict, Optional


def build_enriched_record(
    *,
    symbol: str,
    side: str,
    action: str,
    source_script: str,
    status: str,
    order_id: Optional[int] = None,
    quantity: int = 0,
    entry_price: float = 0.0,
    stop_price: float = 0.0,
    profit_price: float = 0.0,
    regime_at_entry: Optional[str] = None,
    conviction_score: Optional[float] = None,
    atr_at_entry: Optional[float] = None,
    rs_pct: Optional[float] = None,
    composite_score: Optional[float] = None,
    structure_quality: Optional[float] = None,
    rvol_atr: Optional[float] = None,
    reason: Optional[str] = None,
    signal_price: Optional[float] = None,
    slippage: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a fully-enriched execution record ready for DB and JSONL logging.

    Parameters
    ----------
    symbol : str
        Ticker symbol.
    side : str
        "SHORT" or "LONG".
    action : str
        IB action string ("SELL" or "BUY").
    source_script : str
        Originating executor filename.
    status : str
        Order status ("Filled", "SKIPPED", "CANCELLED", "ERROR", etc.).
    order_id : int, optional
        IB order ID.
    quantity : int
        Number of shares/contracts.
    entry_price, stop_price, profit_price : float
        Price levels.
    regime_at_entry : str, optional
        Market regime at time of entry.
    conviction_score : float, optional
        Conviction score from candidate_ranking.
    atr_at_entry : float, optional
        14-day ATR at entry.
    rs_pct, composite_score, structure_quality, rvol_atr : float, optional
        NX screening metrics from the candidate dict.
    reason : str, optional
        Human-readable reason (for SKIPPED/ERROR).
    extra : dict, optional
        Any additional fields to merge in (e.g. score, momentum).
    """
    rec: Dict[str, Any] = {
        "symbol": symbol.strip().upper(),
        "type": side,
        "action": action,
        "source_script": source_script,
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "quantity": quantity,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "profit_price": profit_price,
    }

    if order_id is not None:
        rec["orderId"] = order_id

    if regime_at_entry is not None:
        rec["regime_at_entry"] = regime_at_entry
    if conviction_score is not None:
        rec["conviction_score"] = round(conviction_score, 4)
    if atr_at_entry is not None:
        rec["atr_at_entry"] = round(atr_at_entry, 4)
    if rs_pct is not None:
        rec["rs_pct"] = round(rs_pct, 4)
    if composite_score is not None:
        rec["composite_score"] = round(composite_score, 4)
    if structure_quality is not None:
        rec["structure_quality"] = round(structure_quality, 4)
    if rvol_atr is not None:
        rec["rvol_atr"] = round(rvol_atr, 4)

    # R-multiple: initial risk in dollar terms = |entry - stop| * qty
    if entry_price > 0 and stop_price > 0 and quantity > 0:
        risk_per_share = abs(entry_price - stop_price)
        rec["initial_risk_r"] = round(risk_per_share * quantity, 2)
    else:
        rec["initial_risk_r"] = None

    if slippage is not None:
        rec["slippage"] = round(slippage, 4)
    elif signal_price is not None and signal_price > 0 and entry_price > 0:
        rec["slippage"] = round(abs(entry_price - signal_price), 4)

    if reason:
        rec["reason"] = reason

    if extra:
        rec.update(extra)

    return rec
