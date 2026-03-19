#!/usr/bin/env python3
"""
Automated Options Executor
Fully automated covered calls and cash-secured puts with strict safety rules
Runs on schedule, executes qualifying opportunities automatically

UPDATED: Includes economic calendar + earnings blackout checks
"""
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from ib_insync import IB, Stock

# Add scripts dir to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from economic_calendar import is_economic_blackout, get_blackout_reason
    from earnings_calendar import check_earnings_blackout
    from sector_concentration_manager import can_add_position, check_sector_limit
    from dynamic_position_sizing import calculate_composite_position_size, get_vix_level
    from gap_risk_manager import get_gap_risk_positions, get_eod_checklist, should_close_gap_risk_positions
    from regime_detector import RegimeDetector
    CALENDAR_MODULES_LOADED = True
    STRATEGY_MODULES_LOADED = True
except ImportError as e:
    print(f"Warning: Some modules not loaded: {e}")
    CALENDAR_MODULES_LOADED = False
    STRATEGY_MODULES_LOADED = False

try:
    from dividend_calendar import should_skip_call_for_dividend
    DIVIDEND_MODULE_LOADED = True
except ImportError:
    DIVIDEND_MODULE_LOADED = False

# Paths
TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'
WATCHLIST_MULTIMODE_PATH = TRADING_DIR / 'watchlist_multimode.json'
WATCHLIST_LONGS_PATH = TRADING_DIR / 'watchlist_longs.json'
WATCHLIST_LEGACY_PATH = TRADING_DIR / 'watchlist.json'
RISK_PATH = TRADING_DIR / 'risk.json'
PENDING_TRADES_PATH = LOGS_DIR / 'pending_trades.json'

from delta_strike_selector import (
    TARGET_DELTA_COVERED_CALL,
    TARGET_DELTA_CSP,
    select_strike_by_delta,
)
from execution_policy import ExecutionPolicy, build_intent
from iv_rank import MIN_IV_RANK_FOR_PREMIUM, fetch_iv_rank
from live_allocation import get_effective_equity as _apply_alloc
from order_router import OrderRouter
from risk_config import get_max_options_per_day, get_max_options_per_month

logger = logging.getLogger(__name__)

# Load .env
ENV_PATH = TRADING_DIR / '.env'
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().split('\n'):
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

# IB connection settings
IB_HOST = os.getenv('IB_HOST', '127.0.0.1')
IB_PORT = int(os.getenv('IB_PORT', 4001))
IB_CLIENT_ID = 105  # Dedicated client ID for options (102=longs, 103=dual_mode, 107=MR)

# Telegram settings
TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TG_CHAT = os.getenv('TELEGRAM_CHAT_ID')

# Safety limits (from trading/risk.json via risk_config)
MAX_OPTIONS_PER_DAY = get_max_options_per_day(TRADING_DIR)
MAX_OPTIONS_PER_MONTH = get_max_options_per_month(TRADING_DIR)
MIN_PREMIUM_PERCENT = 0.008  # Minimum 0.8% premium (relaxed for larger account)
MAX_RISK_PER_CONTRACT = 50000  # Max $50K assignment risk per contract (~2.5% of $1.9M NLV)

LOGS_DIR.mkdir(exist_ok=True)

def round_option_strike(strike, interval: float | None = None):
    """Round strike to the nearest valid option interval.

    IB uses tiered intervals that vary by underlying price AND by the specific
    listing. The tiers below are approximate defaults; prefer using
    get_valid_strike_from_chain() when IB connectivity is available.

    Standard tiered intervals (approximate):
      >$200 → $5.00 intervals
      >$100 → $2.50 intervals
      > $25 → $2.50 intervals  (many mid-cap optionable names)
      > $5  → $1.00 or $0.50 intervals
    """
    if interval is not None:
        return round(round(strike / interval) * interval, 2)
    if strike > 200:
        iv = 5.0
    elif strike > 25:
        iv = 2.5
    elif strike > 5:
        iv = 1.0
    else:
        iv = 0.5
    return round(round(strike / iv) * iv, 2)

def count_options_today():
    """Count options trades executed today"""
    today = datetime.now().date()
    count = 0
    
    for log_file in LOGS_DIR.glob('options_*.json'):
        try:
            data = json.loads(log_file.read_text())
            trade_date = datetime.fromisoformat(data.get('executed_at', '')).date()
            if trade_date == today:
                count += 1
        except Exception:
            continue
    
    return count

def count_options_this_month():
    """Count options trades this month"""
    now = datetime.now()
    count = 0
    
    for log_file in LOGS_DIR.glob('options_*.json'):
        try:
            data = json.loads(log_file.read_text())
            trade_date = datetime.fromisoformat(data.get('executed_at', ''))
            if trade_date.month == now.month and trade_date.year == now.year:
                count += 1
        except Exception:
            continue
    
    return count


