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
    from dynamic_position_sizing import (
        calculate_composite_position_size,
        get_vix_level,
        get_options_vix_multiplier,
    )
    from gap_risk_manager import get_gap_risk_positions, get_eod_checklist, should_close_gap_risk_positions
    CALENDAR_MODULES_LOADED = True
    STRATEGY_MODULES_LOADED = True
except ImportError as e:
    logging.warning("Some modules not loaded: %s", e)
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
from env_loader import load_env
from order_router import OrderRouter
from risk_config import get_max_options_per_day, get_max_options_per_month, get_max_single_option_pct_of_equity

logger = logging.getLogger(__name__)

ENV_PATH = TRADING_DIR / ".env"
load_env(ENV_PATH)

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
MIN_PREMIUM_PERCENT = 0.005  # Minimum 0.5% premium — lowered from 0.8% to capture more CC/CSP opportunities on lower-vol holdings
MAX_CSP_RISK_PCT = get_max_single_option_pct_of_equity(TRADING_DIR)  # From risk.json (currently 5%)

LOGS_DIR.mkdir(exist_ok=True)


def _estimate_premium(
    symbol: str,
    strike: float,
    spot: float,
    right: str = "P",
    dte: int = 35,
) -> float:
    """Estimate option premium using live bid/ask or IV-derived approximation.

    Falls back to 1.5% of spot if market data is unavailable.

    Args:
        right: "P" for put, "C" for call
    """
    fallback = spot * 0.015
    try:
        import yfinance as yf
        import math

        ticker_obj = yf.Ticker(symbol)
        exp_dates = ticker_obj.options
        if not exp_dates:
            return fallback

        target_date = (datetime.now().date().__class__.fromordinal(
            datetime.now().date().toordinal() + dte
        )).strftime("%Y-%m-%d")
        closest_exp = min(exp_dates, key=lambda d: abs(
            (datetime.strptime(d, "%Y-%m-%d").date() - datetime.now().date()).days - dte
        ))

        chain = ticker_obj.option_chain(closest_exp)
        opts = chain.puts if right == "P" else chain.calls

        if right == "P":
            near = opts[opts["strike"] <= strike * 1.01]
            if not near.empty:
                row = near.iloc[-1]
            else:
                return fallback
        else:
            near = opts[opts["strike"] >= strike * 0.99]
            if not near.empty:
                row = near.iloc[0]
            else:
                return fallback

        bid = float(row.get("bid", 0) or 0)
        ask = float(row.get("ask", 0) or 0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2

        iv = float(row.get("impliedVolatility", 0) or 0)
        if iv > 0:
            actual_dte = max(1, (datetime.strptime(closest_exp, "%Y-%m-%d").date() - datetime.now().date()).days)
            return spot * iv * math.sqrt(actual_dte / 365) * 0.4
    except Exception:
        pass
    return fallback


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
        logger.info(f"Skipping covered call scan: regime={regime} (downtrend/unfavorable — CC assignment risk too high)")
        return []

    import yfinance as yf

    # Leveraged ETFs have no listed options and their upside must not be capped.
    # This set matches post_entry_premium.py to ensure consistent behavior.
    _LEVERAGED_ETF_NO_CC = frozenset({
        "GDXU", "KORU", "TQQQ", "SOXL", "LABU", "SPXL", "TNA",
        "MEXX", "HIBL", "NAIL", "FNGU", "DFEN", "WANT", "CURE",
        "ERX",  "TECL", "WEBL", "DPST", "RETL", "UTSL", "INDL",
    })

    opportunities = []
    positions = get_ib_positions(ib)
    
    for pos in positions:
        if pos['quantity'] < 100:
            continue
        
        ticker = pos['ticker']
        if ticker.upper() in _LEVERAGED_ETF_NO_CC:
            logger.info("Skipping CC for %s: leveraged ETF — upside must remain uncapped", ticker)
            continue
        entry = pos['avgCost']
        
        try:
            hist = yf.download(ticker, period="5d", progress=False)
            if hist is None or hist.empty:
                logger.info(f"No price data for {ticker}")
                continue

            close_col = hist['Close']
            if hasattr(close_col, 'columns'):
                close_col = close_col.iloc[:, 0]
            current = float(close_col.iloc[-1])
            
            iv_r = fetch_iv_rank(ticker)
            # Covered calls: use a lower IV rank floor (0.25) than CSPs/premium sells (0.45).
            # We already own the stock so there is no downside assignment risk — selling a call
            # is pure income on an existing position. Also allow None (data unavailable) to pass
            # so a yfinance outage doesn't silently kill all CC opportunities.
            CC_MIN_IV_RANK = 0.25
            if iv_r is not None and iv_r < CC_MIN_IV_RANK:
                logger.info(
                    f"Skipping {ticker} covered call: IV rank {iv_r:.2f} < {CC_MIN_IV_RANK} "
                    f"(CC threshold, CSP threshold is {MIN_IV_RANK_FOR_PREMIUM})"
                )
                continue
            if iv_r is None:
                logger.info(f"{ticker} covered call: IV rank unavailable — proceeding anyway")

            gain_pct = (current - entry) / entry
            # Wheel discipline: write CCs on any long position, even if slightly
            # underwater.  Only skip if down >15% (likely needs recovery room, not
            # a cap on upside).  The room_to_strike check below protects against
            # selling calls too close to the money.
            if gain_pct < -0.15:
                logger.info(
                    "Skipping %s covered call: down %.1f%% — needs recovery room before capping upside",
                    ticker, gain_pct * 100,
                )
                continue

            from datetime import timedelta
            target_exp = (datetime.now() + timedelta(days=35)).strftime("%Y%m%d")
            try:
                delta_strike = select_strike_by_delta(
                    ib, ticker, "C", target_exp,
                    target_delta=TARGET_DELTA_COVERED_CALL,
                )
            except RuntimeError:
                delta_strike = None
            strike = delta_strike if delta_strike else round_option_strike(current * 1.10)
            room_to_strike = (strike - current) / current

            if not (current * 0.8 < strike < current * 1.5):
                logger.info(f"Skipping {ticker}: unreasonable strike ${strike} for current ${current}")
                continue

            if DIVIDEND_MODULE_LOADED:
                div_check = should_skip_call_for_dividend(
                    ticker, target_exp, current * 0.015, current,
                )
                if div_check["skip"]:
                    logger.info(f"Skipping {ticker} covered call: {div_check['reason']}")
                    continue

            if room_to_strike >= 0.04:
                premium_estimate = _estimate_premium(ticker, strike, current, right="C", dte=35)
                premium_pct = premium_estimate / current if current > 0 else 0

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
            logger.error(f"Error checking {ticker}: {e}")
            continue
    
    return opportunities

def check_csp_opportunities(regime: str = "CHOPPY", nlv: float = 0.0):
    """Find cash-secured put opportunities from long candidates.

    CSPs are income trades on stocks you WANT to own at a lower price.
    Sources candidates exclusively from the long watchlist and long
    candidates in the multimode watchlist — never from short opportunities.
    Skipped during STRONG_DOWNTREND and UNFAVORABLE regimes to avoid assignment losses.
    """
    max_risk_per_contract = nlv * MAX_CSP_RISK_PCT if nlv > 0 else 50_000
    opportunities = []

    if regime in ("STRONG_DOWNTREND", "UNFAVORABLE"):
        logger.info(f"Skipping CSP scan: regime={regime} (high assignment risk)")
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
            logger.info("No candidates found in watchlists for CSP scanning")
            return opportunities
    except Exception as e:
        logger.error(f"Error loading watchlist: {e}")
        return opportunities
    
    import yfinance as yf
    
    logger.info(f"🔍 Scanning {len(tickers)} symbols for CSP opportunities...")
    
    scanned = 0
    earnings_skipped = 0
    for ticker in tickers:  # Scan full universe
        scanned += 1
        if scanned % 50 == 0:
            logger.info(f"  Scanned {scanned}/{len(tickers)}...")
        
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

                if assignment_risk <= max_risk_per_contract:
                    premium_estimate = _estimate_premium(ticker, strike, current, right="P", dte=35)
                    premium_pct = premium_estimate / current if current > 0 else 0
                    
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
        except Exception as exc:
            logger.debug("CSP scan error for symbol: %s", exc)
            continue

    if CALENDAR_MODULES_LOADED and earnings_skipped > 0:
        logger.info(f"  Skipped {earnings_skipped} symbols in earnings blackout")
    
    return opportunities

def _nearest_monthly_expiry(target_dte: int = 35) -> str:
    """Return the 3rd-Friday expiry string (YYYYMMDD) closest to target_dte days out.

    Monthly option expiries land on the 3rd Friday of each month and have the
    widest range of listed strikes, avoiding 'No security definition' errors
    that occur with weekly expiries for far-OTM legs.
    """
    from datetime import timedelta
    today = datetime.now().date()
    target = today + timedelta(days=target_dte)
    candidates = []
    for delta_months in range(-1, 4):
        yr = target.year + (target.month + delta_months - 1) // 12
        mo = (target.month + delta_months - 1) % 12 + 1
        first = datetime(yr, mo, 1).date()
        fridays = [first + timedelta(days=(4 - first.weekday()) % 7 + 7 * i)
                   for i in range(5) if first + timedelta(days=(4 - first.weekday()) % 7 + 7 * i) > today]
        if len(fridays) >= 3:
            candidates.append(fridays[2])
    best = min(candidates, key=lambda d: abs((d - target).days))
    return best.strftime("%Y%m%d")


async def check_iron_condor_opportunities(ib, regime="CHOPPY"):
    """Find iron condor opportunities on SPY/QQQ.

    Iron condors sell premium when volatility is elevated but direction is unclear.
    Sell OTM put + OTM call, buy further OTM wings for protection.
    Eligible in CHOPPY/MIXED, and STRONG_UPTREND when vol is elevated.
    Uses the nearest standard monthly expiry (3rd Friday) to ensure all strikes
    are listed in the IBKR contract database.
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
    today = datetime.now().date()
    existing_condors = 0
    for log_file in LOGS_DIR.glob("options_*.json"):
        try:
            data = json.loads(log_file.read_text())
            if data.get("type") != "iron_condor":
                continue
            exp_str = data.get("expiration", "")
            if not exp_str:
                continue
            exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
            if exp_date >= today:
                existing_condors += 1
        except Exception:
            continue
    if existing_condors >= max_open_condors:
        return opportunities

    import yfinance as yf
    import math
    expiry = _nearest_monthly_expiry(target_dte=35)

    for symbol in ("SPY", "QQQ"):
        try:
            ticker_yf = yf.Ticker(symbol)
            hist = ticker_yf.history(period="1d", interval="1m")
            if hist.empty:
                logger.debug("IC scan: no yfinance data for %s", symbol)
                continue
            price = float(hist["Close"].iloc[-1])
            if not price or price <= 0 or math.isnan(price):
                continue

            # Use 5%/8% OTM for short/wing legs — monthly expiries list these strikes
            put_strike = round_option_strike(price * 0.95)
            call_strike = round_option_strike(price * 1.05)
            put_wing = round_option_strike(price * 0.92)
            call_wing = round_option_strike(price * 1.08)

            max_risk = (put_strike - put_wing) * 100
            estimated_credit = max_risk * 0.30

            if estimated_credit < 50:
                continue

            opportunities.append({
                "ticker": symbol,
                "type": "iron_condor",
                "expiry": expiry,
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
        except Exception as exc:
            logger.debug("IC scan error: %s", exc)
            continue

    return opportunities


def check_protective_put_opportunities(ib, account_value, regime="MIXED"):
    """Check if protective SPY puts are needed for tail risk hedging.

    Buy SPY puts 5-10% OTM when in MIXED or UNFAVORABLE regime.
    Monthly budget from risk.json (default 0.75% of account).
    Uses yfinance for SPY price to avoid sync-in-async IB calls.
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
        import yfinance as yf
        import math
        hist = yf.Ticker("SPY").history(period="1d", interval="1m")
        if hist.empty:
            return opportunities
        price = float(hist["Close"].iloc[-1])
        if not price or price <= 0 or math.isnan(price):
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
    except Exception as exc:
        logger.warning("Protective put check error: %s", exc)

    return opportunities


async def get_nearest_valid_strike(ib, ticker: str, right: str, expiry: str, target_strike: float) -> "float | None":
    """Resolve target_strike to the nearest strike that actually exists in the IB chain.

    Fetches the option chain via reqSecDefOptParams and returns the closest
    listed strike to target_strike. Returns None if the chain cannot be fetched
    or has no strikes near the target.

    This prevents Error 200 'No security definition' failures caused by
    requesting strikes that don't exist (e.g. $29.5 when only $27.5/$30/$32.5 exist).
    """
    try:
        underlying = Stock(ticker, "SMART", "USD")
        qualified = await ib.qualifyContractsAsync(underlying)
        if not qualified:
            return None
        underlying = qualified[0]
        chains = await ib.reqSecDefOptParamsAsync(ticker, "", "STK", underlying.conId)
        await asyncio.sleep(0.5)

        all_strikes: list[float] = []
        for chain in chains:
            if expiry in chain.expirations:
                all_strikes.extend(chain.strikes)

        if not all_strikes:
            return None

        nearby = [s for s in all_strikes if abs(s - target_strike) / max(target_strike, 1) < 0.30]
        if not nearby:
            nearby = all_strikes

        nearest = min(nearby, key=lambda s: abs(s - target_strike))
        if nearest != target_strike:
            logger.info(f"  Strike resolved: {ticker} {right} {expiry}  ${target_strike} → ${nearest} (nearest listed)")
        return float(nearest)
    except Exception as e:
        logger.warning(f"  Warning: could not resolve strike for {ticker}: {e}")
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

    logger.info("\n  Duplicate positions detected — auto-closing extras: %s", list(dupes.keys()))
    results: list[dict] = []

    for (sym, right, expiry, strike), count in dupes.items():
        extras = count - 1
        logger.info(
            "  BUY %sx %s %s $%s%s to close duplicate(s)...",
            extras, sym, expiry, strike, right,
        )
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
                logger.info(
                    "  %s BTC %s: %s  fill=$%.2f",
                    sym,
                    extras,
                    result.status.value if result.status else "unknown",
                    fill,
                )
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
    try:
        delta_strike = select_strike_by_delta(ib, ticker, right, target_exp, target_delta)
        if delta_strike is not None:
            strike = delta_strike
    except RuntimeError:
        pass

    chain_strike = await get_nearest_valid_strike(ib, ticker, right, target_exp, strike)
    if chain_strike is None:
        from ib_insync import Option as IBOption
        direct_opt = IBOption(ticker, target_exp, strike, right, "SMART",
                              currency="USD", multiplier="100")
        direct_q = await ib.qualifyContractsAsync(direct_opt)
        if direct_q:
            chain_strike = strike
            logger.info(
                "  Chain lookup failed but direct qualify OK for %s $%s%s",
                ticker,
                strike,
                right,
            )
        else:
            logger.info(
                "  Could not resolve a valid strike for %s %s %s — skipping",
                ticker,
                right,
                target_exp,
            )
            return None
    strike = chain_strike

    try:
        resolved = await router.contract_cache.resolve_option(
            ticker, target_exp, strike, right,
        )
        if resolved is None:
            logger.info("Could not resolve option contract for %s $%s%s", ticker, strike, right)
            return None

        mid: float = 0.0
        for mdt in (1, 3, 4):
            ib.reqMarketDataType(mdt)
            tickers_result = await ib.reqTickersAsync(resolved.ib_contract)
            if not tickers_result:
                continue
            ticker_data = tickers_result[0]

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
                logger.info(
                    "Using estimated premium $%.2f for %s $%s%s",
                    mid,
                    ticker,
                    strike,
                    right,
                )
            else:
                logger.info(f"No market data for {ticker} ${strike}{right}")
                return None

        premium_pct = mid / opportunity['current']
        if premium_pct < MIN_PREMIUM_PERCENT:
            logger.info(
                "Premium too low: %.2f%% < %.2f%%",
                premium_pct * 100,
                MIN_PREMIUM_PERCENT * 100,
            )
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
            logger.info(
                "Order not filled: %s — %s",
                submit_result.status.value if submit_result.status else "unknown",
                submit_result.error or "",
            )
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
        logger.warning(f"Warning: Could not fetch positions: {e}")
    return positions

def send_telegram(text):
    """Send Telegram notification via the shared notifications module.

    Converts Markdown bold (*text*) to HTML bold (<b>text</b>) since the
    shared module uses HTML parse mode.
    """
    import re
    html_text = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', text)
    try:
        from notifications import send_telegram as _send
        return _send(html_text)
    except ImportError:
        logger.debug("notifications module unavailable — Telegram message dropped")
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
        logger.error("  Could not read pending_trades.json: %s", e)
        return []

    trades = pending.get("trades", [])
    if not trades:
        return []

    logger.info("\n  Processing %s pending trade(s) from alert monitor...", len(trades))
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
            logger.info(
                "     Skipping %s: strike '%s' is an unresolved placeholder",
                sym,
                raw_strike,
            )
            results.append({"symbol": sym, "action": action, "status": "skipped", "reason": f"unresolved strike placeholder: {raw_strike}"})
            continue
        if raw_expiry.startswith("auto_"):
            logger.info(
                "     Skipping %s: expiry '%s' is an unresolved placeholder",
                sym,
                raw_expiry,
            )
            results.append({"symbol": sym, "action": action, "status": "skipped", "reason": f"unresolved expiry placeholder: {raw_expiry}"})
            continue

        try:
            strike = float(raw_strike)
        except (TypeError, ValueError):
            logger.info(
                "     Skipping %s: could not parse strike '%s' as a number",
                sym,
                raw_strike,
            )
            results.append({"symbol": sym, "action": action, "status": "skipped", "reason": f"invalid strike: {raw_strike}"})
            continue

        expiry = raw_expiry
        logger.info("\n  -> %s %sx %s %s %s%s  [%s]", action, qty, sym, expiry, strike, right, note)

        if action == "SELL_TO_OPEN":
            dup_key = (sym.upper(), right.upper(), str(expiry))
            if dup_key in already_executed:
                logger.info(
                    "     Skipping %s %s %s: already sold to open today (duplicate guard)",
                    sym,
                    right,
                    expiry,
                )
                results.append({"symbol": sym, "action": action, "status": "skipped", "reason": "duplicate: already executed today"})
                continue

        if dry_run:
            logger.info("     [DRY RUN — not sending order]")
            results.append({"symbol": sym, "action": action, "status": "dry_run"})
            continue

        try:
            resolved_strike = await get_nearest_valid_strike(ib, sym, right, expiry, strike)
            if resolved_strike is None:
                from ib_insync import Option as IBOption
                direct_opt = IBOption(sym, expiry, strike, right, "SMART",
                                      currency="USD", multiplier="100")
                direct_q = await ib.qualifyContractsAsync(direct_opt)
                if direct_q:
                    resolved_strike = strike
                    logger.info(
                        "     Chain lookup failed but direct qualify OK for %s $%s%s",
                        sym,
                        strike,
                        right,
                    )
                else:
                    logger.info(
                        "     Could not resolve valid strike for %s %s %s — skipping",
                        sym,
                        right,
                        expiry,
                    )
                    results.append({"symbol": sym, "action": action, "status": "skipped", "reason": "no valid strike in chain"})
                    continue
            if resolved_strike != strike:
                logger.info(
                    "     Strike adjusted: $%s -> $%s (nearest listed)",
                    strike,
                    resolved_strike,
                )
                strike = resolved_strike

            if action == "SELL_TO_OPEN":
                side = "SELL"
            elif action == "BUY_TO_CLOSE":
                side = "BUY"
            else:
                logger.info("     Unknown action '%s' — skipping", action)
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
                logger.info("     Placed: %s  fill: $%.2f", status_str, fill_price)
            else:
                logger.error("     Failed: %s", submit_result.error)

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
    logger.info("  Archived to %s", archived_path.name)

    return results


async def execute_iron_condor(
    ib: IB, opp: dict, quantity: int = 1
) -> "dict | None":
    """Execute an iron condor as a single BAG combo order.

    All four legs are submitted atomically so IBKR evaluates the position as
    a defined-risk spread.  This avoids Error 201 (naked option permission)
    and eliminates orphan-leg risk entirely.

    Leg structure (net credit opening):
      SELL OTM call  (call_strike)   +  BUY far-OTM call (call_wing)
      SELL OTM put   (put_strike)    +  BUY far-OTM put  (put_wing)
    """
    from ib_insync import Option as IBOption, Contract, ComboLeg, LimitOrder

    ticker = opp["ticker"]
    expiry = opp.get("expiry") or _nearest_monthly_expiry(opp.get("dte", 35))

    leg_specs = [
        (opp["call_strike"], "C", "SELL"),
        (opp["call_wing"],   "C", "BUY"),
        (opp["put_strike"],  "P", "SELL"),
        (opp["put_wing"],    "P", "BUY"),
    ]

    # ── Step 1: Qualify all four option contracts & get mid prices ────────
    # Try IB market data first; fall back to yfinance options chain.
    import yfinance as yf
    import math

    yf_chain_cache: dict[str, object] = {}

    def _yf_mid(sym: str, expiry_str: str, strike_val: float, right_val: str) -> float:
        """Fetch option mid-price from yfinance options chain."""
        yf_expiry = f"{expiry_str[:4]}-{expiry_str[4:6]}-{expiry_str[6:]}"
        cache_key = f"{sym}_{yf_expiry}"
        if cache_key not in yf_chain_cache:
            try:
                yf_chain_cache[cache_key] = yf.Ticker(sym).option_chain(yf_expiry)
            except Exception:
                return 0.0
        chain = yf_chain_cache[cache_key]
        df = chain.calls if right_val == "C" else chain.puts
        row = df.loc[df["strike"] == strike_val]
        if row.empty:
            nearest_idx = (df["strike"] - strike_val).abs().idxmin()
            row = df.loc[[nearest_idx]]
        bid_v = float(row["bid"].iloc[0])
        ask_v = float(row["ask"].iloc[0])
        if bid_v > 0 and ask_v > 0:
            return round((bid_v + ask_v) / 2, 2)
        last_v = float(row["lastPrice"].iloc[0])
        if last_v > 0 and not math.isnan(last_v):
            return round(last_v, 2)
        return 0.0

    qualified_legs: list[tuple] = []  # (qualified_contract, action, mid_price)
    for strike, right, action in leg_specs:
        opt = IBOption(ticker, expiry, strike, right, "SMART",
                       currency="USD", multiplier="100")
        qualified = await ib.qualifyContractsAsync(opt)
        if not qualified:
            logger.warning("IC leg: could not qualify %s $%s%s %s", ticker, strike, right, expiry)
            return None

        bid, ask, mid = 0.0, 0.0, 0.0
        for mdt in (1, 3, 4):
            ib.reqMarketDataType(mdt)
            tickers_data = await ib.reqTickersAsync(qualified[0])
            if tickers_data:
                td = tickers_data[0]
                bid = td.bid if td.bid and td.bid > 0 else 0.0
                ask = td.ask if td.ask and td.ask > 0 else 0.0
            if bid > 0 and ask > 0:
                mid = round((bid + ask) / 2, 2)
                break
            if ask > 0:
                mid = round(ask * 0.95, 2)
                break

        if mid <= 0:
            mid = _yf_mid(ticker, expiry, strike, right)
            if mid > 0:
                logger.info("IC leg %s $%s%s: using yfinance mid $%.2f (IB data unavailable)", ticker, strike, right, mid)

        if mid <= 0:
            logger.warning("IC leg: no market data for %s $%s%s — aborting condor", ticker, strike, right)
            return None

        mid = max(mid, 0.01)
        qualified_legs.append((qualified[0], action, mid))

    # ── Step 2: Compute net credit (per-share, not per-contract) ──────────
    # SELL legs contribute positive credit, BUY legs are a debit.
    net_credit_per_share = 0.0
    for _con, action, mid in qualified_legs:
        if action == "SELL":
            net_credit_per_share += mid
        else:
            net_credit_per_share -= mid
    net_credit_per_share = round(net_credit_per_share, 2)

    if net_credit_per_share <= 0:
        logger.warning("IC %s: net credit $%.2f ≤ 0 — skipping (would be a debit)", ticker, net_credit_per_share)
        return None

    # ── Step 3: Build the BAG combo contract ──────────────────────────────
    combo_legs: list[ComboLeg] = []
    for con, action, _mid in qualified_legs:
        leg = ComboLeg()
        leg.conId = con.conId
        leg.ratio = 1
        leg.action = action
        leg.exchange = "SMART"
        combo_legs.append(leg)

    bag = Contract()
    bag.symbol = ticker
    bag.secType = "BAG"
    bag.currency = "USD"
    bag.exchange = "SMART"
    bag.comboLegs = combo_legs

    # ── Step 4: Submit a single limit order for the net credit ────────────
    # IBKR BAG convention: leg actions define what happens when you BUY the
    # combo.  Our legs are SELL/BUY/SELL/BUY → opening a credit IC.
    # Use action=BUY with a negative limit price to indicate credit received.
    combo_limit = round(-net_credit_per_share, 2)

    order = LimitOrder(
        action="BUY",
        totalQuantity=quantity,
        lmtPrice=combo_limit,
        tif="DAY",
        transmit=True,
    )

    logger.info(
        "IC %s: submitting BAG combo — put $%s/$%s, call $%s/$%s, "
        "exp %s, net credit $%.2f × %d (combo limit %.2f)",
        ticker, opp["put_wing"], opp["put_strike"],
        opp["call_strike"], opp["call_wing"],
        expiry, net_credit_per_share, quantity, combo_limit,
    )

    trade = ib.placeOrder(bag, order)

    # ── Step 5: Wait for fill (up to 60s for a combo) ─────────────────────
    filled = False
    for _ in range(60):
        await asyncio.sleep(1)
        status = getattr(trade.orderStatus, "status", "")
        if status == "Filled":
            filled = True
            break
        if status in ("Cancelled", "ApiCancelled", "Inactive"):
            err_msg = ""
            if trade.log:
                err_msg = trade.log[-1].message
            logger.error("IC %s combo rejected: %s — %s", ticker, status, err_msg)
            return None

    if not filled:
        logger.warning("IC %s combo not filled after 60s — cancelling", ticker)
        ib.cancelOrder(order)
        await asyncio.sleep(2)
        return None

    raw_fill = float(trade.orderStatus.avgFillPrice or 0)
    credit_per_share = abs(raw_fill)
    net_credit_total = round(credit_per_share * 100 * quantity, 2)

    result = {
        "ticker": ticker,
        "type": "iron_condor",
        "right": "IC",
        "call_strike": opp["call_strike"],
        "call_wing": opp["call_wing"],
        "put_strike": opp["put_strike"],
        "put_wing": opp["put_wing"],
        "expiration": expiry,
        "quantity": quantity,
        "net_credit": net_credit_total,
        "fill_price_per_share": credit_per_share,
        "max_risk": opp.get("max_risk", 0),
        "executed_at": datetime.now().isoformat(),
        "status": "filled",
    }
    logger.info(
        "Iron condor %s filled: $%.2f/share net credit ($%.2f total, max risk $%.0f)",
        ticker, credit_per_share, net_credit_total, opp.get("max_risk", 0),
    )
    return result


async def async_main() -> None:
    _mode = os.getenv("TRADING_MODE", "paper")
    if _mode == "live":
        logger.info("LIVE TRADING MODE — real money at risk")
    logger.info("Auto Options Executor Starting [%s]...", _mode.upper())

    try:
        from agents.risk_monitor import is_kill_switch_active
        if is_kill_switch_active():
            logger.info("Kill switch active — halting options executor")
            return
    except ImportError:
        pass

    try:
        from drawdown_circuit_breaker import is_entries_halted, get_position_scale
        if is_entries_halted():
            logger.info("Drawdown breaker tier 2+ — new entries halted")
            return
        _breaker_scale = get_position_scale()
        if _breaker_scale < 1.0:
            logger.info("Drawdown breaker active — sizing reduced to %.0f%%", _breaker_scale * 100)
    except ImportError:
        _breaker_scale = 1.0

    if CALENDAR_MODULES_LOADED:
        today = datetime.now().date().strftime("%Y-%m-%d")
        if is_economic_blackout(today):
            reason = get_blackout_reason(today)
            logger.info("ECONOMIC BLACKOUT TODAY: %s", reason)
            logger.info("Trading halted. Exiting.")
            return

    today_count = count_options_today()
    month_count = count_options_this_month()

    logger.info("Options today: %s/%s", today_count, MAX_OPTIONS_PER_DAY)
    logger.info("Options this month: %s/%s", month_count, MAX_OPTIONS_PER_MONTH)

    if today_count >= MAX_OPTIONS_PER_DAY:
        logger.info("Daily limit reached")
        return

    if month_count >= MAX_OPTIONS_PER_MONTH:
        logger.info("Monthly limit reached")
        return

    ib = IB()
    try:
        await ib.connectAsync(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        logger.info("Connected to IB Gateway")
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
        logger.info("OrderRouter started (reconciliation complete)")

        current_positions = get_current_positions(ib)
        account_value = 0.0
        try:
            for av in ib.accountValues():
                if av.tag == "NetLiquidation" and av.currency == "USD":
                    account_value = float(av.value)
                    break
        except Exception as e:
            logger.warning(f"Warning: Could not fetch account value from IB: {e}")
        if account_value <= 0:
            try:
                for av in ib.accountValues():
                    if av.tag == "NetLiquidation" and av.currency == "USD":
                        account_value = float(av.value)
                        break
            except Exception:
                pass
        if account_value <= 0 and _mode == "live":
            logger.error("Could not read live NLV — halting to prevent wrong sizing")
            return
        if account_value <= 0:
            account_value = 100_000.0
            logger.warning(f"Warning: Using paper fallback NLV ${account_value:,.0f}")
        account_value = _apply_alloc(account_value)
        logger.info("Account value (allocation-adjusted): $%s", format(account_value, ",.0f"))

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
            logger.info(
                "  Pending trades processed: %s/%s executed",
                executed_count,
                len(pending_results),
            )

        regime = "CHOPPY"
        macro_multiplier = 1.0
        if STRATEGY_MODULES_LOADED:
            try:
                from regime_detector import detect_market_regime, get_macro_size_multiplier
                regime = detect_market_regime()
                macro_multiplier = get_macro_size_multiplier()
                logger.info(
                    "Regime: %s | Macro size multiplier: %.2f×",
                    regime,
                    macro_multiplier,
                )
            except Exception as e:
                logger.info("Regime detection failed (using CHOPPY, multiplier 1.0): %s", e)

        cc_opps = check_covered_call_opportunities(ib, regime=regime)
        csp_opps = check_csp_opportunities(regime=regime, nlv=account_value)
        ic_opps = await check_iron_condor_opportunities(ib, regime=regime)
        pp_opps = check_protective_put_opportunities(ib, account_value, regime=regime)

        logger.info("\nFound:")
        logger.info("  %s covered call opportunities", len(cc_opps))
        logger.info("  %s cash-secured put opportunities", len(csp_opps))
        logger.info("  %s iron condor opportunities (SPY/QQQ)", len(ic_opps))
        logger.info("  %s protective put opportunities (SPY)", len(pp_opps))

        earnings_safe_opps: list[dict] = []
        if CALENDAR_MODULES_LOADED:
            logger.info("\n Checking earnings blackout...")
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
                        logger.info(
                            "  Skipping %s: earnings in %s day(s) (%s)",
                            opp["ticker"],
                            days_until,
                            earnings_str,
                        )
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
            logger.info("\n Checking sector concentration...")
            for opp in earnings_safe_opps:
                sector_check = can_add_position(opp['ticker'], current_positions)
                if sector_check['allowed']:
                    valid_opps.append(opp)
                else:
                    logger.info("  %s: %s", opp["ticker"], sector_check["reason"])
        else:
            valid_opps = earnings_safe_opps

        logger.info("Sector-compliant opportunities: %s", len(valid_opps))

        already_executed = get_already_executed_today()
        if already_executed:
            logger.info("\n Already executed today: %s", sorted(already_executed))
        deduped_opps: list[dict] = []
        for opp in valid_opps:
            right = 'C' if opp['type'] == 'covered_call' else 'P'
            from datetime import timedelta
            exp = (datetime.now() + timedelta(days=opp.get('dte', 35))).strftime('%Y%m%d')
            key = (opp['ticker'].upper(), right, exp)
            if key in already_executed:
                logger.info("  Skipping %s %s (already sold to open today)", opp["ticker"], right)
            else:
                deduped_opps.append(opp)
        valid_opps = deduped_opps

        executed: list[dict] = []
        remaining = MAX_OPTIONS_PER_DAY - today_count

        max_single_option_alloc = risk_cfg.get("options", {}).get(
            "max_single_option_pct_of_equity",
            get_max_single_option_pct_of_equity(TRADING_DIR),
        )

        # Fetch VIX once outside the loop — reused for all contracts this run
        if STRATEGY_MODULES_LOADED:
            _vix_data = get_vix_level()
            _run_vix: float = _vix_data['vix'] if _vix_data.get('vix') else 20.0
        else:
            _run_vix = 20.0

        for opp in valid_opps[:remaining]:
            if STRATEGY_MODULES_LOADED:
                sizing = calculate_composite_position_size(
                    symbol=opp['ticker'],
                    account_value=account_value,
                    vix=_run_vix,
                    days_until_earnings=opp.get('_days_until_earnings'),
                    peak_value=account_value
                )
                composite = sizing['composite_multiplier']
                # VIX premium scaling: when VIX is elevated, implied vol is rich
                # and we want MORE premium contracts (inverse of equity sizing).
                # Only boost when IV rank is also elevated (confirming rich premium).
                iv_r = fetch_iv_rank(opp['ticker'])
                # Covered calls use a lower IV floor (0.25); CSPs/others use MIN_IV_RANK_FOR_PREMIUM
                _cc_iv_floor = 0.25 if opp.get('type') == 'covered_call' else MIN_IV_RANK_FOR_PREMIUM
                iv_ok = iv_r is None or iv_r >= _cc_iv_floor
                premium_vix_mult = get_options_vix_multiplier(_run_vix) if iv_ok else 1.0
            else:
                composite = 1.0
                premium_vix_mult = 1.0

            # macro_multiplier: FRED-based regime band (1.0 RISK_ON → 0.25 DEFENSIVE)
            max_notional = (
                account_value
                * max_single_option_alloc
                * composite
                * _breaker_scale
                * macro_multiplier
                * premium_vix_mult
            )
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
                logger.info(f"Skipping {opp['ticker']}: sizing too small")
                continue

            opp['quantity'] = adjusted_qty
            logger.info(
                "%s: %s contracts ($%s notional, composite=%.0f%%)",
                opp["ticker"],
                opp["quantity"],
                format(assignment_cost * adjusted_qty, ",.0f"),
                composite * 100,
            )

            logger.info("\nExecuting: %s $%s %s", opp["ticker"], opp["strike"], opp["type"])
            result = await execute_option_trade(ib, router, opp)

            if result:
                executed.append(result)
                logger.info(
                    "Filled: $%.2f, Premium: $%.2f",
                    result["fill_price"],
                    result["premium_collected"],
                )

                msg = "*AUTO-EXECUTED Options*\n\n"
                msg += f"*{result['ticker']}* ${result['strike']} {result['right']}\n"
                msg += f"Type: {result['type'].replace('_', ' ').title()}\n"
                msg += f"Premium: ${result['premium_collected']:.2f}\n"
                msg += f"Expiration: {result['expiration']}\n"
                msg += "\nTrade logged and confirmed"

                send_telegram(msg)
            else:
                logger.error("Failed to execute")

        if not executed:
            logger.info("\nNo trades executed (no qualifying opportunities)")
        else:
            logger.info("\nExecuted %s options trades", len(executed))

        # ── Iron condor execution ──────────────────────────────────────────────
        # ICs are executed after single-leg trades to avoid using up the daily
        # limit before the primary CC/CSP trades have run.
        if ic_opps:
            ic_remaining = max(0, remaining - len(executed))
            ic_vix_mult = get_options_vix_multiplier(_run_vix) if STRATEGY_MODULES_LOADED else 1.0
            # VIX-responsive IC qty: 1 at normal vol, up to 2 at elevated VIX
            ic_qty = min(2, max(1, round(ic_vix_mult)))

            logger.info(
                "\nIron condors: %s identified, VIX=%.1f → %sx contracts",
                len(ic_opps),
                _run_vix,
                ic_qty,
            )

            for ic_opp in ic_opps[:min(2, ic_remaining)]:
                logger.info(
                    "  Executing IC: %s put $%s / call $%s",
                    ic_opp["ticker"],
                    ic_opp["put_strike"],
                    ic_opp["call_strike"],
                )
                ic_result = await execute_iron_condor(ib, ic_opp, quantity=ic_qty)
                if ic_result:
                    executed.append(ic_result)
                    ic_log_path = LOGS_DIR / f"options_{datetime.now().strftime('%Y%m%d_%H%M%S')}_ic.json"
                    ic_log_path.write_text(json.dumps(ic_result, indent=2))
                    msg = (
                        "*AUTO-EXECUTED Iron Condor*\n\n"
                        f"*{ic_result['ticker']}* {ic_result['expiration']}\n"
                        f"Put spread: ${ic_result['put_wing']} / ${ic_result['put_strike']}\n"
                        f"Call spread: ${ic_result['call_strike']} / ${ic_result['call_wing']}\n"
                        f"Net credit: ${ic_result['net_credit']:.2f}\n"
                        f"Max risk: ${ic_result['max_risk']:.0f}\n"
                        f"Qty: {ic_qty} contract(s)"
                    )
                    try:
                        send_telegram(msg)
                    except Exception:
                        pass
                    logger.info("  Filled: net credit $%.2f", ic_result["net_credit"])
                else:
                    logger.error("  IC execution failed for %s", ic_opp["ticker"])

        if pp_opps:
            for o in pp_opps[:2]:
                logger.info(
                    "  Protective put: SPY $%s (~$%.0f cost)",
                    o["strike"],
                    o.get("estimated_cost", 0),
                )
            logger.info("  (Protective puts require manual approval — not auto-executed)")

        if STRATEGY_MODULES_LOADED:
            logger.info("\nGap Risk Check:")
            gap_checklist = get_eod_checklist(current_positions)
            logger.info("  Time to close: %.1f minutes", gap_checklist["time_remaining_min"])
            if gap_checklist['gap_risk_positions']:
                logger.info("  %s position(s) with gap risk:", len(gap_checklist["gap_risk_positions"]))
                for pos in gap_checklist['gap_risk_positions']:
                    logger.info("    - %s %s", pos["symbol"], pos["type"])
                if gap_checklist['should_act']:
                    logger.info("\n%s", gap_checklist["summary"])
            else:
                logger.info("  No gap risk positions")

    finally:
        await router.shutdown()
        ib.disconnect()
        logger.info("\nDisconnected from IB")


def check_tail_hedge_needed(ib, nlv: float) -> dict:
    """Dalio structural tail hedge: check if a SPY put debit spread should be placed.

    Executes a small SPY put debit spread (~8% OTM long / ~15% OTM short) when:
      1. enabled in risk.json → tail_hedge
      2. VIX < min_vix_to_skip (cheap to buy insurance; don't buy when VIX is already 30+)
      3. No existing SPY put hedge placed within min_days_between_hedges days
      4. Monthly premium budget not exceeded

    Returns a dict with keys: 'action' ('execute'|'skip'), 'reason', optional order info.
    """
    try:
        _risk = json.loads((TRADING_DIR / 'risk.json').read_text())
        cfg = _risk.get('tail_hedge', {})
    except Exception:
        cfg = {}

    if not cfg.get('enabled', False):
        return {'action': 'skip', 'reason': 'tail_hedge disabled in risk.json'}

    max_premium = nlv * cfg.get('max_monthly_premium_pct', 0.015)
    instrument = cfg.get('hedge_instrument', 'SPY')
    long_otm = cfg.get('long_put_otm_pct', 0.08)
    short_otm = cfg.get('short_put_otm_pct', 0.15)
    target_dte = cfg.get('target_dte', 45)
    vix_skip = cfg.get('min_vix_to_skip', 30)
    min_days = cfg.get('min_days_between_hedges', 28)
    max_contracts = cfg.get('max_contracts', 2)

    # Check VIX — don't buy puts when vol is already elevated (expensive and lagging)
    try:
        import yfinance as yf
        vix_data = yf.download('^VIX', period='2d', progress=False)
        vix_level = float(vix_data['Close'].iloc[-1])
        if vix_level >= vix_skip:
            return {'action': 'skip', 'reason': f'VIX={vix_level:.1f} >= {vix_skip} — too expensive to hedge now'}
    except Exception:
        vix_level = 20.0  # assume normal if yfinance fails

    # Check when we last placed a hedge
    hedge_log = LOGS_DIR / 'tail_hedge_log.json'
    if hedge_log.exists():
        try:
            last = json.loads(hedge_log.read_text())
            last_dt = datetime.fromisoformat(last.get('placed_at', '2000-01-01'))
            days_since = (datetime.now() - last_dt).days
            if days_since < min_days:
                return {'action': 'skip', 'reason': f'Hedge placed {days_since}d ago (min={min_days}d)'}
        except Exception:
            pass

    # Check for existing SPY put position
    if ib and ib.isConnected():
        try:
            from ib_insync import Option as _Opt
            positions = ib.positions()
            existing_spy_puts = [
                p for p in positions
                if p.contract.symbol == instrument
                and p.contract.secType == 'OPT'
                and p.contract.right == 'P'
                and p.position < 0  # only check short puts; long puts = we have protection
            ]
            long_spy_puts = [p for p in positions
                             if p.contract.symbol == instrument
                             and p.contract.secType == 'OPT'
                             and p.contract.right == 'P'
                             and p.position > 0]
            if long_spy_puts:
                return {'action': 'skip', 'reason': f'Already hold {len(long_spy_puts)} SPY put(s)'}
        except Exception:
            pass

    # Get SPY price and compute strikes
    try:
        import yfinance as yf
        spy_price = float(yf.download(instrument, period='2d', progress=False)['Close'].iloc[-1])
    except Exception:
        return {'action': 'skip', 'reason': 'Could not fetch SPY price'}

    long_strike = round(spy_price * (1 - long_otm) / 5) * 5   # 8% OTM, rounded to $5
    short_strike = round(spy_price * (1 - short_otm) / 5) * 5  # 15% OTM, rounded to $5

    # Find appropriate expiry
    try:
        import yfinance as yf
        from datetime import timedelta
        spy_ticker = yf.Ticker(instrument)
        expirations = spy_ticker.options
        target_date = datetime.now() + timedelta(days=target_dte)
        best_exp = min(expirations, key=lambda e: abs((datetime.strptime(e, '%Y-%m-%d') - target_date).days))
    except Exception:
        return {'action': 'skip', 'reason': 'Could not find SPY expiry'}

    # Estimate spread cost via yfinance
    try:
        chain = spy_ticker.option_chain(best_exp)
        puts = chain.puts
        long_row = puts[puts['strike'] == long_strike]
        short_row = puts[puts['strike'] == short_strike]
        if long_row.empty or short_row.empty:
            return {'action': 'skip', 'reason': f'No chain data for strikes {short_strike}/{long_strike}'}
        long_mid = float((long_row.iloc[0]['bid'] + long_row.iloc[0]['ask']) / 2)
        short_mid = float((short_row.iloc[0]['bid'] + short_row.iloc[0]['ask']) / 2)
        spread_cost = (long_mid - short_mid) * 100  # per contract
    except Exception:
        return {'action': 'skip', 'reason': 'Could not price spread'}

    if spread_cost <= 0:
        return {'action': 'skip', 'reason': f'Spread cost non-positive (${spread_cost:.2f})'}

    # Size: how many contracts within the monthly premium budget?
    contracts = min(max_contracts, max(1, int(max_premium / spread_cost)))
    total_cost = contracts * spread_cost

    result = {
        'action': 'execute',
        'instrument': instrument,
        'expiry': best_exp,
        'long_strike': long_strike,
        'short_strike': short_strike,
        'contracts': contracts,
        'spread_cost_per_contract': round(spread_cost, 2),
        'total_cost': round(total_cost, 2),
        'vix': round(vix_level, 1),
        'spy_price': round(spy_price, 2),
        'max_gain': round((long_strike - short_strike) * 100 * contracts - total_cost, 0),
    }
    logger.info(
        'Tail hedge recommended: buy %dx SPY %s $%s/$%s put spread @ $%.2f/contract '
        '(total $%.0f, VIX=%.1f, max_gain=$%.0f)',
        contracts, best_exp, long_strike, short_strike,
        spread_cost, total_cost, vix_level, result['max_gain'],
    )
    return result


def main() -> None:
    """Sync wrapper preserving the existing scheduler/subprocess interface."""
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
