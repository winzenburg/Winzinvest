#!/usr/bin/env python3
"""
Options Income Monitor - Covered Calls & Cash-Secured Puts
Monitors existing positions for covered call opportunities
Scans watchlist for cash-secured put opportunities
Sends Telegram notifications for manual review/approval
"""
import os, json, sys
from pathlib import Path
from datetime import datetime, timedelta

# Paths
TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'
WATCHLIST_PATH = TRADING_DIR / 'watchlist.json'
RISK_PATH = TRADING_DIR / 'risk.json'

def round_option_strike(strike):
    """Round strike to valid option intervals"""
    if strike > 200:
        interval = 5.0
    elif strike > 100:
        interval = 2.5
    else:
        interval = 1.0
    return round(strike / interval) * interval

def load_positions():
    """Load current positions from logs (approved trades)"""
    positions = []
    if not LOGS_DIR.exists():
        return positions
    
    for log_file in LOGS_DIR.glob('*.json'):
        try:
            with open(log_file) as f:
                data = json.load(f)
                intent = data.get('intent', {})
                if intent.get('signal') in ('long', 'buy', 'entry'):
                    positions.append({
                        'ticker': intent.get('ticker'),
                        'entry': intent.get('price'),
                        'stop': intent.get('stop_loss'),
                        'target': intent.get('take_profit'),
                        'entry_date': datetime.fromtimestamp(intent.get('ts', 0) / 1000) if intent.get('ts') else None
                    })
        except Exception:
            continue
    return positions

def check_covered_call_opportunities(positions):
    """Check if any long positions qualify for covered calls"""
    opportunities = []
    
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance not installed. Run: pip install yfinance")
        return opportunities
    
    for pos in positions:
        ticker = pos['ticker']
        entry = pos['entry']
        target = pos['target']
        entry_date = pos['entry_date']
        
        # Skip if no entry price or date
        if not entry or not entry_date:
            continue
        
        # Get current price
        try:
            stock = yf.Ticker(ticker)
            current = float(stock.history(period='1d')['Close'].iloc[-1])
        except Exception:
            continue
        
        # Calculate metrics
        gain_pct = (current - entry) / entry
        days_held = (datetime.now() - entry_date).days
        dist_to_target = (target - current) / current if target else 1.0
        
        # Check rules
        if gain_pct >= 0.05 and days_held >= 3 and dist_to_target >= 0.08:
            opportunities.append({
                'ticker': ticker,
                'entry': entry,
                'current': current,
                'gain_pct': gain_pct,
                'days_held': days_held,
                'target': target,
                'dist_to_target': dist_to_target,
                'type': 'covered_call',
                'suggested_strike': round_option_strike(current * 1.12),  # +12% OTM, rounded
                'suggested_dte': 35
            })
    
    return opportunities

def check_csp_opportunities():
    """Scan watchlist for cash-secured put opportunities"""
    opportunities = []
    
    # Load watchlist
    if not WATCHLIST_PATH.exists():
        return opportunities
    
    with open(WATCHLIST_PATH) as f:
        watchlist = json.load(f)
    
    # Flatten watchlist (handle both flat and grouped formats)
    tickers = []
    if isinstance(watchlist, dict):
        for key, val in watchlist.items():
            if isinstance(val, list):
                if key == 'watchlist':
                    tickers.extend([x.get('ticker') if isinstance(x, dict) else x for x in val])
                else:
                    tickers.extend(val)
    
    # Get currently held positions
    positions = load_positions()
    held_tickers = {p['ticker'] for p in positions}
    
    try:
        import yfinance as yf
    except ImportError:
        return opportunities
    
    for ticker in tickers:
        # Skip if already holding
        if ticker in held_tickers:
            continue
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='60d')
            if hist.empty:
                continue
            
            current = float(hist['Close'].iloc[-1])
            recent_high = float(hist['High'].tail(20).max())
            ema50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
            
            # Calculate pullback from recent high
            pullback_pct = (recent_high - current) / recent_high
            
            # Check if near support (within 2% of 50 EMA)
            near_support = abs(current - ema50) / current < 0.02
            
            # Volume check (not panic selling)
            avg_vol = hist['Volume'].tail(20).mean()
            recent_vol = hist['Volume'].iloc[-1]
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 0
            
            # Check rules: 3-8% pullback, near support, normal volume
            if 0.03 <= pullback_pct <= 0.08 and near_support and vol_ratio < 1.5:
                opportunities.append({
                    'ticker': ticker,
                    'current': current,
                    'recent_high': recent_high,
                    'pullback_pct': pullback_pct,
                    'ema50': ema50,
                    'vol_ratio': vol_ratio,
                    'type': 'cash_secured_put',
                    'suggested_strike': round_option_strike(ema50 * 0.99),  # Slightly below EMA50, rounded
                    'suggested_dte': 35
                })
        except Exception:
            continue
    
    return opportunities