def get_already_executed_today() -> set[tuple[str, str, str]]:
    """Return a set of (ticker, right, expiry) for options sold to open today.

    Used to prevent duplicate positions when the executor is run multiple times
    in the same session (e.g. manual re-runs after a pending-trade fix).
    Only SELL_TO_OPEN / covered_call / cash_secured_put entries count —
    BUY_TO_CLOSE rolls are intentionally excluded.
    """
    today = datetime.now().date()
    executed: set[tuple[str, str, str]] = set()

    for log_file in LOGS_DIR.glob('options_*.json'):
        try:
            data = json.loads(log_file.read_text())
            trade_date = datetime.fromisoformat(data.get('executed_at', '')).date()
            if trade_date != today:
                continue
            ticker = data.get('ticker', '')
            right  = data.get('right', '')
            expiry = data.get('expiration', '')
            if ticker and right and expiry:
                executed.add((ticker.upper(), right.upper(), expiry))
        except Exception:
            continue

    return executed

def get_ib_positions(ib):
    """Get current stock positions from IB"""
    positions = []
    for pos in ib.positions():
        if pos.contract.secType == 'STK':
            positions.append({
                'ticker': pos.contract.symbol,
                'quantity': int(pos.position),
                'avgCost': float(pos.avgCost)
            })
    return positions

def check_covered_call_opportunities(ib, regime: str = "CHOPPY"):
    """Find covered call opportunities from current positions.

    Regime-gated: blocked during STRONG_DOWNTREND and UNFAVORABLE to avoid
    selling calls on positions likely to be called away at a loss or that need
    room to recover.
    Active regimes: CHOPPY, MIXED, STRONG_UPTREND.

    Uses yfinance for price data (avoids IB Error 10197 market data conflicts).
    """
    if regime in ("STRONG_DOWNTREND", "UNFAVORABLE"):
        print(f"Skipping covered call scan: regime={regime} (downtrend/unfavorable — CC assignment risk too high)")
        return []

    import yfinance as yf

    opportunities = []
    positions = get_ib_positions(ib)
    
    for pos in positions:
        if pos['quantity'] < 100:
            continue
        
        ticker = pos['ticker']
        entry = pos['avgCost']
        
        try:
            hist = yf.download(ticker, period="5d", progress=False)
            if hist is None or hist.empty:
                print(f"No price data for {ticker}")
                continue

            close_col = hist['Close']
            if hasattr(close_col, 'columns'):
                close_col = close_col.iloc[:, 0]
            current = float(close_col.iloc[-1])
            
            iv_r = fetch_iv_rank(ticker)
            if iv_r is not None and iv_r < MIN_IV_RANK_FOR_PREMIUM:
                print(f"Skipping {ticker} covered call: IV rank {iv_r:.2f} < {MIN_IV_RANK_FOR_PREMIUM}")
                continue

            gain_pct = (current - entry) / entry
            if gain_pct >= 0.005:
                from datetime import timedelta
                target_exp = (datetime.now() + timedelta(days=35)).strftime("%Y%m%d")
                delta_strike = select_strike_by_delta(
                    ib, ticker, "C", target_exp,
                    target_delta=TARGET_DELTA_COVERED_CALL,
                )
                strike = delta_strike if delta_strike else round_option_strike(current * 1.10)
                room_to_strike = (strike - current) / current
                
                if not (current * 0.8 < strike < current * 1.5):
                    print(f"Skipping {ticker}: unreasonable strike ${strike} for current ${current}")
                    continue

                if DIVIDEND_MODULE_LOADED:
                    div_check = should_skip_call_for_dividend(
                        ticker, target_exp, current * 0.015, current,
                    )
                    if div_check["skip"]:
                        print(f"Skipping {ticker} covered call: {div_check['reason']}")
                        continue
                
                if room_to_strike >= 0.04:
                    premium_estimate = current * 0.015
                    premium_pct = premium_estimate / current
                    
                    if premium_pct >= MIN_PREMIUM_PERCENT:
                        num_contracts = pos['quantity'] // 100
                        opportunities.append({
                            'ticker': ticker,
                            'type': 'covered_call',
                            'current': current,
                            'entry': entry,
                            'strike': strike,
                            'dte': 35,
                            'quantity': num_contracts,
                            'gain_pct': gain_pct,
                            'premium_estimate': premium_estimate
                        })
        except Exception as e:
            print(f"Error checking {ticker}: {e}")
            continue
    
    return opportunities

