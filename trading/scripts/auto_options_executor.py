#!/usr/bin/env python3
"""
Automated Options Executor
Fully automated covered calls and cash-secured puts with strict safety rules
Runs on schedule, executes qualifying opportunities automatically

UPDATED: Includes economic calendar + earnings blackout checks
"""
import os, json, sys, time
from pathlib import Path
from datetime import datetime
from ib_insync import IB, Stock, Option, MarketOrder, util

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
from iv_rank import MIN_IV_RANK_FOR_PREMIUM, fetch_iv_rank
from live_allocation import get_effective_equity as _apply_alloc
from risk_config import get_max_options_per_day, get_max_options_per_month

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

def round_option_strike(strike):
    """Round strike to valid option intervals"""
    if strike > 200:
        interval = 5.0
    elif strike > 100:
        interval = 2.5
    else:
        interval = 1.0
    return round(strike / interval) * interval

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

def check_covered_call_opportunities(ib):
    """Find covered call opportunities from current positions.
    
    Uses yfinance for price data (avoids IB Error 10197 market data conflicts).
    """
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
            
            iv_r = fetch_iv_rank(ticker, ib=ib)
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
        iv_r = fetch_iv_rank("SPY", ib=ib)
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


def get_option_contract(ib, ticker, strike, right, dte):
    """Get option contract for given parameters"""
    from datetime import date, timedelta
    from calendar import monthrange
    
    # Calculate next monthly expiration (3rd Friday)
    today = date.today()
    
    # Start with next month
    if today.month == 12:
        next_month = 1
        next_year = today.year + 1
    else:
        next_month = today.month + 1
        next_year = today.year
    
    # Find 3rd Friday of next month
    # Start with the 15th (guaranteed to be in 3rd week)
    third_week_start = date(next_year, next_month, 15)
    
    # Find the Friday in that week
    days_until_friday = (4 - third_week_start.weekday()) % 7
    third_friday = third_week_start + timedelta(days=days_until_friday)
    
    expiration = third_friday.strftime('%Y%m%d')
    
    option = Option(ticker, expiration, strike, right, 'SMART')
    
    try:
        ib.qualifyContracts(option)
        return option
    except Exception as e:
        print(f"Failed to qualify option contract: {e}")
        return None

def execute_option_trade(ib, opportunity):
    """Execute option trade with IB, preferring delta-targeted strikes."""
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
    
    try:
        option = get_option_contract(ib, ticker, strike, right, dte)
        
        if not option:
            print(f"Could not get valid option contract for {ticker} ${strike}{right}")
            return None
        
        for mdt in (1, 3, 4):
            ib.reqMarketDataType(mdt)
            [ticker_data] = ib.reqTickers(option)
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
        
        order = MarketOrder('SELL', quantity)
        trade = ib.placeOrder(option, order)
        
        # Wait for fill
        ib.sleep(2)
        
        if trade.orderStatus.status in ('Filled', 'PreSubmitted'):
            fill_price = trade.orderStatus.avgFillPrice
            
            result = {
                'ticker': ticker,
                'type': opportunity['type'],
                'strike': strike,
                'right': right,
                'expiration': option.lastTradeDateOrContractMonth,
                'quantity': quantity,
                'fill_price': fill_price,
                'premium_collected': fill_price * quantity * 100,
                'executed_at': datetime.now().isoformat(),
                'status': 'filled'
            }
            
            # Log trade
            log_file = LOGS_DIR / f"options_{int(time.time())}.json"
            log_file.write_text(json.dumps(result, indent=2))
            
            return result
        else:
            print(f"Order not filled: {trade.orderStatus.status}")
            return None
            
    except Exception as e:
        print(f"Error executing {ticker} ${strike}{right}: {e}")
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

