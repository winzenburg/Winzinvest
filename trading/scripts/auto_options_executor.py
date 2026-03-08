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

# Paths
TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'
WATCHLIST_MULTIMODE_PATH = TRADING_DIR / 'watchlist_multimode.json'
WATCHLIST_LONGS_PATH = TRADING_DIR / 'watchlist_longs.json'
WATCHLIST_LEGACY_PATH = TRADING_DIR / 'watchlist.json'
RISK_PATH = TRADING_DIR / 'risk.json'

from delta_strike_selector import (
    TARGET_DELTA_COVERED_CALL,
    TARGET_DELTA_CSP,
    select_strike_by_delta,
)
from iv_rank import MIN_IV_RANK_FOR_PREMIUM, fetch_iv_rank
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
IB_PORT = int(os.getenv('IB_PORT', 7497))
IB_CLIENT_ID = 103  # Dedicated client ID for options (stocks use 101, test uses 102)

# Telegram settings
TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TG_CHAT = os.getenv('TELEGRAM_CHAT_ID')

# Safety limits (from trading/risk.json via risk_config)
MAX_OPTIONS_PER_DAY = get_max_options_per_day(TRADING_DIR)
MAX_OPTIONS_PER_MONTH = get_max_options_per_month(TRADING_DIR)
MIN_PREMIUM_PERCENT = 0.015  # Minimum 1.5% premium
MAX_RISK_PER_CONTRACT = 5000  # Max $5000 assignment risk per contract

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
    """Find covered call opportunities from current positions"""
    opportunities = []
    positions = get_ib_positions(ib)
    
    for pos in positions:
        if pos['quantity'] < 100:
            continue  # Need at least 100 shares
        
        ticker = pos['ticker']
        entry = pos['avgCost']
        
        try:
            # Get current price from IB (real-time)
            stock = Stock(ticker, 'SMART', 'USD')
            ib.qualifyContracts(stock)
            ib.reqMarketDataType(1)  # Live data
            [ticker_data] = ib.reqTickers(stock)
            ib.sleep(0.5)
            
            if ticker_data.last > 0:
                current = float(ticker_data.last)
            elif ticker_data.close > 0:
                current = float(ticker_data.close)
            else:
                print(f"No price data for {ticker}")
                continue
            
            iv_r = fetch_iv_rank(ticker, ib=ib)
            if iv_r is not None and iv_r < MIN_IV_RANK_FOR_PREMIUM:
                print(f"Skipping {ticker} covered call: IV rank {iv_r:.2f} < {MIN_IV_RANK_FOR_PREMIUM}")
                continue

            gain_pct = (current - entry) / entry
            if gain_pct >= 0.02:
                from datetime import timedelta
                target_exp = (datetime.now() + timedelta(days=35)).strftime("%Y%m%d")
                delta_strike = select_strike_by_delta(
                    ib, ticker, "C", target_exp,
                    target_delta=TARGET_DELTA_COVERED_CALL,
                )
                strike = delta_strike if delta_strike else round_option_strike(current * 1.12)
                room_to_strike = (strike - current) / current
                
                if not (current * 0.8 < strike < current * 1.5):
                    print(f"Skipping {ticker}: unreasonable strike ${strike} for current ${current}")
                    continue
                
                if room_to_strike >= 0.08:
                    # Calculate potential premium (estimate 2%)
                    premium_estimate = current * 0.02
                    premium_pct = premium_estimate / current
                    
                    if premium_pct >= MIN_PREMIUM_PERCENT:
                        opportunities.append({
                            'ticker': ticker,
                            'type': 'covered_call',
                            'current': current,
                            'entry': entry,
                            'strike': strike,
                            'dte': 35,
                            'quantity': pos['quantity'] // 100,
                            'gain_pct': gain_pct,
                            'premium_estimate': premium_estimate
                        })
        except Exception as e:
            print(f"Error checking {ticker}: {e}")
            continue
    
    return opportunities