def check_csp_opportunities(regime: str = "CHOPPY"):
    """Find cash-secured put opportunities from long candidates.

    CSPs are income trades on stocks you WANT to own at a lower price.
    Sources candidates exclusively from the long watchlist and long
    candidates in the multimode watchlist — never from short opportunities.
    Skipped during STRONG_DOWNTREND and UNFAVORABLE regimes to avoid assignment losses.
    """
    opportunities = []

    if regime in ("STRONG_DOWNTREND", "UNFAVORABLE"):
        print(f"Skipping CSP scan: regime={regime} (high assignment risk)")
        return opportunities

    try:
        tickers: list = []
        if WATCHLIST_LONGS_PATH.exists():
            data = json.loads(WATCHLIST_LONGS_PATH.read_text())
            for entry in data.get("long_candidates", []):
                if isinstance(entry, dict) and entry.get("symbol"):
                    tickers.append(entry["symbol"].strip().upper())
        if WATCHLIST_MULTIMODE_PATH.exists():
            data = json.loads(WATCHLIST_MULTIMODE_PATH.read_text())
            modes = data.get("modes", {}) or {}
            for mode_key in ("sector_strength", "premium_selling"):
                for entry in (modes.get(mode_key) or {}).get("long", []):
                    if isinstance(entry, dict) and entry.get("symbol"):
                        tickers.append(entry["symbol"].strip().upper())
            # Premium-selling shorts are high-IV weak names — ideal CSP targets
            # because we collect rich premium and only get assigned at a discount.
            for entry in (modes.get("premium_selling") or {}).get("short", []):
                if isinstance(entry, dict) and entry.get("symbol"):
                    tickers.append(entry["symbol"].strip().upper())
        if not tickers and WATCHLIST_LEGACY_PATH.exists():
            data = json.loads(WATCHLIST_LEGACY_PATH.read_text())
            if isinstance(data, dict):
                for candidate in data.get("long_candidates", []):
                    if isinstance(candidate, dict) and "symbol" in candidate:
                        tickers.append(candidate["symbol"])
        tickers = list(set(tickers))
        if not tickers:
            print("No candidates found in watchlists for CSP scanning")
            return opportunities
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        return opportunities
    
    import yfinance as yf
    
    print(f"🔍 Scanning {len(tickers)} symbols for CSP opportunities...")
    
    scanned = 0
    earnings_skipped = 0
    for ticker in tickers:  # Scan full universe
        scanned += 1
        if scanned % 50 == 0:
            print(f"  Scanned {scanned}/{len(tickers)}...")
        
        # Skip if in earnings blackout
        if CALENDAR_MODULES_LOADED and check_earnings_blackout(ticker):
            earnings_skipped += 1
            continue
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='60d')
            if hist.empty:
                continue
            
            close_s = hist['Close']
            high_s = hist['High']
            if hasattr(close_s, 'columns'):
                close_s = close_s.iloc[:, 0]
            if hasattr(high_s, 'columns'):
                high_s = high_s.iloc[:, 0]
            current = float(close_s.iloc[-1])
            recent_high = float(high_s.tail(20).max())
            ema50 = close_s.ewm(span=50, adjust=False).mean().iloc[-1]
            
            pullback_pct = (recent_high - current) / recent_high
            near_support = abs(current - ema50) / current < 0.03
            
            avg_vol = hist['Volume'].tail(20).mean()
            recent_vol = hist['Volume'].iloc[-1]
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 0

            iv_r = fetch_iv_rank(ticker)
            if iv_r is not None and iv_r < MIN_IV_RANK_FOR_PREMIUM:
                continue

            if 0.015 <= pullback_pct <= 0.12 and near_support and vol_ratio < 2.0:
                strike = round_option_strike(ema50 * 0.98)
                assignment_risk = strike * 100

                if assignment_risk <= MAX_RISK_PER_CONTRACT:
                    premium_estimate = current * 0.015
                    premium_pct = premium_estimate / current
                    
                    if premium_pct >= MIN_PREMIUM_PERCENT:
                        opportunities.append({
                            'ticker': ticker,
                            'type': 'cash_secured_put',
                            'current': current,
                            'strike': strike,
                            'dte': 35,
                            'quantity': 1,
                            'pullback_pct': pullback_pct,
                            'premium_estimate': premium_estimate,
                            'assignment_risk': assignment_risk
                        })
        except Exception:
            continue
    
    if CALENDAR_MODULES_LOADED and earnings_skipped > 0:
        print(f"  Skipped {earnings_skipped} symbols in earnings blackout")
    
    return opportunities

def check_iron_condor_opportunities(ib, regime="CHOPPY"):
    """Find iron condor opportunities on SPY/QQQ.

    Iron condors sell premium when volatility is elevated but direction is unclear.
    Sell OTM put + OTM call, buy further OTM wings for protection.
    Eligible in CHOPPY/MIXED, and STRONG_UPTREND when vol is elevated.
    """
    opportunities = []
    ic_eligible = regime in ("CHOPPY", "MIXED")
    if not ic_eligible and regime == "STRONG_UPTREND":
        iv_r = fetch_iv_rank("SPY")
        if iv_r is not None and iv_r > 0.30:
            ic_eligible = True
    if not ic_eligible:
        return opportunities

    max_open_condors = 4
    existing_condors = sum(
        1 for log_file in LOGS_DIR.glob("options_*.json")
        if "iron_condor" in log_file.read_text(errors="ignore")
    )
    if existing_condors >= max_open_condors:
        return opportunities

    for symbol in ("SPY", "QQQ"):
        try:
            contract = Stock(symbol, "SMART", "USD")
            ib.qualifyContracts(contract)
            ticker_data = ib.reqMktData(contract, "", False, False)
            ib.sleep(2)
            price = ticker_data.marketPrice()
            if not price or price <= 0:
                continue

            put_strike = round_option_strike(price * 0.90)
            call_strike = round_option_strike(price * 1.10)
            put_wing = round_option_strike(price * 0.85)
            call_wing = round_option_strike(price * 1.15)

            max_risk = (put_strike - put_wing) * 100
            estimated_credit = max_risk * 0.30

            if estimated_credit < 50:
                continue

            opportunities.append({
                "ticker": symbol,
                "type": "iron_condor",
                "current": round(float(price), 2),
                "put_strike": put_strike,
                "call_strike": call_strike,
                "put_wing": put_wing,
                "call_wing": call_wing,
                "dte": 35,
                "quantity": 1,
                "max_risk": max_risk,
                "estimated_credit": estimated_credit,
            })
        except Exception:
            continue

    return opportunities


