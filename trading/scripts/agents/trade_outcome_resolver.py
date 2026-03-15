"""
Trade Outcome Resolver — periodically check IB positions against open trades
in the DB, mark closed trades, and compute exit P&L / MAE / MFE.

Runs every 30 minutes during market hours (or on-demand).
Designed to be called from agents/run_all.py as an asyncio task.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _is_market_hours() -> bool:
    """Rough check: weekday and 9:00-17:00 ET (covers pre/post-market buffer)."""
    from datetime import timezone

    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
    except ImportError:
        et = timezone(timedelta(hours=-5))
    now = datetime.now(tz=et)
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour < 17


def _get_ib_position_symbols(ib: Any) -> Dict[str, float]:
    """Return {SYMBOL: signed_position_size} from IB positions.

    Positive = long, negative = short.
    """
    out: Dict[str, float] = {}
    try:
        for pos in ib.positions():
            sec_type = getattr(pos.contract, "secType", "")
            if sec_type != "STK":
                continue
            sym = getattr(pos.contract, "symbol", "")
            if isinstance(sym, str) and sym.strip():
                qty = float(getattr(pos, "position", 0))
                out[sym.strip().upper()] = qty
    except Exception as e:
        logger.warning("Could not fetch IB positions: %s", e)
    return out


def _infer_exit_reason(
    trade: Dict[str, Any],
    last_price: float,
) -> str:
    """Best-effort guess at exit reason based on stop/TP levels."""
    entry = trade.get("entry_price") or 0
    stop = trade.get("stop_price") or 0
    tp = trade.get("profit_price") or 0
    side = (trade.get("side") or "").upper()

    if not entry or not last_price:
        return "UNKNOWN"

    if side == "SELL":
        if stop and last_price >= stop:
            return "STOP_HIT"
        if tp and last_price <= tp:
            return "TP_HIT"
    else:
        if stop and last_price <= stop:
            return "STOP_HIT"
        if tp and last_price >= tp:
            return "TP_HIT"

    return "TRAIL_HIT"


def _compute_excursions(
    symbol: str,
    side: str,
    entry_price: float,
    entry_date: str,
    ib: Any,
) -> tuple:
    """Fetch daily bars from entry to now and compute MFE/MAE.

    Returns (mae, mfe) in dollar terms per share, or (None, None) on failure.
    """
    try:
        from ib_insync import Stock, util
    except ImportError:
        return None, None
    if not getattr(ib, "isConnected", lambda: False)():
        return _excursions_yfinance(symbol, side, entry_price, entry_date)

    try:
        contract = Stock(symbol, "SMART", "USD")
        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="3 M",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        if not bars:
            return _excursions_yfinance(symbol, side, entry_price, entry_date)
        import pandas as pd

        df = util.df(bars)
        col_map = {c.lower(): c for c in df.columns}
        date_col = col_map.get("date", "date")
        high_col = col_map.get("high", "High")
        low_col = col_map.get("low", "Low")
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col])
            entry_dt = pd.to_datetime(entry_date[:10])
            df = df[df[date_col] >= entry_dt]
        if df.empty:
            return None, None
        return _calc_mae_mfe(df[high_col], df[low_col], side, entry_price)
    except Exception:
        return _excursions_yfinance(symbol, side, entry_price, entry_date)


def _excursions_yfinance(
    symbol: str, side: str, entry_price: float, entry_date: str
) -> tuple:
    try:
        import yfinance as yf
        import pandas as pd

        df = yf.download(symbol, start=entry_date[:10], progress=False)
        if df is None or df.empty:
            return None, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return _calc_mae_mfe(df["High"], df["Low"], side, entry_price)
    except Exception:
        return None, None


def _calc_mae_mfe(
    highs: Any, lows: Any, side: str, entry_price: float
) -> tuple:
    """Given high/low series, compute MAE/MFE per share."""
    is_short = side.upper() in ("SELL", "SHORT")
    if is_short:
        mae = float(highs.max()) - entry_price
        mfe = entry_price - float(lows.min())
    else:
        mae = entry_price - float(lows.min())
        mfe = float(highs.max()) - entry_price
    return round(max(0.0, mae), 4), round(max(0.0, mfe), 4)


def _get_last_price(symbol: str, ib: Any) -> Optional[float]:
    """Get last traded price for symbol via IB snapshot or yfinance."""
    if ib is not None and getattr(ib, "isConnected", lambda: False)():
        try:
            from ib_insync import Stock
            ticker = ib.reqMktData(Stock(symbol, "SMART", "USD"), snapshot=True)
            ib.sleep(2)
            price = ticker.marketPrice()
            ib.cancelMktData(ticker.contract)
            if price and price > 0:
                return float(price)
        except Exception:
            pass
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        hist = t.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


MAX_HOLDING_DAYS = 20
STALE_PNL_THRESHOLD_PCT = 0.01  # exit if |pnl%| < 1% after max holding days


def find_stale_positions(ib: Any) -> List[Dict[str, Any]]:
    """Identify open positions that have exceeded the max holding period with negligible P&L.

    Returns list of {symbol, side, qty, trade_id} dicts for positions to close.
    """
    from trade_log_db import get_open_trades

    stale: List[Dict[str, Any]] = []
    open_trades = get_open_trades()
    if not open_trades:
        return stale

    for trade in open_trades:
        entry_ts = trade.get("timestamp") or ""
        if not entry_ts:
            continue
        try:
            entry_dt = datetime.fromisoformat(entry_ts[:19])
            holding_days = max(0, (datetime.now() - entry_dt).days)
        except (ValueError, TypeError):
            continue

        if holding_days < MAX_HOLDING_DAYS:
            continue

        symbol = (trade.get("symbol") or "").strip().upper()
        entry_price = float(trade.get("entry_price") or trade.get("price") or 0)
        if not symbol or entry_price <= 0:
            continue

        last_price = _get_last_price(symbol, ib)
        if last_price is None:
            continue

        side = (trade.get("side") or "").upper()
        if side in ("SELL", "SHORT"):
            pnl_pct = (entry_price - last_price) / entry_price
        else:
            pnl_pct = (last_price - entry_price) / entry_price

        if pnl_pct < STALE_PNL_THRESHOLD_PCT:
            stale.append({
                "symbol": symbol,
                "side": side,
                "qty": int(trade.get("qty") or 0),
                "trade_id": trade.get("id"),
                "entry_price": entry_price,
                "holding_days": holding_days,
                "pnl_pct": round(pnl_pct, 4),
            })
            logger.info(
                "Stale position: %s %s held %d days, pnl=%.2f%% — flagged for exit",
                side, symbol, holding_days, pnl_pct * 100,
            )

    return stale


def close_stale_positions(ib: Any) -> int:
    """Close positions that exceed max holding period. Returns count closed."""
    stale = find_stale_positions(ib)
    if not stale:
        return 0

    closed = 0
    for pos in stale:
        symbol = pos["symbol"]
        side = pos["side"]
        qty = pos["qty"]
        if qty <= 0:
            continue
        try:
            from ib_insync import Stock, MarketOrder
            contract = Stock(symbol, "SMART", "USD")
            close_action = "BUY" if side in ("SELL", "SHORT") else "SELL"
            order = MarketOrder(close_action, qty)
            trade = ib.placeOrder(contract, order)
            ib.sleep(10)
            status = trade.orderStatus.status
            if status in ("Filled", "PartiallyFilled"):
                exit_price = float(trade.orderStatus.avgFillPrice or 0)
                from trade_log_db import update_trade_exit
                entry_price = float(pos.get("entry_price", 0)) or exit_price
                if side in ("SELL", "SHORT"):
                    pnl = (entry_price - exit_price) * qty
                else:
                    pnl = (exit_price - entry_price) * qty
                update_trade_exit(
                    trade_id=pos["trade_id"],
                    exit_price=exit_price,
                    exit_timestamp=datetime.now().isoformat(),
                    exit_reason="TIME_STOP",
                    realized_pnl=round(pnl, 2),
                    realized_pnl_pct=round(pos.get("pnl_pct", 0), 4),
                    holding_days=pos["holding_days"],
                )
                closed += 1
                logger.info("Closed stale %s %s: exit=%.2f days=%d", side, symbol, exit_price, pos["holding_days"])
            else:
                logger.warning("Stale close order not filled: %s %s", symbol, status)
        except Exception as e:
            logger.error("Failed to close stale position %s: %s", symbol, e)

    return closed


def resolve_outcomes(ib: Any) -> int:
    """Check open trades against IB positions and resolve exits.

    Returns number of trades resolved.
    """
    from trade_log_db import get_open_trades, update_trade_exit

    open_trades = get_open_trades()
    if not open_trades:
        return 0

    positions = _get_ib_position_symbols(ib)
    resolved = 0

    for trade in open_trades:
        symbol = (trade.get("symbol") or "").strip().upper()
        side = (trade.get("side") or "").upper()
        trade_id = trade.get("id")
        if not symbol or trade_id is None:
            continue

        pos_qty = positions.get(symbol, 0)

        still_open = False
        if side in ("SELL", "SHORT") and pos_qty < 0:
            still_open = True
        elif side in ("BUY", "LONG") and pos_qty > 0:
            still_open = True

        if still_open:
            continue

        entry_price = trade.get("entry_price") or trade.get("price") or 0
        if not entry_price:
            continue
        entry_price = float(entry_price)
        qty = int(trade.get("qty") or 0)
        if qty <= 0:
            continue

        last_price = _get_last_price(symbol, ib)
        if last_price is None:
            logger.warning("Could not resolve price for %s; skipping", symbol)
            continue

        exit_reason = _infer_exit_reason(trade, last_price)

        if side in ("SELL", "SHORT"):
            pnl = (entry_price - last_price) * qty
        else:
            pnl = (last_price - entry_price) * qty
        pnl_pct = pnl / (entry_price * qty) if entry_price * qty > 0 else 0.0

        entry_ts = trade.get("timestamp") or ""
        holding_days = 0
        if entry_ts:
            try:
                entry_dt = datetime.fromisoformat(entry_ts[:19])
                holding_days = max(0, (datetime.now() - entry_dt).days)
            except (ValueError, TypeError):
                pass

        mae, mfe = _compute_excursions(
            symbol, side, entry_price, entry_ts, ib,
        )

        ok = update_trade_exit(
            trade_id=trade_id,
            exit_price=last_price,
            exit_timestamp=datetime.now().isoformat(),
            exit_reason=exit_reason,
            realized_pnl=round(pnl, 2),
            realized_pnl_pct=round(pnl_pct, 4),
            holding_days=holding_days,
            max_adverse_excursion=mae,
            max_favorable_excursion=mfe,
        )
        if ok:
            resolved += 1
            logger.info(
                "Resolved %s %s: exit=%.2f pnl=%.2f (%.2f%%) reason=%s days=%d",
                side, symbol, last_price, pnl, pnl_pct * 100, exit_reason, holding_days,
            )
            try:
                from streak_tracker import record_win, record_loss
                if pnl >= 0:
                    record_win()
                else:
                    record_loss()
            except ImportError:
                pass
            try:
                from notifications import notify_info
                pnl_sign = "+" if pnl >= 0 else ""
                notify_info(
                    f"<b>Trade Closed</b>: {side} {symbol}\n"
                    f"Exit: ${last_price:.2f} | P&L: {pnl_sign}${pnl:.2f} ({pnl_sign}{pnl_pct*100:.1f}%)\n"
                    f"Reason: {exit_reason} | Days held: {holding_days}"
                )
            except Exception:
                pass

    # Reverse check: IB positions with no matching open trade in DB
    try:
        open_symbols = {
            (t.get("symbol") or "").strip().upper()
            for t in open_trades
            if t.get("symbol")
        }
        for symbol, qty in positions.items():
            if qty == 0:
                continue
            if symbol not in open_symbols:
                side = "LONG" if qty > 0 else "SHORT"
                logger.warning(
                    "Orphaned IB position detected: %s %s qty=%d — not tracked in trades.db",
                    side, symbol, abs(int(qty)),
                )
                try:
                    from notifications import notify_info
                    notify_info(
                        f"<b>Orphaned Position</b>: {side} {symbol} qty={abs(int(qty))}\n"
                        "This position exists in IB but has no matching record in trades.db. "
                        "It may be a manual trade or a missed insert."
                    )
                except Exception:
                    pass
    except Exception as exc:
        logger.warning("Orphan position check failed: %s", exc)

    return resolved


async def run_loop(
    ib: Any,
    interval_sec: int = 1800,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Run outcome resolution in a loop every interval_sec seconds.

    Designed to be used as an asyncio task in run_all.py.
    """
    logger.info("Trade outcome resolver started (interval=%ds)", interval_sec)
    while True:
        if stop_event and stop_event.is_set():
            break
        try:
            if _is_market_hours() or datetime.now().hour == 16:
                n = resolve_outcomes(ib)
                if n > 0:
                    logger.info("Resolved %d trade outcomes", n)
                stale_closed = close_stale_positions(ib)
                if stale_closed > 0:
                    logger.info("Closed %d stale positions (time stop)", stale_closed)
        except Exception as e:
            logger.error("Outcome resolver error: %s", e)
        try:
            if stop_event:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_sec)
                break
            else:
                await asyncio.sleep(interval_sec)
        except asyncio.TimeoutError:
            pass
    logger.info("Trade outcome resolver stopped")
