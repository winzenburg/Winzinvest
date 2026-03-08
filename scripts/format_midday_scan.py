#!/usr/bin/env python3
import re, sys
from collections import OrderedDict
try:
    import yfinance as yf
except Exception:
    print("ERR: Missing yfinance", file=sys.stderr)
    sys.exit(1)

lines = [l.strip() for l in sys.stdin if l.strip()]
# Extract tickers
tickers = []
for l in lines:
    m = re.match(r"^([A-Z]+): ", l)
    if m:
        tickers.append(m.group(1))

# Unique preserve order
seen = set()
uniq = [t for t in tickers if not (t in seen or seen.add(t))]

prices = {}
if uniq:
    # Fetch last price using fast_info when possible; fallback to last intraday close
    for t in uniq:
        try:
            ti = yf.Ticker(t)
            p = getattr(ti, 'fast_info', None)
            last = None
            if p and 'last_price' in p:
                last = float(p['last_price'])
            if not last:
                df = yf.download(t, period='1d', interval='1m', progress=False, prepost=False)
                if df is not None and not df.empty:
                    if isinstance(df.columns, tuple) or hasattr(df.columns, 'levels'):
                        try:
                            df = df.xs(t, axis=1, level=1)
                        except Exception:
                            pass
                    last = float(df['Close'].iloc[-1])
            if last:
                prices[t] = last
        except Exception:
            continue

# Format output: [TICKER] @ $XX.XX - [key level/pattern/signal]
for l in lines:
    m = re.match(r"^([A-Z]+): (.+?) \| (.+?) \| (.+)$", l)
    if not m:
        continue
    t, level, pattern, action = m.groups()
    price = prices.get(t)
    price_str = f"${price:.2f}" if price else "$?"
    # Key: combine level + pattern, keep concise
    key = f"{level} — {pattern}"
    print(f"[{t}] @ {price_str} - {key}")