def check_protective_put_opportunities(ib, account_value, regime="MIXED"):
    """Check if protective SPY puts are needed for tail risk hedging.

    Buy SPY puts 5-10% OTM when in MIXED or UNFAVORABLE regime.
    Monthly budget from risk.json (default 0.75% of account).
    """
    opportunities = []
    if regime not in ("MIXED", "UNFAVORABLE", "STRONG_DOWNTREND"):
        return opportunities

    try:
        risk_data = json.loads(RISK_PATH.read_text()) if RISK_PATH.exists() else {}
        budget_cap = risk_data.get("options", {}).get("max_protective_put_budget_monthly", 15000)
    except Exception:
        budget_cap = 15000
    monthly_budget = min(float(budget_cap), account_value * 0.0075)

    existing_puts = sum(
        1 for log_file in LOGS_DIR.glob("options_*.json")
        if "protective_put" in log_file.read_text(errors="ignore")
    )
    if existing_puts >= 2:
        return opportunities

    try:
        spy = Stock("SPY", "SMART", "USD")
        ib.qualifyContracts(spy)
        ticker_data = ib.reqMktData(spy, "", False, False)
        ib.sleep(2)
        price = ticker_data.marketPrice()
        if not price or price <= 0:
            return opportunities

        strike = round_option_strike(price * 0.93)
        estimated_cost = price * 0.02 * 100

        if estimated_cost > monthly_budget:
            return opportunities

        opportunities.append({
            "ticker": "SPY",
            "type": "protective_put",
            "current": round(float(price), 2),
            "strike": strike,
            "dte": 30,
            "quantity": 1,
            "estimated_cost": round(estimated_cost, 2),
        })
    except Exception:
        pass

    return opportunities


def get_nearest_valid_strike(ib, ticker: str, right: str, expiry: str, target_strike: float) -> float | None:
    """Resolve target_strike to the nearest strike that actually exists in the IB chain.

    Fetches the option chain via reqSecDefOptParams and returns the closest
    listed strike to target_strike. Returns None if the chain cannot be fetched
    or has no strikes near the target.

    This prevents Error 200 'No security definition' failures caused by
    requesting strikes that don't exist (e.g. $29.5 when only $27.5/$30/$32.5 exist).
    """
    try:
        underlying = Stock(ticker, "SMART", "USD")
        ib.qualifyContracts(underlying)
        chains = ib.reqSecDefOptParams(ticker, "", "STK", underlying.conId)
        ib.sleep(1)

        all_strikes: list[float] = []
        for chain in chains:
            if expiry in chain.expirations:
                all_strikes.extend(chain.strikes)

        if not all_strikes:
            return None

        # Filter to a sensible band (±30% of target) to avoid far-away strikes
        nearby = [s for s in all_strikes if abs(s - target_strike) / max(target_strike, 1) < 0.30]
        if not nearby:
            nearby = all_strikes

        nearest = min(nearby, key=lambda s: abs(s - target_strike))
        if nearest != target_strike:
            print(f"  Strike resolved: {ticker} {right} {expiry}  ${target_strike} → ${nearest} (nearest listed)")
        return float(nearest)
    except Exception as e:
        print(f"  Warning: could not resolve strike for {ticker}: {e}")
        return None


async def auto_close_duplicate_positions(ib: IB, router: OrderRouter) -> list[dict]:
    """Detect and close extra contracts where the same (symbol, right, expiry, strike)
    appears more than once in today's execution logs but IB shows qty > -1 (for shorts).

    Compares today's options_*.json logs against live IB positions. For each
    duplicate entry, buys 1 contract to bring the position back to -1.
    Returns list of close results.
    """
    today = datetime.now().date()
    from collections import Counter

    sold_counts: Counter = Counter()
    for log_file in LOGS_DIR.glob("options_*.json"):
        try:
            data = json.loads(log_file.read_text())
            dt = datetime.fromisoformat(data.get("executed_at", "")).date()
            if dt != today:
                continue
            key = (
                data.get("ticker", "").upper(),
                data.get("right", "").upper(),
                data.get("expiration", ""),
                float(data.get("strike", 0)),
            )
            sold_counts[key] += 1
        except Exception:
            continue

    dupes = {k: v for k, v in sold_counts.items() if v > 1}
    if not dupes:
        return []

    print(f"\n  Duplicate positions detected — auto-closing extras: {list(dupes.keys())}")
    results: list[dict] = []

    for (sym, right, expiry, strike), count in dupes.items():
        extras = count - 1
        print(f"  BUY {extras}x {sym} {expiry} ${strike}{right} to close duplicate(s)...")
        try:
            intent = build_intent(
                symbol=sym, side="BUY", quantity=extras,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="auto_options_executor.py",
                sec_type="OPT", expiry=expiry, strike=strike, right=right,
            )
            result = await router.submit(intent, wait_for_fill=True)
            if result.success:
                fill = result.avg_fill_price
                print(f"  {sym} BTC {extras}: {result.status.value if result.status else 'unknown'}  fill=${fill:.2f}")
                entry = {
                    "symbol": sym, "right": right, "expiry": expiry, "strike": strike,
                    "qty_closed": extras, "status": result.status.value if result.status else "submitted",
                    "fill_price": fill, "closed_at": datetime.now().isoformat(),
                }
                results.append(entry)
                log_path = LOGS_DIR / f"btc_duplicate_{sym}_{int(time.time())}.json"
                log_path.write_text(json.dumps(entry, indent=2))
            else:
                logger.error("Failed to close %s duplicate: %s", sym, result.error)
                results.append({"symbol": sym, "status": "error", "error": result.error or "unknown"})
        except Exception as e:
            logger.error("Failed to close %s duplicate: %s", sym, e)
            results.append({"symbol": sym, "status": "error", "error": str(e)})

    return results


