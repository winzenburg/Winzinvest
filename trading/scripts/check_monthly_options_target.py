#!/usr/bin/env python3
"""
Monthly Options Target Checker
Runs on last Friday of each month to ensure minimum deployment target is met
"""
import os, json, sys
from pathlib import Path
from datetime import datetime
from calendar import monthrange

# Paths
TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'
OPTIONS_DIR = TRADING_DIR / 'options'

# Targets
MIN_MONTHLY_TARGET = 2
IDEAL_MONTHLY_TARGET = 4

def count_options_trades_this_month():
    """Count options trades deployed this month"""
    if not LOGS_DIR.exists():
        return 0, []
    
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    options_trades = []
    
    for log_file in LOGS_DIR.glob('*.json'):
        try:
            with open(log_file) as f:
                data = json.load(f)
                intent = data.get('intent', {})
                
                # Check if this is an options trade
                if intent.get('option_type'):
                    # Get timestamp
                    ts = intent.get('ts', 0)
                    if ts:
                        trade_date = datetime.fromtimestamp(ts / 1000)
                        if trade_date.month == current_month and trade_date.year == current_year:
                            options_trades.append({
                                'date': trade_date.strftime('%Y-%m-%d'),
                                'ticker': intent.get('ticker'),
                                'type': intent.get('type'),
                                'strike': intent.get('strike'),
                                'option_type': intent.get('option_type')
                            })
        except Exception:
            continue
    
    return len(options_trades), options_trades

def is_last_week_of_month():
    """Check if we're in the last 7 days of the month"""
    now = datetime.now()
    last_day = monthrange(now.year, now.month)[1]
    days_remaining = last_day - now.day
    return days_remaining <= 7

def format_telegram_message(count, trades, is_last_week):
    """Format status message"""
    now = datetime.now()
    month_name = now.strftime('%B %Y')
    
    msg = f"📊 *Options Income - {month_name}*\n\n"
    msg += f"Deployed: *{count}* trades\n"
    msg += f"Target: {MIN_MONTHLY_TARGET}-{IDEAL_MONTHLY_TARGET} trades\n\n"
    
    if count >= IDEAL_MONTHLY_TARGET:
        msg += "✅ *Target exceeded!* Great month.\n"
        if trades:
            msg += "\n*Trades this month:*\n"
            for t in trades:
                msg += f"  • {t['date']}: {t['ticker']} ${t['strike']} {t['option_type'].upper()}\n"
    elif count >= MIN_MONTHLY_TARGET:
        msg += "✅ *Minimum target met.*\n"
        remaining = IDEAL_MONTHLY_TARGET - count
        msg += f"\n_{remaining} more to ideal target_\n"
        if is_last_week:
            msg += "\n💡 Consider adding 1-2 more quality setups if available."
    else:
        needed = MIN_MONTHLY_TARGET - count
        msg += f"⚠️ *Below minimum!* Need {needed} more.\n"
        if is_last_week:
            msg += "\n🚨 *Last week of month* - Force deploy if needed:\n"
            msg += "  • Review watchlist for best CSP opportunities\n"
            msg += "  • Accept slightly lower quality (2-7% pullbacks)\n"
            msg += "  • Still require support levels & normal volume\n"
        else:
            msg += f"\n_Plenty of time remaining this month_"
    
    return msg

def send_telegram(text):
    """Send Telegram notification"""
    import urllib.parse, urllib.request
    
    TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TG_CHAT = os.getenv('TELEGRAM_CHAT_ID')
    
    if not (TG_TOKEN and TG_CHAT):
        print("Telegram not configured")
        return False
    
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
    except Exception as e:
        print(f"Failed to send Telegram: {e}")
        return False

def main():
    count, trades = count_options_trades_this_month()
    is_last_week = is_last_week_of_month()
    
    print(f"Options trades this month: {count}")
    print(f"Last week of month: {is_last_week}")
    
    msg = format_telegram_message(count, trades, is_last_week)
    print("\n" + msg.replace('*', '').replace('_', ''))
    
    # Send to Telegram
    if send_telegram(msg):
        print("\n✅ Sent to Telegram")
    else:
        print("\n⚠️ Telegram not configured or failed to send")

if __name__ == '__main__':
    main()