def process_pending_trades(ib: IB, dry_run: bool = False) -> list[dict]:
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
        print(f"⚠️ Could not read pending_trades.json: {e}")
        return []

    trades = pending.get("trades", [])
    if not trades:
        return []

    print(f"\n📋 Processing {len(trades)} pending trade(s) from alert monitor...")
    results = []

    for trade in trades:
        sym = trade.get("symbol", "")
        action = trade.get("action", "")
        right = trade.get("right", "C")
        strike = float(trade.get("strike", 0))
        expiry = str(trade.get("expiry", ""))
        qty = int(trade.get("quantity", 1))
        note = trade.get("note", "")

        print(f"\n  → {action} {qty}x {sym} {expiry} {strike}{right}  [{note}]")

        if dry_run:
            print(f"     [DRY RUN — not sending order]")
            results.append({"symbol": sym, "action": action, "status": "dry_run"})
            continue

        try:
            contract = Option(sym, expiry, strike, right, "SMART")
            ib.qualifyContracts(contract)
            ib.sleep(0.5)

            if action == "SELL_TO_OPEN":
                order = MarketOrder("SELL", qty)
            elif action == "BUY_TO_CLOSE":
                order = MarketOrder("BUY", qty)
            else:
                print(f"     ⚠️ Unknown action '{action}' — skipping")
                continue

            trade_obj = ib.placeOrder(contract, order)
            ib.sleep(2)
            fill_price = trade_obj.orderStatus.avgFillPrice
            status = trade_obj.orderStatus.status

            print(f"     ✅ Placed: {status}  fill: ${fill_price:.2f}")
            results.append({
                "symbol": sym, "action": action, "qty": qty,
                "strike": strike, "expiry": expiry, "right": right,
                "status": status, "fill_price": fill_price,
                "executed_at": datetime.now().isoformat(),
            })
        except Exception as e:
            print(f"     ❌ Failed: {e}")
            results.append({"symbol": sym, "action": action, "status": "error", "error": str(e)})

    # Archive processed trades so they don't re-run
    archived_path = LOGS_DIR / f"pending_trades_executed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    pending["executed_results"] = results
    pending["processed_at"] = datetime.now().isoformat()
    archived_path.write_text(json.dumps(pending, indent=2))
    PENDING_TRADES_PATH.unlink(missing_ok=True)
    print(f"  📁 Archived to {archived_path.name}")

    return results


