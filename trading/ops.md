# Ops Cheatsheet (Local)

Prereqs (one‑time):
- pip install --upgrade yfinance pandas flask jsonschema

Screeners (print + CSV only)
- Conservative: 
  python3 trading/scripts/conservative_screener.py '["AAPL","MSFT","JNJ","PG","XOM","CVX"]'
- Trend:
  python3 trading/scripts/trend_screener.py '["NVDA","AMD","SMCI","DELL","PLTR","TSLA"]'
- Box:
  python3 trading/scripts/box_screener.py '["AFRM","UPST","COIN","HOOD","SOFI"]'

Validate alert payloads (schema quick check is inside webhook)
- Start listener (safe mode, no orders):
  export MOLT_WEBHOOK_SECRET=changeme
  python3 trading/scripts/webhook_listener.py
- Test POST (example):
  curl -s -X POST http://127.0.0.1:5001/webhook \
    -H 'Content-Type: application/json' \
    -d '{"secret":"changeme","ticker":"AAPL","timeframe":"15m","signal":"entry","price":186.2}'

Notes
- IBKR wiring is intentionally disabled in this stub. We will introduce paper trading via confirm‑to‑execute once rules/risk are finalized.
- For OpenClaw routing, cron wrappers already dispatch cheap compute to Gemini Flash for scans; coordinator remains Sonnet.