def create_pending_intent(opp):
    """Create pending intent for options order approval"""
    import uuid, time
    
    PENDING_DIR = TRADING_DIR / 'pending'
    PENDING_DIR.mkdir(exist_ok=True)
    
    intent_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    token = uuid.uuid4().hex
    
    intent = {
        'id': intent_id,
        'token': token,
        'ticker': opp['ticker'],
        'type': opp['type'],
        'option_type': 'call' if opp['type'] == 'covered_call' else 'put',
        'strike': opp['suggested_strike'],
        'dte': opp['suggested_dte'],
        'action': 'SELL',  # Selling covered calls or CSPs
        'quantity': 1,  # 1 contract = 100 shares
        'underlying_price': opp['current'],
        'canary': True,
        'ts': int(time.time() * 1000),
        'metrics': {
            'gain_pct': opp.get('gain_pct'),
            'pullback_pct': opp.get('pullback_pct'),
            'days_held': opp.get('days_held'),
            'vol_ratio': opp.get('vol_ratio')
        }
    }
    
    intent_file = PENDING_DIR / f"{intent_id}.json"
    with open(intent_file, 'w') as f:
        json.dump(intent, f, indent=2)
    
    return intent_id, token

def format_telegram_message(opportunities):
    """Format opportunities as Telegram message with approve/reject buttons"""
    if not opportunities:
        return None, []
    
    BASE_URL = os.getenv('BASE_URL')
    if not BASE_URL:
        # Fallback to manual review if no BASE_URL
        return format_telegram_message_manual(opportunities), []
    
    # Create pending intents and collect buttons
    all_buttons = []
    
    for opp in opportunities[:5]:  # Limit to 5 total
        intent_id, token = create_pending_intent(opp)
        
        # Create button row for this opportunity
        approve_url = f"{BASE_URL}/act?op=approve&token={token}"
        reject_url = f"{BASE_URL}/act?op=reject&token={token}"
        
        ticker = opp['ticker']
        strike = opp['suggested_strike']
        opt_type = 'C' if opp['type'] == 'covered_call' else 'P'
        
        button_row = [
            {"text": f"✅ {ticker} ${strike}{opt_type}", "url": approve_url},
            {"text": "❌", "url": reject_url}
        ]
        all_buttons.append(button_row)
    
    # Build message
    msg = "📊 *Options Income Opportunities*\n\n"
    
    cc_opps = [o for o in opportunities if o['type'] == 'covered_call']
    csp_opps = [o for o in opportunities if o['type'] == 'cash_secured_put']
    
    if cc_opps:
        msg += "🟢 *Covered Calls*:\n"
        for opp in cc_opps[:3]:
            msg += f"\n*{opp['ticker']}* ${opp['suggested_strike']} call\n"
            msg += f"  +{opp['gain_pct']*100:.1f}%, {opp['days_held']}d held\n"
    
    if csp_opps:
        if cc_opps:
            msg += "\n"
        msg += "🔵 *Cash-Secured Puts*:\n"
        for opp in csp_opps[:3]:
            msg += f"\n*{opp['ticker']}* ${opp['suggested_strike']} put\n"
            msg += f"  -{opp['pullback_pct']*100:.1f}% pullback\n"
    
    msg += "\n_Click buttons to approve/reject_"
    
    return msg, all_buttons