def check_csp_opportunities():
    """Find cash-secured put opportunities from long candidates.

    CSPs are income trades on stocks you WANT to own at a lower price.
    Sources candidates exclusively from the long watchlist and long
    candidates in the multimode watchlist — never from short opportunities.
    """
    opportunities = []

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
        if not tickers and WATCHLIST_LEGACY_PATH.exists():
            data = json.loads(WATCHLIST_LEGACY_PATH.read_text())
            if isinstance(data, dict):
                for candidate in data.get("long_candidates", []):
                    if isinstance(candidate, dict) and "symbol" in candidate:
                        tickers.append(candidate["symbol"])
        tickers = list(set(tickers))
        if not tickers:
            print("No long candidates found in watchlists for CSP scanning")
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
            
            current = float(hist['Close'].iloc[-1])
            recent_high = float(hist['High'].tail(20).max())
            ema50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
            
            pullback_pct = (recent_high - current) / recent_high
            near_support = abs(current - ema50) / current < 0.02
            
            avg_vol = hist['Volume'].tail(20).mean()
            recent_vol = hist['Volume'].iloc[-1]
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 0

            iv_r = fetch_iv_rank(ticker)
            if iv_r is not None and iv_r < MIN_IV_RANK_FOR_PREMIUM:
                continue

            if 0.03 <= pullback_pct <= 0.08 and near_support and vol_ratio < 1.5:
                strike = round_option_strike(ema50 * 0.99)
                assignment_risk = strike * 100  # Risk if assigned
                
                if assignment_risk <= MAX_RISK_PER_CONTRACT:
                    premium_estimate = current * 0.02
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
    """Find iron condor opportunities on SPY/QQQ during CHOPPY regime.

    Iron condors sell premium when volatility is elevated but direction is unclear.
    Sell OTM put + OTM call, buy further OTM wings for protection.
    Best in CHOPPY regime with VIX > 15.
    """
    opportunities = []
    if regime not in ("CHOPPY", "MIXED"):
        return opportunities

    max_open_condors = 2
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
    Monthly budget capped at $5K or 0.5% of account, whichever is smaller.
    """
    opportunities = []
    if regime not in ("MIXED", "UNFAVORABLE", "STRONG_DOWNTREND"):
        return opportunities

    monthly_budget = min(5000.0, account_value * 0.005)

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
        
        # Get market price
        ib.reqMarketDataType(1)  # Live data
        [ticker_data] = ib.reqTickers(option)
        ib.sleep(1)
        
        if not ticker_data.marketPrice():
            print(f"No market data for {ticker} ${strike}{right}")
            return None
        
        bid = ticker_data.bid
        ask = ticker_data.ask
        mid = (bid + ask) / 2
        
        # Check minimum premium
        premium_pct = mid / opportunity['current']
        if premium_pct < MIN_PREMIUM_PERCENT:
            print(f"Premium too low: {premium_pct*100:.2f}% < {MIN_PREMIUM_PERCENT*100:.2f}%")
            return None
        
        # Place order (SELL to open)
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

def main():
    print("🤖 Auto Options Executor Starting...")
    
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
        account_value = 100_000.0
        try:
            summary = ib.reqAccountSummary()
            for item in summary:
                if item.tag == "NetLiquidation":
                    account_value = float(item.value)
                    break
        except Exception as e:
            print(f"Warning: Could not fetch account value from IB: {e}")
        print(f"Account value: ${account_value:,.0f}")
        
        # Find opportunities
        cc_opps = check_covered_call_opportunities(ib)
        csp_opps = check_csp_opportunities()
        
        print(f"\nFound:")
        print(f"  {len(cc_opps)} covered call opportunities")
        print(f"  {len(csp_opps)} cash-secured put opportunities")
        
        # Filter by sector concentration
        valid_opps = []
        if STRATEGY_MODULES_LOADED:
            print(f"\n🔍 Checking sector concentration...")
            for opp in cc_opps + csp_opps:
                sector_check = can_add_position(opp['ticker'], current_positions)
                if sector_check['allowed']:
                    valid_opps.append(opp)
                else:
                    print(f"  ❌ {opp['ticker']}: {sector_check['reason']}")
        else:
            valid_opps = cc_opps + csp_opps
        
        print(f"✅ Sector-compliant opportunities: {len(valid_opps)}")
        
        executed = []
        
        # Execute up to daily limit
        remaining = MAX_OPTIONS_PER_DAY - today_count
        
        for opp in valid_opps[:remaining]:
            # Calculate dynamic position sizing
            if STRATEGY_MODULES_LOADED:
                vix_data = get_vix_level()
                vix = vix_data['vix'] if vix_data['vix'] else 20
                
                sizing = calculate_composite_position_size(
                    symbol=opp['ticker'],
                    account_value=account_value,
                    vix=vix,
                    days_until_earnings=None,  # TODO: Get from earnings calendar
                    peak_value=account_value
                )
                
                adjusted_qty = int(opp['quantity'] * sizing['composite_multiplier'])
                if adjusted_qty < 1:
                    print(f"⏭️  Skipping {opp['ticker']}: Sizing too small ({sizing['composite_multiplier']:.0%})")
                    continue
                
                opp['quantity'] = adjusted_qty
                print(f"📊 {opp['ticker']}: {opp['quantity']} contracts (sizing: {sizing['composite_multiplier']:.0%})")
            
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
