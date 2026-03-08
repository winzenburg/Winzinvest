#!/usr/bin/env python3
# Saved reference: Manus-provided webhook listener (v1.0 Phase 1)
# NOTE: Not executed. Used for diff/merge against our active listener.

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Third-party imports guarded; active runtime may not have them yet
try:
    from ib_insync import IB, Stock, LimitOrder, BracketOrder, MarketOrder, StopOrder  # type: ignore
except Exception:
    IB = None
try:
    import yfinance as yf  # type: ignore
    import pandas as pd    # type: ignore
except Exception:
    yf = None
    pd = None

# Load environment variables
load_dotenv()

# Configuration
WEBHOOK_SECRET = os.getenv('MOLT_WEBHOOK_SECRET', 'CHANGE_ME')
IB_HOST = os.getenv('IB_HOST', '127.0.0.1')
IB_PORT = int(os.getenv('IB_PORT', '7497'))
IB_CLIENT_ID = int(os.getenv('IB_CLIENT_ID', '101'))
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
SAFE_MODE = os.getenv('SAFE_MODE', 'true').lower() == 'true'

# Paths assume CWD; adjust to workspace/trading when merging
BASE_DIR = os.getcwd()

# Load risk configuration
RISK_CONFIG = {}
try:
    with open(os.path.join(BASE_DIR, 'risk.json'), 'r') as f:
        RISK_CONFIG = json.load(f)
except Exception:
    pass

# Load watchlist (note: package expects a flat list of {ticker}; our schema differs)
WATCHLIST = {}
try:
    with open(os.path.join(BASE_DIR, 'watchlist.json'), 'r') as f:
        WATCHLIST_CONFIG = json.load(f)
        # Package expected: { "watchlist": [ {"ticker": "AAPL"}, ... ] }
        if isinstance(WATCHLIST_CONFIG, dict) and 'watchlist' in WATCHLIST_CONFIG:
            WATCHLIST = {item['ticker']: item for item in WATCHLIST_CONFIG['watchlist']}
except Exception:
    pass

# Load feature flags
try:
    with open(os.path.join(BASE_DIR, 'feature_flags.json'), 'r') as f:
        FEATURE_FLAGS = json.load(f)
except FileNotFoundError:
    FEATURE_FLAGS = {
        "setups": {
            "trend_following": {"enabled": True},
            "box_strategy": {"enabled": True},
            "dividend_growth": {"enabled": True}
        }
    }

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, 'trades/webhook_listener.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# NOTE: The remainder of the business logic is unchanged from the provided script.
# Kept minimal here; we merge behavior deltas into our active listener separately.

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "reference-only"})

if __name__ == '__main__':
    logger.info('Reference-only module; use trading/scripts/webhook_listener.py for runtime')