async def execute_option_trade(
    ib: IB, router: OrderRouter, opportunity: dict,
) -> dict | None:
    """Execute option trade via OrderRouter, preferring delta-targeted strikes."""
    ticker = opportunity['ticker']
    strike = opportunity['strike']
    dte = opportunity['dte']
    quantity = opportunity['quantity']

    right = 'C' if opportunity['type'] == 'covered_call' else 'P'
    target_delta = TARGET_DELTA_COVERED_CALL if right == 'C' else TARGET_DELTA_CSP

    from datetime import timedelta
    target_exp = (datetime.now() + timedelta(days=dte)).strftime("%Y%m%d")
    delta_strike = select_strike_by_delta(ib, ticker, right, target_exp, target_delta)
    if delta_strike is not None:
        strike = delta_strike

    chain_strike = get_nearest_valid_strike(ib, ticker, right, target_exp, strike)
    if chain_strike is None:
        print(f"  Could not resolve a valid strike for {ticker} {right} {target_exp} — skipping")
        return None
    strike = chain_strike

    try:
        resolved = await router.contract_cache.resolve_option(
            ticker, target_exp, strike, right,
        )
        if resolved is None:
            print(f"Could not resolve option contract for {ticker} ${strike}{right}")
            return None

        mid: float = 0.0
        for mdt in (1, 3, 4):
            ib.reqMarketDataType(mdt)
            [ticker_data] = ib.reqTickers(resolved.ib_contract)
            ib.sleep(3)

            bid = getattr(ticker_data, 'bid', 0) or 0
            ask = getattr(ticker_data, 'ask', 0) or 0
            last = getattr(ticker_data, 'last', 0) or 0
            close = getattr(ticker_data, 'close', 0) or 0
            if isinstance(bid, float) and bid != bid:
                bid = 0
            if isinstance(ask, float) and ask != ask:
                ask = 0
            if isinstance(last, float) and last != last:
                last = 0
            if isinstance(close, float) and close != close:
                close = 0
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2
                break
            elif last > 0:
                mid = last
                break
            elif close > 0:
                mid = close
                break
            else:
                mp = ticker_data.marketPrice()
                if mp and isinstance(mp, (int, float)) and mp > 0 and mp == mp:
                    mid = mp
                    break
        else:
            premium_est = opportunity.get('premium_estimate', 0)
            if premium_est and premium_est > 0:
                mid = premium_est
                print(f"Using estimated premium ${mid:.2f} for {ticker} ${strike}{right}")
            else:
                print(f"No market data for {ticker} ${strike}{right}")
                return None

        premium_pct = mid / opportunity['current']
        if premium_pct < MIN_PREMIUM_PERCENT:
            print(f"Premium too low: {premium_pct*100:.2f}% < {MIN_PREMIUM_PERCENT*100:.2f}%")
            return None

        intent = build_intent(
            symbol=ticker, side="SELL", quantity=quantity,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="auto_options_executor.py",
            sec_type="OPT", expiry=target_exp, strike=strike, right=right,
            metadata={"type": opportunity["type"], "premium_mid": mid},
        )

        submit_result = await router.submit(
            intent, resolved=resolved, wait_for_fill=True,
        )

        if submit_result.is_filled or submit_result.is_partial:
            fill_price = submit_result.avg_fill_price
            filled_qty = submit_result.filled_qty or quantity
            trade_record = {
                'ticker': ticker,
                'type': opportunity['type'],
                'strike': strike,
                'right': right,
                'expiration': target_exp,
                'quantity': filled_qty,
                'fill_price': fill_price,
                'premium_collected': fill_price * filled_qty * 100,
                'executed_at': datetime.now().isoformat(),
                'status': 'filled',
            }
            log_file = LOGS_DIR / f"options_{int(time.time())}.json"
            log_file.write_text(json.dumps(trade_record, indent=2))
            return trade_record
        else:
            print(f"Order not filled: {submit_result.status.value if submit_result.status else 'unknown'} — {submit_result.error or ''}")
            return None

    except Exception as e:
        logger.error("Error executing %s $%s%s: %s", ticker, strike, right, e)
        return None

def get_current_positions(ib) -> list:
    """Get current portfolio positions from IB"""
    positions = []
    try:
        for pos in ib.positions():
            positions.append({
                'symbol': pos.contract.symbol,
                'quantity': int(pos.position),
                'type': 'stock' if pos.contract.secType == 'STK' else 'option',
            })
    except Exception as e:
        print(f"Warning: Could not fetch positions: {e}")
    return positions

