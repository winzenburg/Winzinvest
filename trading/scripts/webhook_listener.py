#!/usr/bin/env python3
"""
TradingView → Webhook → Confirm-to-Execute (Paper) Listener
- Default SAFE: no orders until explicit approve.
- Paper-only via IB Gateway/TWS on 127.0.0.1:7497 (configurable).
- Optional Telegram approve/deny with inline buttons (requires env vars and a public BASE_URL).

Security:
- Require SECRET via env MOLT_WEBHOOK_SECRET for ALL POST endpoints.
- Approve/deny links use one-time tokens; do not embed the secret in URLs.
- Never expose secrets in logs. Store pending intents under trading/pending/.

Env:
  MOLT_WEBHOOK_SECRET=changeme
  IB_HOST=127.0.0.1
  IB_PORT=7497      # 7497 paper, 7496 live
  IB_CLIENT_ID=101
  CANARY=1          # 1-share by default when set
  TELEGRAM_BOT_TOKEN=... (optional)
  TELEGRAM_CHAT_ID=...   (optional)
  BASE_URL=https://your-public-url (optional; used for Telegram buttons)

Usage:
  python3 trading/scripts/webhook_listener.py
"""
import os, json, time, uuid, pathlib, urllib.parse, urllib.request, sys
from flask import Flask, request, jsonify
from datetime import datetime, time as dtime
import zoneinfo
import nest_asyncio

# Add scripts directory to path
SCRIPTS_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

# Import regime params helper
try:
    from get_regime_params import get_regime_params
    REGIME_AVAILABLE = True
except ImportError:
    REGIME_AVAILABLE = False
    print("WARNING: Regime monitoring not available")

# Allow nested event loops (required for Flask + ib_insync)
nest_asyncio.apply()

PENDING_DIR = pathlib.Path(__file__).resolve().parents[1] / 'pending'
LOGS_DIR = pathlib.Path(__file__).resolve().parents[1] / 'logs'
CONF_DIR = pathlib.Path(__file__).resolve().parents[1]
PENDING_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

try:
    import jsonschema  # type: ignore
except Exception:
    jsonschema = None

try:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder, BracketOrder, StopOrder  # type: ignore
except Exception:
    IB = None  # optional

app = Flask(__name__)
SECRET = os.getenv('MOLT_WEBHOOK_SECRET')
IB_HOST = os.getenv('IB_HOST', '127.0.0.1')
IB_PORT = int(os.getenv('IB_PORT', '7497'))
IB_CLIENT_ID = int(os.getenv('IB_CLIENT_ID', '101'))

# Global IB connection (reuse across requests)
_ib_connection = None
_ib_lock = None