def format_telegram_message_manual(opportunities):
    """Fallback format without buttons"""
    msg = "📊 *Options Income Opportunities*\n\n"
    
    cc_opps = [o for o in opportunities if o['type'] == 'covered_call']
    csp_opps = [o for o in opportunities if o['type'] == 'cash_secured_put']
    
    if cc_opps:
        msg += "🟢 *Covered Calls* (on profitable longs):\n"
        for opp in cc_opps:
            msg += f"\n*{opp['ticker']}*\n"
            msg += f"  Entry: ${opp['entry']:.2f} → Current: ${opp['current']:.2f} (+{opp['gain_pct']*100:.1f}%)\n"
            msg += f"  Days held: {opp['days_held']}\n"
            msg += f"  Target: ${opp['target']:.2f} ({opp['dist_to_target']*100:.1f}% away)\n"
            msg += f"  💡 Suggest: Sell ${opp['suggested_strike']} call, {opp['suggested_dte']} DTE\n"
    
    if csp_opps:
        if cc_opps:
            msg += "\n"
        msg += "🔵 *Cash-Secured Puts* (watchlist pullbacks):\n"
        for opp in csp_opps[:5]:
            msg += f"\n*{opp['ticker']}*\n"
            msg += f"  Current: ${opp['current']:.2f} (pulled back {opp['pullback_pct']*100:.1f}% from ${opp['recent_high']:.2f})\n"
            msg += f"  Support (50 EMA): ${opp['ema50']:.2f}\n"
            msg += f"  Volume: {opp['vol_ratio']:.2f}x avg (normal)\n"
            msg += f"  💡 Suggest: Sell ${opp['suggested_strike']} put, {opp['suggested_dte']} DTE\n"
    
    msg += "\n_Review and execute manually via your broker_"
    
    return msg

def send_telegram(text, buttons=None):
    """Send Telegram notification with optional inline buttons"""
    import urllib.parse, urllib.request
    
    TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TG_CHAT = os.getenv('TELEGRAM_CHAT_ID')
    
    if not (TG_TOKEN and TG_CHAT):
        print("Telegram not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)")
        return False
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        'chat_id': TG_CHAT,
        'text': text,
        'parse_mode': 'Markdown'
    }
    
    if buttons:
        payload['reply_markup'] = json.dumps({'inline_keyboard': buttons})
    
    data = urllib.parse.urlencode(payload).encode()
    
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Failed to send Telegram: {e}")
        return False

def main():
    print("🔍 Scanning for options income opportunities...")
    
    # Check for covered call opportunities
    positions = load_positions()
    cc_opportunities = check_covered_call_opportunities(positions)
    print(f"  Found {len(cc_opportunities)} covered call opportunities")
    
    # Check for CSP opportunities
    csp_opportunities = check_csp_opportunities()
    print(f"  Found {len(csp_opportunities)} cash-secured put opportunities")
    
    # Combine and format
    all_opportunities = cc_opportunities + csp_opportunities
    
    if all_opportunities:
        msg, buttons = format_telegram_message(all_opportunities)
        if msg:
            print("\n" + msg.replace('*', '').replace('_', ''))
            
            # Send to Telegram if configured
            if send_telegram(msg, buttons):
                print(f"\n✅ Sent to Telegram ({len(buttons)} opportunities with approve/reject buttons)")
            else:
                print("\n⚠️ Telegram not configured or failed to send")
    else:
        print("\n✅ No opportunities meeting criteria right now")

if __name__ == '__main__':
    main()