def main():
    _mode = os.getenv("TRADING_MODE", "paper")
    if _mode == "live":
        print("🔴 LIVE TRADING MODE — real money at risk")
    print(f"🤖 Auto Options Executor Starting [{_mode.upper()}]...")

    try:
        from agents.risk_monitor import is_kill_switch_active
        if is_kill_switch_active():
            print("⛔ Kill switch active — halting options executor")
            return
    except ImportError:
        pass

    try:
        from drawdown_circuit_breaker import is_entries_halted, get_position_scale
        if is_entries_halted():
            print("⛔ Drawdown breaker tier 2+ — new entries halted")
            return
        _breaker_scale = get_position_scale()
        if _breaker_scale < 1.0:
            print(f"⚠️ Drawdown breaker active — sizing reduced to {_breaker_scale:.0%}")
    except ImportError:
        _breaker_scale = 1.0

    # Check economic calendar first (CRITICAL)
    if CALENDAR_MODULES_LOADED:
        today = datetime.now().date().strftime("%Y-%m-%d")
        if is_economic_blackout(today):
            reason = get_blackout_reason(today)
            print(f"🚫 ECONOMIC BLACKOUT TODAY: {reason}")
            print("⛔ Trading halted. Exiting.")
            return
    
    # Check limits
    today_count = count_options_today()
    month_count = count_options_this_month()
    
    print(f"Options today: {today_count}/{MAX_OPTIONS_PER_DAY}")
    print(f"Options this month: {month_count}/{MAX_OPTIONS_PER_MONTH}")
    
    if today_count >= MAX_OPTIONS_PER_DAY:
        print("⚠️ Daily limit reached")
        return
    
    if month_count >= MAX_OPTIONS_PER_MONTH:
        print("⚠️ Monthly limit reached")
        return
    
    # Connect to IB
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        print(f"✅ Connected to IB Gateway")
    except Exception as e:
        print(f"❌ Failed to connect to IB: {e}")
        return
    
    try:
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
            print("❌ ERROR: Could not read live NLV — halting to prevent wrong sizing")
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

        # Process any pending trades queued by the alert monitor (highest priority)
        pending_results = process_pending_trades(ib, dry_run=(_mode != "live"))
        if pending_results:
            executed_count = sum(1 for r in pending_results if r.get("status") not in ("error", "dry_run"))
            print(f"  Pending trades processed: {executed_count}/{len(pending_results)} executed")

        # Regime for Iron Condors (CHOPPY/MIXED) and Protective Puts (MIXED/UNFAVORABLE/STRONG_DOWNTREND)
        regime = "CHOPPY"
        if STRATEGY_MODULES_LOADED:
            try:
                from regime_detector import detect_market_regime
                regime = detect_market_regime(ib=ib)
                print(f"Regime: {regime}")
            except Exception as e:
                print(f"Regime detection failed (using CHOPPY): {e}")

        # Find opportunities (all four strategies)
        cc_opps = check_covered_call_opportunities(ib)
        csp_opps = check_csp_opportunities(regime=regime)
        ic_opps = check_iron_condor_opportunities(ib, regime=regime)
        pp_opps = check_protective_put_opportunities(ib, account_value, regime=regime)

        print(f"\nFound:")
        print(f"  {len(cc_opps)} covered call opportunities")
        print(f"  {len(csp_opps)} cash-secured put opportunities")
        print(f"  {len(ic_opps)} iron condor opportunities (SPY/QQQ)")
        print(f"  {len(pp_opps)} protective put opportunities (SPY)")

        # Filter by earnings blackout (block entries within 7 days of earnings; CC/CSP only)
        earnings_safe_opps = []
        if CALENDAR_MODULES_LOADED:
            print(f"\n Checking earnings blackout...")
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

        # Filter by sector concentration
        valid_opps = []
        if STRATEGY_MODULES_LOADED:
            print(f"\n Checking sector concentration...")
            for opp in earnings_safe_opps:
                sector_check = can_add_position(opp['ticker'], current_positions)
                if sector_check['allowed']:
                    valid_opps.append(opp)
                else:
                    print(f"  {opp['ticker']}: {sector_check['reason']}")
        else:
            valid_opps = earnings_safe_opps

        print(f"Sector-compliant opportunities: {len(valid_opps)}")
        
        executed = []
        
        # Execute up to daily limit
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

            max_notional = account_value * max_single_option_alloc * composite * _breaker_scale
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
            
            print(f"\n🔄 Executing: {opp['ticker']} ${opp['strike']} {opp['type']}")
            result = execute_option_trade(ib, opp)
            
            if result:
                executed.append(result)
                print(f"✅ Filled: ${result['fill_price']:.2f}, Premium: ${result['premium_collected']:.2f}")
                
                # Send Telegram notification
                msg = f"🤖 *AUTO-EXECUTED Options*\n\n"
                msg += f"*{result['ticker']}* ${result['strike']} {result['right']}\n"
                msg += f"Type: {result['type'].replace('_', ' ').title()}\n"
                msg += f"Premium: ${result['premium_collected']:.2f}\n"
                msg += f"Expiration: {result['expiration']}\n"
                msg += f"\n✅ Trade logged and confirmed"
                
                send_telegram(msg)
            else:
                print(f"❌ Failed to execute")
        
        if not executed:
            print("\n✅ No trades executed (no qualifying opportunities)")
        else:
            print(f"\n✅ Executed {len(executed)} options trades")

        # Combined strategy: report IC/PP (regime-gated; auto-execution for IC/PP can be added later)
        if ic_opps or pp_opps:
            print("\n📋 Combined strategy (regime-gated):")
            if ic_opps:
                for o in ic_opps[:3]:
                    print(f"  Iron condor: {o['ticker']} put ${o['put_strike']} / call ${o['call_strike']} (~${o['estimated_credit']:.0f} credit)")
            if pp_opps:
                for o in pp_opps[:2]:
                    print(f"  Protective put: SPY ${o['strike']} (~${o['estimated_cost']:.0f} cost)")
            print("  (IC/PP are not auto-executed in this run; execute manually or enable in code)")

        # Check gap risk at end of day
        if STRATEGY_MODULES_LOADED:
            print("\n📋 Gap Risk Check:")
            gap_checklist = get_eod_checklist(current_positions)
            print(f"  Time to close: {gap_checklist['time_remaining_min']:.1f} minutes")
            if gap_checklist['gap_risk_positions']:
                print(f"  ⚠️ {len(gap_checklist['gap_risk_positions'])} position(s) with gap risk:")
                for pos in gap_checklist['gap_risk_positions']:
                    print(f"    - {pos['symbol']} {pos['type']}")
                if gap_checklist['should_act']:
                    print(f"\n🚨 {gap_checklist['summary']}")
            else:
                print(f"  ✅ No gap risk positions")
            
    finally:
        ib.disconnect()
        print("\n🔌 Disconnected from IB")

if __name__ == '__main__':
    main()