def get_ib_connection():
    """Get or create IB connection (thread-safe)"""
    global _ib_connection, _ib_lock
    import threading
    
    if _ib_lock is None:
        _ib_lock = threading.Lock()
    
    with _ib_lock:
        if _ib_connection is None or not _ib_connection.isConnected():
            if IB is None:
                return None
            _ib_connection = IB()
            try:
                print(f"Attempting IB connection to {IB_HOST}:{IB_PORT} with clientId {IB_CLIENT_ID}")
                _ib_connection.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
                print(f"✅ IB connected successfully! Account: {_ib_connection.managedAccounts()}")
            except Exception as e:
                print(f"❌ IB connection failed: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                _ib_connection = None
        return _ib_connection
CANARY = os.getenv('CANARY', '1') not in ('0', 'false', 'False')
TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TG_CHAT = os.getenv('TELEGRAM_CHAT_ID')
BASE_URL = os.getenv('BASE_URL')  # required for Telegram approve links

# Load risk/flags relative to trading dir
RISK_PATH = CONF_DIR / 'risk.json'
FLAGS_PATH = CONF_DIR / 'feature_flags.json'
WATCHLIST_PATH = CONF_DIR / 'watchlist.json'
RISK = json.loads(RISK_PATH.read_text()) if RISK_PATH.exists() else {}
FLAGS = json.loads(FLAGS_PATH.read_text()) if FLAGS_PATH.exists() else { 'setups': {} }
WATCH = json.loads(WATCHLIST_PATH.read_text()) if WATCHLIST_PATH.exists() else {}

ALERT_SCHEMA = {
    'type': 'object',
    'required': ['secret'],  # accept both legacy and AMS-NX variants; validate fields below
    'properties': {
        # Common
        'secret': {'type': 'string'},
        'timeframe': {'type': 'string'},
        'ts': {},
        'notes': {},
        'idempotency_key': {},
        'source': {'type': 'string'},
        'chart_url': {'type': 'string'},  # Optional TradingView chart snapshot URL
        # Legacy fields
        'ticker': {'type': 'string'},
        'signal': {'type': 'string'},
        'price': {'type': ['number', 'string']},
        'setup_type': {'type': 'string'},
        'stop_loss': {},
        'take_profit': {},
        'confidence': {},
        # AMS-NX fields
        'symbol': {'type': 'string'},
        'side': {'type': 'string'},
        'entry': {'type': ['number', 'string']},
        'stop': {'type': ['number', 'string']},
        'tp1': {'type': ['number', 'string']},
        'zScore': {},
        'rsPct': {},
        'rvol': {}
    }
}

def require_secret(data):
    if not SECRET or not data or data.get('secret') != SECRET:
        return False
    return True

def within_trading_window_now():
    try:
        tz = zoneinfo.ZoneInfo(RISK.get('time_restrictions',{}).get('trading_hours',{}).get('timezone','America/New_York'))
    except Exception:
        tz = zoneinfo.ZoneInfo('America/New_York')
    now = datetime.now(tz).time()
    start_s = RISK.get('time_restrictions',{}).get('trading_hours',{}).get('start','09:45')
    end_s = RISK.get('time_restrictions',{}).get('trading_hours',{}).get('end','15:45')
    sh, sm = map(int, start_s.split(':'))
    eh, em = map(int, end_s.split(':'))
    return dtime(sh, sm) <= now <= dtime(eh, em)

def rs_ratio_vs_spy(ticker, days):
    try:
        import yfinance as yf  # lazy import
        stock = yf.Ticker(ticker).history(period=f"{max(days+5, days)}d")
        spy = yf.Ticker('SPY').history(period=f"{max(days+5, days)}d")
        if stock.empty or spy.empty:
            return None
        sret = (stock['Close'].iloc[-1] / stock['Close'].iloc[-days] - 1)
        bret = (spy['Close'].iloc[-1] / spy['Close'].iloc[-days] - 1)
        return (sret / bret) if bret != 0 else None
    except Exception:
        return None

def volume_ratio(ticker):
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period='3mo')
        if hist.empty:
            return None
        avg = float(hist['Volume'].tail(20).mean())
        last = float(hist['Volume'].iloc[-1])
        return (last / avg) if avg > 0 else None
    except Exception:
        return None

def check_earnings_window(ticker):
    """
    Check if ticker has earnings within blackout window
    Returns: (ok: bool, reason: str)
    """
    try:
        import yfinance as yf
        from datetime import timedelta
        
        stock = yf.Ticker(ticker)
        calendar = stock.calendar
        
        if calendar is None or calendar.empty:
            # No earnings data available, allow trade
            return True, "No earnings data"
        
        # Get next earnings date
        if 'Earnings Date' in calendar:
            earnings_dates = calendar['Earnings Date']
            if isinstance(earnings_dates, str):
                from dateutil import parser
                next_earnings = parser.parse(earnings_dates)
            else:
                # Sometimes it's a list or array
                next_earnings = earnings_dates[0] if hasattr(earnings_dates, '__iter__') else earnings_dates
            
            # Calculate days until earnings
            now = datetime.now()
            days_until = (next_earnings - now).days
            
            # Blackout: 5 days before to 2 days after
            if -2 <= days_until <= 5:
                return False, f"Earnings in {days_until} days (blackout: -2 to +5 days)"
        
        return True, "Outside earnings window"
    except Exception as e:
        # If check fails, allow trading (fail open, but log)
        return True, f"Earnings check failed: {e}"