def send_telegram(text):
    """Send Telegram notification"""
    if not (TG_TOKEN and TG_CHAT):
        return False
    
    import urllib.parse, urllib.request
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': TG_CHAT,
        'text': text,
        'parse_mode': 'Markdown'
    }).encode()
    
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

async def process_pending_trades(
    ib: IB, router: OrderRouter, dry_run: bool = False,
) -> list[dict]:
    """Execute any trades queued in logs/pending_trades.json by the alert monitor.

    Each entry must have: action (SELL_TO_OPEN/BUY_TO_CLOSE), symbol, sec_type,
    right (C/P), strike, expiry (YYYYMMDD), quantity.

    Clears the file after processing so trades don't re-execute on next run.
    Returns list of execution results.
    """
    if not PENDING_TRADES_PATH.exists():
        return []

    try:
        pending = json.loads(PENDING_TRADES_PATH.read_text())
    except Exception as e:
        print(f"  Could not read pending_trades.json: {e}")
        return []

    trades = pending.get("trades", [])
    if not trades:
        return []

    print(f"\n  Processing {len(trades)} pending trade(s) from alert monitor...")
    results: list[dict] = []
    already_executed = get_already_executed_today()

    for trade_entry in trades:
        sym = trade_entry.get("symbol", "")
        action = trade_entry.get("action", "")
        right = trade_entry.get("right", "C")
        qty = int(trade_entry.get("quantity", 1))
        note = trade_entry.get("note", "")

        raw_strike = trade_entry.get("strike", 0)
        raw_expiry = str(trade_entry.get("expiry", ""))

        if isinstance(raw_strike, str) and raw_strike.startswith("auto_"):
            print(f"     Skipping {sym}: strike '{raw_strike}' is an unresolved placeholder")
            results.append({"symbol": sym, "action": action, "status": "skipped", "reason": f"unresolved strike placeholder: {raw_strike}"})
            continue
        if raw_expiry.startswith("auto_"):
            print(f"     Skipping {sym}: expiry '{raw_expiry}' is an unresolved placeholder")
            results.append({"symbol": sym, "action": action, "status": "skipped", "reason": f"unresolved expiry placeholder: {raw_expiry}"})
            continue

        try:
            strike = float(raw_strike)
        except (TypeError, ValueError):
            print(f"     Skipping {sym}: could not parse strike '{raw_strike}' as a number")
            results.append({"symbol": sym, "action": action, "status": "skipped", "reason": f"invalid strike: {raw_strike}"})
            continue

        expiry = raw_expiry
        print(f"\n  -> {action} {qty}x {sym} {expiry} {strike}{right}  [{note}]")

        if action == "SELL_TO_OPEN":
            dup_key = (sym.upper(), right.upper(), str(expiry))
            if dup_key in already_executed:
                print(f"     Skipping {sym} {right} {expiry}: already sold to open today (duplicate guard)")
                results.append({"symbol": sym, "action": action, "status": "skipped", "reason": "duplicate: already executed today"})
                continue

        if dry_run:
            print("     [DRY RUN — not sending order]")
            results.append({"symbol": sym, "action": action, "status": "dry_run"})
            continue

        try:
            resolved_strike = get_nearest_valid_strike(ib, sym, right, expiry, strike)
            if resolved_strike is None:
                print(f"     Could not resolve valid strike for {sym} {right} {expiry} — skipping")
                results.append({"symbol": sym, "action": action, "status": "skipped", "reason": "no valid strike in chain"})
                continue
            if resolved_strike != strike:
                print(f"     Strike adjusted: ${strike} -> ${resolved_strike} (nearest listed)")
                strike = resolved_strike

            if action == "SELL_TO_OPEN":
                side = "SELL"
            elif action == "BUY_TO_CLOSE":
                side = "BUY"
            else:
                print(f"     Unknown action '{action}' — skipping")
                continue

            intent = build_intent(
                symbol=sym, side=side, quantity=qty,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="auto_options_executor.py",
                sec_type="OPT", expiry=expiry, strike=strike, right=right,
                metadata={"pending_action": action, "note": note},
            )

            submit_result = await router.submit(intent, wait_for_fill=True)
            fill_price = submit_result.avg_fill_price
            status_str = submit_result.status.value if submit_result.status else "unknown"

            if submit_result.success:
                print(f"     Placed: {status_str}  fill: ${fill_price:.2f}")
            else:
                print(f"     Failed: {submit_result.error}")

            results.append({
                "symbol": sym, "action": action, "qty": qty,
                "strike": strike, "expiry": expiry, "right": right,
                "status": status_str, "fill_price": fill_price,
                "executed_at": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error("Pending trade failed for %s: %s", sym, e)
            results.append({"symbol": sym, "action": action, "status": "error", "error": str(e)})

    archived_path = LOGS_DIR / f"pending_trades_executed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    pending["executed_results"] = results
    pending["processed_at"] = datetime.now().isoformat()
    archived_path.write_text(json.dumps(pending, indent=2))
    PENDING_TRADES_PATH.unlink(missing_ok=True)
    print(f"  Archived to {archived_path.name}")

    return results


async def async_main() -> None:
    _mode = os.getenv("TRADING_MODE", "paper")
    if _mode == "live":
        print("LIVE TRADING MODE — real money at risk")
    print(f"Auto Options Executor Starting [{_mode.upper()}]...")

    try:
        from agents.risk_monitor import is_kill_switch_active
        if is_kill_switch_active():
            print("Kill switch active — halting options executor")
            return
    except ImportError:
        pass

    try:
        from drawdown_circuit_breaker import is_entries_halted, get_position_scale
        if is_entries_halted():
            print("Drawdown breaker tier 2+ — new entries halted")
            return
        _breaker_scale = get_position_scale()
        if _breaker_scale < 1.0:
            print(f"Drawdown breaker active — sizing reduced to {_breaker_scale:.0%}")
    except ImportError:
        _breaker_scale = 1.0

    if CALENDAR_MODULES_LOADED:
        today = datetime.now().date().strftime("%Y-%m-%d")
        if is_economic_blackout(today):
            reason = get_blackout_reason(today)
            print(f"ECONOMIC BLACKOUT TODAY: {reason}")
            print("Trading halted. Exiting.")
            return

    today_count = count_options_today()
    month_count = count_options_this_month()

    print(f"Options today: {today_count}/{MAX_OPTIONS_PER_DAY}")
    print(f"Options this month: {month_count}/{MAX_OPTIONS_PER_MONTH}")

    if today_count >= MAX_OPTIONS_PER_DAY:
        print("Daily limit reached")
        return

    if month_count >= MAX_OPTIONS_PER_MONTH:
        print("Monthly limit reached")
        return

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        print("Connected to IB Gateway")
    except Exception as e:
        logger.error("Failed to connect to IB: %s", e)
        return

    router = OrderRouter(
        ib,
        state_store_path=LOGS_DIR / "options_order_state.jsonl",
        fill_timeout=10.0,
    )

    try:
        await router.startup()
        print("OrderRouter started (reconciliation complete)")

        current_positions = get_current_positions(ib)
        account_value = 0.0
        try:
            ib.reqAccountSummary()
            ib.sleep(2)
            for item in ib.accountSummary():
                if item.tag == "NetLiquidation" and item.currency == "USD":
                    account_value = float(item.value)
                    break
        except Exception as e:
            print(f"Warning: Could not fetch account value from IB: {e}")
        if account_value <= 0:
            try:
                for av in ib.accountValues():
                    if av.tag == "NetLiquidation" and av.currency == "USD":
                        account_value = float(av.value)
                        break
            except Exception:
                pass
        if account_value <= 0 and _mode == "live":
            print("ERROR: Could not read live NLV — halting to prevent wrong sizing")
            return
        if account_value <= 0:
            account_value = 100_000.0
            print(f"Warning: Using paper fallback NLV ${account_value:,.0f}")
        account_value = _apply_alloc(account_value)
        print(f"Account value (allocation-adjusted): ${account_value:,.0f}")

        risk_cfg: dict = {}
        if RISK_PATH.exists():
            try:
                risk_cfg = json.loads(RISK_PATH.read_text())
            except Exception:
                pass

        await auto_close_duplicate_positions(ib, router)

        pending_results = await process_pending_trades(
            ib, router, dry_run=(_mode != "live"),
        )
        if pending_results:
            executed_count = sum(1 for r in pending_results if r.get("status") not in ("error", "dry_run"))
            print(f"  Pending trades processed: {executed_count}/{len(pending_results)} executed")

        regime = "CHOPPY"
        macro_multiplier = 1.0
        if STRATEGY_MODULES_LOADED:
            try:
                from regime_detector import detect_market_regime, get_macro_size_multiplier
                regime = detect_market_regime()
                macro_multiplier = get_macro_size_multiplier()
                print(f"Regime: {regime} | Macro size multiplier: {macro_multiplier:.2f}×")
            except Exception as e:
                print(f"Regime detection failed (using CHOPPY, multiplier 1.0): {e}")

        cc_opps = check_covered_call_opportunities(ib, regime=regime)
        csp_opps = check_csp_opportunities(regime=regime)
        ic_opps = check_iron_condor_opportunities(ib, regime=regime)
        pp_opps = check_protective_put_opportunities(ib, account_value, regime=regime)

        print(f"\nFound:")
        print(f"  {len(cc_opps)} covered call opportunities")
        print(f"  {len(csp_opps)} cash-secured put opportunities")
        print(f"  {len(ic_opps)} iron condor opportunities (SPY/QQQ)")
        print(f"  {len(pp_opps)} protective put opportunities (SPY)")

        earnings_safe_opps: list[dict] = []
        if CALENDAR_MODULES_LOADED:
            print("\n Checking earnings blackout...")
            for opp in cc_opps + csp_opps:
                try:
                    from earnings_calendar import get_earnings_date
                    ed = get_earnings_date(opp['ticker'])
                    earnings_str = ed.get("earnings_date")
                    days_until = None
                    if earnings_str:
                        from datetime import datetime as _dt
                        earnings_dt = _dt.strptime(earnings_str, "%Y-%m-%d").date()
                        days_until = (earnings_dt - _dt.now().date()).days
                    if days_until is not None and 0 <= days_until <= 7:
                        print(f"  Skipping {opp['ticker']}: earnings in {days_until} day(s) ({earnings_str})")
                        continue
                    opp['_days_until_earnings'] = days_until
                    earnings_safe_opps.append(opp)
                except Exception as e:
                    logger.warning("Earnings check failed for %s: %s", opp['ticker'], e)
                    earnings_safe_opps.append(opp)
        else:
            earnings_safe_opps = cc_opps + csp_opps

        valid_opps: list[dict] = []
        if STRATEGY_MODULES_LOADED:
            print("\n Checking sector concentration...")
            for opp in earnings_safe_opps:
                sector_check = can_add_position(opp['ticker'], current_positions)
                if sector_check['allowed']:
                    valid_opps.append(opp)
                else:
                    print(f"  {opp['ticker']}: {sector_check['reason']}")
        else:
            valid_opps = earnings_safe_opps

        print(f"Sector-compliant opportunities: {len(valid_opps)}")

        already_executed = get_already_executed_today()
        if already_executed:
            print(f"\n Already executed today: {sorted(already_executed)}")
        deduped_opps: list[dict] = []
        for opp in valid_opps:
            right = 'C' if opp['type'] == 'covered_call' else 'P'
            from datetime import timedelta
            exp = (datetime.now() + timedelta(days=opp.get('dte', 35))).strftime('%Y%m%d')
            key = (opp['ticker'].upper(), right, exp)
            if key in already_executed:
                print(f"  Skipping {opp['ticker']} {right} (already sold to open today)")
            else:
                deduped_opps.append(opp)
        valid_opps = deduped_opps

        executed: list[dict] = []
        remaining = MAX_OPTIONS_PER_DAY - today_count

        max_single_option_alloc = risk_cfg.get("options", {}).get(
            "max_single_option_pct_of_equity", 0.03
        )

        for opp in valid_opps[:remaining]:
            if STRATEGY_MODULES_LOADED:
                vix_data = get_vix_level()
                vix = vix_data['vix'] if vix_data['vix'] else 20

                sizing = calculate_composite_position_size(
                    symbol=opp['ticker'],
                    account_value=account_value,
                    vix=vix,
                    days_until_earnings=opp.get('_days_until_earnings'),
                    peak_value=account_value
                )
                composite = sizing['composite_multiplier']
            else:
                composite = 1.0

            # macro_multiplier: FRED-based regime band (1.0 RISK_ON → 0.25 DEFENSIVE)
            max_notional = account_value * max_single_option_alloc * composite * _breaker_scale * macro_multiplier
            assignment_cost = opp['strike'] * 100
            if assignment_cost > 0:
                nlv_based_qty = max(1, int(max_notional / assignment_cost))
            else:
                nlv_based_qty = 1

            if opp['type'] == 'covered_call':
                adjusted_qty = min(opp['quantity'], nlv_based_qty)
            else:
                adjusted_qty = nlv_based_qty

            if adjusted_qty < 1:
                print(f"Skipping {opp['ticker']}: sizing too small")
                continue

            opp['quantity'] = adjusted_qty
            print(f"{opp['ticker']}: {opp['quantity']} contracts (${assignment_cost * adjusted_qty:,.0f} notional, composite={composite:.0%})")

            print(f"\nExecuting: {opp['ticker']} ${opp['strike']} {opp['type']}")
            result = await execute_option_trade(ib, router, opp)

            if result:
                executed.append(result)
                print(f"Filled: ${result['fill_price']:.2f}, Premium: ${result['premium_collected']:.2f}")

                msg = f"*AUTO-EXECUTED Options*\n\n"
                msg += f"*{result['ticker']}* ${result['strike']} {result['right']}\n"
                msg += f"Type: {result['type'].replace('_', ' ').title()}\n"
                msg += f"Premium: ${result['premium_collected']:.2f}\n"
                msg += f"Expiration: {result['expiration']}\n"
                msg += f"\nTrade logged and confirmed"

                send_telegram(msg)
            else:
                print("Failed to execute")

        if not executed:
            print("\nNo trades executed (no qualifying opportunities)")
        else:
            print(f"\nExecuted {len(executed)} options trades")

        if ic_opps or pp_opps:
            print("\nCombined strategy (regime-gated):")
            if ic_opps:
                for o in ic_opps[:3]:
                    print(f"  Iron condor: {o['ticker']} put ${o['put_strike']} / call ${o['call_strike']} (~${o['estimated_credit']:.0f} credit)")
            if pp_opps:
                for o in pp_opps[:2]:
                    print(f"  Protective put: SPY ${o['strike']} (~${o['estimated_cost']:.0f} cost)")
            print("  (IC/PP are not auto-executed in this run; execute manually or enable in code)")

        if STRATEGY_MODULES_LOADED:
            print("\nGap Risk Check:")
            gap_checklist = get_eod_checklist(current_positions)
            print(f"  Time to close: {gap_checklist['time_remaining_min']:.1f} minutes")
            if gap_checklist['gap_risk_positions']:
                print(f"  {len(gap_checklist['gap_risk_positions'])} position(s) with gap risk:")
                for pos in gap_checklist['gap_risk_positions']:
                    print(f"    - {pos['symbol']} {pos['type']}")
                if gap_checklist['should_act']:
                    print(f"\n{gap_checklist['summary']}")
            else:
                print("  No gap risk positions")

    finally:
        await router.shutdown()
        ib.disconnect()
        print("\nDisconnected from IB")


def main() -> None:
    """Sync wrapper preserving the existing scheduler/subprocess interface."""
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