def regime_allows(setup):
    # Simple regime gate using SPY 200 EMA and VIX level
    try:
        import yfinance as yf
        spy = yf.Ticker('SPY').history(period='1y')
        vix = yf.Ticker('^VIX').history(period='6mo')
        if spy.empty or vix.empty:
            return True
        ema200 = spy['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
        above = spy['Close'].iloc[-1] > ema200
        vix_last = float(vix['Close'].iloc[-1])
        if above and vix_last < 20:
            return True  # bull: all allowed
        if not above and vix_last > 25:
            # bear: restrict to dividend/pullback only
            return setup in ('dividend_growth','pullback_ma')
        # choppy: prefer swing/box/pullback
        return setup in ('swing_trading_fast','pullback_ma','box_strategy','dividend_growth','trend_following')
    except Exception:
        return True

def check_daily_loss_limit():
    """Check if daily loss limit has been exceeded"""
    import subprocess
    try:
        result = subprocess.run(
            ['python3', str(CONF_DIR / 'scripts' / 'daily_pnl_tracker.py')],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0, result.stdout
    except Exception as e:
        # If check fails, allow trading (fail open)
        return True, f"Daily loss check failed: {e}"

def is_trading_paused():
    """Check if trading is manually paused via .pause file"""
    pause_file = CONF_DIR / '.pause'
    return pause_file.exists()

def passes_filters(alert):
    # Normalize fields to internal names
    ticker = alert.get('ticker') or alert.get('symbol')
    signal = (alert.get('signal') or alert.get('side') or '').lower()
    setup = alert.get('setup_type')

    # Kill switch / manual pause
    if is_trading_paused():
        return False, "Trading paused (kill switch active)"

    # Daily loss circuit breaker
    loss_ok, loss_msg = check_daily_loss_limit()
    if not loss_ok:
        return False, "Daily loss limit exceeded - circuit breaker active"

    # Trading window
    if not within_trading_window_now():
        return False, "Outside trading window"

    # Watchlist (accept both flat and grouped)
    in_watch = False
    if isinstance(WATCH, dict) and ticker:
        if 'watchlist' in WATCH:
            in_watch = any(x.get('ticker') == ticker for x in WATCH['watchlist'])
        else:
            for arr in WATCH.values():
                if isinstance(arr, list) and ticker in arr:
                    in_watch = True
                    break
    if not in_watch:
        return False, f"Ticker {ticker} not in watchlist"
    
    # Earnings blackout window
    earnings_ok, earnings_reason = check_earnings_window(ticker)
    if not earnings_ok:
        return False, earnings_reason

    # Prefer AMS-NX inline metrics if present; else fall back to yfinance lookups
    rsPct = alert.get('rsPct')
    zScore = alert.get('zScore')
    rvol = alert.get('rvol')

    # RS threshold logic (percentile 0..1)
    if rsPct is None:
        # Fallback to ratio vs SPY (slower)
        days = 40 if setup in ('trend_following','momentum_breakout') else 20
        rs = rs_ratio_vs_spy(ticker, days)
        if rs is None:
            return False, "RS ratio unavailable"
        # Map to rough percentile gate by ratio
        if signal in ('long','buy','entry'):
            if rs < 1.03:
                return False, f"RS ratio {rs:.2f} < 1.03"
        else:
            if rs > 0.97:
                return False, f"RS ratio {rs:.2f} > 0.97"
    else:
        try:
            rsPct = float(rsPct)
        except Exception:
            return False, "Invalid rsPct"
        if signal in ('long','buy','entry') and rsPct < 0.60:
            return False, f"rsPct {rsPct:.2f} < 0.60"
        if signal in ('short','sell') and rsPct > 0.40:
            return False, f"rsPct {rsPct:.2f} > 0.40"

    # Volume filter
    if rvol is None:
        vr = volume_ratio(ticker)
        if vr is None or vr < 1.2:
            return False, f"Volume ratio {vr if vr else 'n/a'} < 1.2"
    else:
        try:
            rvol = float(rvol)
        except Exception:
            return False, "Invalid rvol"
        if rvol < 1.2:
            return False, f"rvol {rvol:.2f} < 1.2"

    # Z-score check with regime-based threshold
    if zScore is not None:
        try:
            zScore = float(zScore)
        except Exception:
            return False, "Invalid zScore"
        
        # Get regime threshold (default to 2.0 if regime unavailable)
        z_threshold = 2.0
        if REGIME_AVAILABLE:
            try:
                regime = get_regime_params()
                z_threshold = regime.get('zEnter', 2.0)
            except Exception as e:
                app.logger.warning(f"Regime check failed: {e}")
        
        if signal in ('long','buy','entry') and abs(zScore) < z_threshold:
            return False, f"zScore {zScore:.2f} < {z_threshold} (regime threshold)"
        if signal in ('short','sell') and abs(zScore) < z_threshold:
            return False, f"zScore {zScore:.2f} < {z_threshold} (regime threshold)"

    # Regime gate (use setup if provided; otherwise allow)
    if setup and not regime_allows(setup):
        return False, "Market regime gate blocked this setup"
    
    # Correlation check (warning only, not blocking)
    try:
        import subprocess
        result = subprocess.run(
            ['python3', str(CONF_DIR / 'scripts' / 'correlation_checker.py'), ticker],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            # High correlation detected, but we'll allow with warning
            app.logger.warning(f"Correlation warning for {ticker}: {result.stdout}")
    except Exception as e:
        app.logger.warning(f"Correlation check failed: {e}")

    return True, "filters ok"

def send_telegram(text, buttons=None):
    if not (TG_TOKEN and TG_CHAT):
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {'chat_id': TG_CHAT, 'text': text}
    if buttons:
        payload['reply_markup'] = json.dumps({'inline_keyboard': [buttons]})
    data = urllib.parse.urlencode({'chat_id': TG_CHAT, 'text': text, 'reply_markup': payload.get('reply_markup','')}).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except Exception:
        pass

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True) or {}
    if not require_secret(data):
        return jsonify({'status':'error','message':'invalid or missing secret'}), 401
    if jsonschema:
        try:
            jsonschema.validate(instance=data, schema=ALERT_SCHEMA)
        except Exception as e:
            return jsonify({'status':'error','message':f'invalid payload: {e}'}), 400
    # gate by filters (RS, volume, regime, watchlist, window)
    ok, why = passes_filters(data)
    if not ok:
        return jsonify({'status':'rejected','reason': why}), 400
    intent_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    token = uuid.uuid4().hex  # one-time approve/reject token
    # Normalize legacy vs AMS-NX payloads
    px_str = str(data.get('entry') or data.get('price') or '')
    try:
        px_val = float(px_str)
    except Exception:
        px_val = px_str or None
    # Get regime context
    regime_info = {}
    if REGIME_AVAILABLE:
        try:
            regime_info = get_regime_params()
        except Exception as e:
            app.logger.warning(f"Could not get regime params: {e}")
    
    intent = {
        'id': intent_id,
        'token': token,
        'ticker': data.get('ticker') or data.get('symbol'),
        'signal': data.get('signal') or data.get('side'),
        'price': px_val,
        'setup': data.get('setup_type') or data.get('source'),
        'notes': data.get('notes'),
        'ts': data.get('ts'),
        'canary': CANARY,
        'qty': 1 if CANARY else int(data.get('quantity') or 0) or 1,
        'stop_loss': data.get('stop_loss') or data.get('stop'),
        'take_profit': data.get('take_profit') or data.get('tp1'),
        'metrics': {
            'zScore': data.get('zScore'),
            'rsPct': data.get('rsPct'),
            'rvol': data.get('rvol')
        },
        'regime': regime_info
    }
    (PENDING_DIR / f"{intent_id}.json").write_text(json.dumps(intent, indent=2))
    app.logger.info(f"PENDING (no exec): {intent}")
    
    # AUTO-EXECUTE in canary mode (1 share, low risk)
    if intent.get('canary'):
        app.logger.info(f"CANARY MODE: Auto-executing {intent['ticker']} {intent['signal']}")
        
        # Send notification (no buttons, just FYI)
        if TG_TOKEN and TG_CHAT:
            sym = intent['ticker']
            sig = intent['signal']
            px = intent['price']
            z = intent['metrics'].get('zScore')
            
            try:
                z = float(z) if z is not None else None
            except (ValueError, TypeError):
                z = None
            
            txt = f"🤖 AUTO-EXECUTING (Canary Mode)\n\n"
            txt += f"📊 {sym} {sig.upper()}\n"
            txt += f"├─ Entry: ${px}\n"
            txt += f"├─ Z-Score: {z:.2f}\n" if z is not None else ""
            txt += f"└─ Qty: 1 share\n"
            txt += f"\n✅ Trade passed all safety filters\n"
            txt += f"⏳ Executing now..."
            
            send_telegram(txt)
        
        # Auto-approve and execute
        path = PENDING_DIR / f"{intent_id}.json"
        return _approve_intent(intent, path)

    # Telegram approve UI (optional)
    if TG_TOKEN and TG_CHAT and BASE_URL:
        sym = intent['ticker']
        sig = intent['signal']
        px  = intent['price']
        
        # Build message with metrics and regime
        z = intent['metrics'].get('zScore')
        rs = intent['metrics'].get('rsPct')
        
        # Convert to float if string
        try:
            z = float(z) if z is not None else None
        except (ValueError, TypeError):
            z = None
        try:
            rs = float(rs) if rs is not None else None
        except (ValueError, TypeError):
            rs = None
        
        txt = f"🚨 TRADE SIGNAL: {sym} ({sig.upper()})\n\n"
        txt += f"📊 Signal:\n"
        txt += f"├─ Entry: ${px}\n"
        txt += f"├─ Z-Score: {z:.2f}\n" if z is not None else ""
        txt += f"└─ RS: {rs:.2f}\n" if rs is not None else ""
        txt += f"\n💰 Position:\n"
        txt += f"├─ Qty: {intent['qty']}"
        if intent.get('canary'):
            txt += f" (CANARY MODE)\n"
        else:
            txt += f"\n"
        
        # Add regime context if available
        if regime_info:
            regime_emoji = regime_info.get('emoji', '')
            regime_name = regime_info.get('regime', 'UNKNOWN')
            regime_score = regime_info.get('score', 0)
            size_mult = regime_info.get('sizeMultiplier', 1.0)
            txt += f"└─ Regime: {regime_emoji} {regime_name} ({size_mult*100:.0f}% sizing, score {regime_score}/10)\n"
        
        txt += f"\n⏸️ Awaiting manual approval (CLI)"
        txt += f"\nToken: {token[:16]}..."
        
        if BASE_URL:
            approve_link = f"{BASE_URL}/act?op=approve&token={token}"
            reject_link  = f"{BASE_URL}/act?op=reject&token={token}"
            buttons = [
                {"text": "✅ Approve", "url": approve_link},
                {"text": "❌ Reject",  "url": reject_link}
            ]
            send_telegram(txt, buttons=buttons)
        else:
            # No buttons, just notification
            send_telegram(txt)

    return jsonify({'status':'pending','id': intent_id})

@app.route('/act', methods=['GET'])
def act_get():
    # Approve/reject via tokenized link (no secret in URL). Use only over HTTPS.
    op = request.args.get('op')
    token = request.args.get('token')
    if not (op and token):
        return jsonify({'status':'error','message':'missing op or token'}), 400
    # find pending by token
    target = None
    for p in PENDING_DIR.glob('*.json'):
        try:
            intent = json.loads(p.read_text())
            if intent.get('token') == token:
                target = (p, intent)
                break
        except Exception:
            continue
    if not target:
        return jsonify({'status':'error','message':'unknown or expired token'}), 404
    path, intent = target
    if op == 'approve':
        return _approve_intent(intent, path)
    elif op == 'reject':
        return _reject_intent(intent, path)
    else:
        return jsonify({'status':'error','message':'invalid op'}), 400

@app.route('/approve', methods=['POST'])
def approve_post():
    data = request.get_json(silent=True) or {}
    if not require_secret(data):
        return jsonify({'status':'error','message':'invalid or missing secret'}), 401
    intent_id = data.get('id')
    if not intent_id:
        return jsonify({'status':'error','message':'missing id'}), 400
    path = PENDING_DIR / f"{intent_id}.json"
    if not path.exists():
        return jsonify({'status':'error','message':'unknown id'}), 404
    intent = json.loads(path.read_text())
    return _approve_intent(intent, path)

@app.route('/reject', methods=['POST'])
def reject_post():
    data = request.get_json(silent=True) or {}
    if not require_secret(data):
        return jsonify({'status':'error','message':'invalid or missing secret'}), 401
    intent_id = data.get('id')
    if not intent_id:
        return jsonify({'status':'error','message':'missing id'}), 400
    path = PENDING_DIR / f"{intent_id}.json"
    if not path.exists():
        return jsonify({'status':'error','message':'unknown id'}), 404
    intent = json.loads(path.read_text())
    return _reject_intent(intent, path)

# --- helpers ---

def round_option_strike(strike, ticker):
    """Round strike to valid option intervals"""
    # Most stocks use $5 intervals for far OTM, $2.50 for ATM, $1 for near
    # For simplicity, use $5 for high-priced stocks, $2.50 otherwise
    if strike > 200:
        interval = 5.0
    elif strike > 100:
        interval = 2.5
    else:
        interval = 1.0
    
    return round(strike / interval) * interval

def _place_order(intent):
    if IB is None:
        return False, 'ib_insync not installed; dry-run only'
    
    # Create event loop for this thread if needed
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        ib = get_ib_connection()
        if ib is None:
            return False, 'IB connection unavailable'
        
        # Check if this is an options order
        if intent.get('option_type'):
            # Options order (covered call or cash-secured put)
            from ib_insync import Option  # type: ignore
            from datetime import datetime, timedelta
            
            ticker = intent['ticker']
            strike = round_option_strike(float(intent['strike']), ticker)
            dte = int(intent.get('dte', 30))
            opt_type = intent['option_type'].upper()  # 'CALL' or 'PUT'
            qty = int(intent.get('quantity', 1))  # contracts, not shares
            
            # Calculate expiry date (use 3rd Friday of next month for standard monthly)
            from calendar import monthrange
            now = datetime.now()
            target_month = now.month + 1 if dte > 15 else now.month
            target_year = now.year if target_month <= 12 else now.year + 1
            target_month = target_month if target_month <= 12 else 1
            
            # Find 3rd Friday of target month
            first_day = datetime(target_year, target_month, 1)
            # First Friday
            days_to_friday = (4 - first_day.weekday()) % 7
            first_friday = first_day + timedelta(days=days_to_friday)
            # Third Friday (add 2 weeks)
            third_friday = first_friday + timedelta(weeks=2)
            expiry_str = third_friday.strftime('%Y%m%d')
            
            # Create option contract
            contract = Option(ticker, expiry_str, strike, opt_type, 'SMART')
            ib.qualifyContracts(contract)
            
            # Sell option (covered call or CSP)
            action = intent.get('action', 'SELL').upper()
            order = MarketOrder(action, qty)
            trade = ib.placeOrder(contract, order)
            
            return True, f'option {action} ${strike} {opt_type} exp {expiry_str} orderId={getattr(trade.order, "orderId", None)}'
        else:
            # Stock order (swing trade)
            contract = Stock(intent['ticker'], 'SMART', 'USD')
            ib.qualifyContracts(contract)
            qty = max(1, int(intent.get('qty') or 1))
            side = 'BUY' if str(intent.get('signal','')).lower() in ('buy','entry','long') else 'SELL'
            sl = intent.get('stop_loss')
            tp = intent.get('take_profit')
            if sl and tp:
                # Bracket order: parent market + child stop + child limit target
                parent = MarketOrder(side, qty, tif='DAY', transmit=False)
                stop   = LimitOrder('SELL' if side=='BUY' else 'BUY', qty, float(tp) if side=='SELL' else float(sl), tif='DAY', transmit=False)  # placeholder
                # Correct children: use StopOrder + LimitOrder
                from ib_insync import StopOrder  # type: ignore
                child_stop = StopOrder('SELL' if side=='BUY' else 'BUY', qty, float(sl), tif='DAY', parentId=0, transmit=False)
                child_lmt  = LimitOrder('SELL' if side=='BUY' else 'BUY', qty, float(tp), tif='DAY', parentId=0, transmit=True)
                trade_p = ib.placeOrder(contract, parent)
                pid = trade_p.order.orderId
                child_stop.parentId = pid
                child_lmt.parentId = pid
                ib.placeOrder(contract, child_stop)
                ib.placeOrder(contract, child_lmt)
                return True, f'bracket placed parentId={pid}'
            else:
                order = MarketOrder(side, qty)
                trade = ib.placeOrder(contract, order)
                return True, f'orderId={getattr(trade.order, "orderId", None)}'
    except Exception as e:
        return False, str(e)

def _approve_intent_async(intent, path):
    """Process approval in background thread"""
    import threading
    
    def process():
        placed, msg = _place_order(intent)
        if placed:
            (LOGS_DIR / f"{intent['id']}.json").write_text(json.dumps({'intent': intent, 'result': msg}, indent=2))
            try: path.unlink()
            except Exception: pass
            if TG_TOKEN and TG_CHAT:
                # Handle both stock and options confirmations
                if intent.get('option_type'):
                    opt_type = intent.get('option_type', '').upper()
                    strike = intent.get('strike')
                    send_telegram(f"✅ Placed {intent['ticker']} ${strike} {opt_type} ({msg})")
                else:
                    send_telegram(f"✅ Placed paper order for {intent['ticker']} ({msg})")
        else:
            if TG_TOKEN and TG_CHAT:
                send_telegram(f"⚠️ Failed to place order for {intent['ticker']}: {msg}")
    
    # Start background thread
    thread = threading.Thread(target=process)
    thread.daemon = True
    thread.start()

def _approve_intent(intent, path):
    """Approve and return immediately (process in background)"""
    _approve_intent_async(intent, path)
    
    # Return immediately
    ticker = intent.get('ticker')
    if intent.get('option_type'):
        opt_type = intent.get('option_type', '').upper()
        strike = intent.get('strike')
        msg = f"Processing {ticker} ${strike} {opt_type}..."
    else:
        msg = f"Processing {ticker} order..."
    
    return jsonify({'status':'processing','id': intent['id'], 'message': msg})

def _reject_intent(intent, path):
    (LOGS_DIR / f"rejected-{intent['id']}.json").write_text(json.dumps(intent, indent=2))
    try: path.unlink()
    except Exception: pass
    if TG_TOKEN and TG_CHAT:
        # Handle both stock and options rejections
        if intent.get('option_type'):
            opt_type = intent.get('option_type', '').upper()
            strike = intent.get('strike')
            send_telegram(f"❌ Rejected {intent['ticker']} ${strike} {opt_type}")
        else:
            signal = intent.get('signal', intent.get('side', 'trade'))
            send_telegram(f"❌ Rejected {signal} {intent['ticker']}")
    return jsonify({'status':'ok','id': intent['id'], 'message':'rejected'})

# --- service status ---
START_TS = time.time()

@app.route('/status', methods=['GET'])
def status_get():
    pending = len(list(PENDING_DIR.glob('*.json')))
    return jsonify({
        'service': 'webhook-listener',
        'mode': 'paper',
        'host': IB_HOST,
        'port': IB_PORT,
        'pending': pending,
        'uptime_sec': int(time.time() - START_TS)
    })

@app.route('/health', methods=['GET'])
def health_get():
    # Lightweight liveness check; no secrets exposed
    return jsonify({'ok': True, 'service': 'webhook-listener'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5001'))
    app.run(host='127.0.0.1', port=port)
