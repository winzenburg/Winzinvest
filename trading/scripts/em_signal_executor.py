#!/usr/bin/env python3
"""
EM Signal Executor — Auto-Execute EM Screener Candidates to IBKR

This script is called by nx_screener_enhanced_em.py to immediately execute passing EM ETF candidates.

Integration:
- Reads watchlist_enhanced_em.json (EM screener output)
- Converts passing candidates to webhook signals
- Sends to webhook listener for IBKR execution
- Uses EM-specific position sizing (0.5x default = risk-controlled)

Execution Model:
- LONG candidates: Market order, size = 0.5x production size
- SHORT candidates: Market order, size = 0.5x production size
- Position sizing conservative (experimental thresholds)

Safety:
- All signals go through webhook_listener filter pipeline
- Circuit breaker respects VIX regime
- Stop loss manager enforces EM-specific stops
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
import logging
from typing import Optional
from paths import TRADING_DIR, LOGS_DIR, WORKSPACE

# Setup logging
LOG_DIR = LOGS_DIR
LOG_FILE = LOG_DIR / "em_signal_executor.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WORKSPACE_DIR = WORKSPACE
EM_WATCHLIST_FILE = TRADING_DIR / "watchlist_enhanced_em.json"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://127.0.0.1:5001/webhook")


def _webhook_secret() -> Optional[str]:
    """Non-empty secret required; matches MOLT_WEBHOOK_SECRET on webhook_listener."""
    for key in ("MOLT_WEBHOOK_SECRET", "TV_WEBHOOK_SECRET"):
        raw = os.getenv(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None

# EM Position Sizing (conservative, 0.5x default)
EM_POSITION_SIZE_LONG = 100  # shares for long entries (adjust as needed)
EM_POSITION_SIZE_SHORT = 50   # shares for short entries (more conservative)

def load_em_watchlist():
    """Load EM screener output."""
    try:
        with open(EM_WATCHLIST_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load EM watchlist: {e}")
        return None

def send_webhook_signal(
    symbol: str,
    side: str,
    price,
    comp_score,
    rs,
    rvol,
    struct_q,
    *,
    webhook_secret: str,
) -> bool:
    """Send signal to webhook listener for execution."""
    # Determine position size based on side
    if side == 'long':
        qty = EM_POSITION_SIZE_LONG
        signal_type = 'long'
    else:
        qty = EM_POSITION_SIZE_SHORT
        signal_type = 'short'
    
    # Build webhook payload
    payload = {
        "secret": webhook_secret,
        'symbol': symbol,
        'side': signal_type,
        'entry': price,
        'source': 'em_screener',
        'quantity': qty,
        'rsPct': rs,
        'rvol': rvol,
        'notes': f"EM Screener Signal: comp={comp_score:.3f}, struct={struct_q:.3f}",
        'ts': datetime.now().isoformat()
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            WEBHOOK_URL,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            logger.info(f"Webhook response for {symbol}: {result}")
            # webhook_listener returns 'pending' (queued for approval) or 'processing'
            # (CANARY/FULL_AUTO — executed immediately). 'ok' means rejected.
            return result.get('status') in ('pending', 'processing')
    except Exception as e:
        logger.error(f"Failed to send webhook signal for {symbol}: {e}")
        return False

def execute_em_candidates():
    """Execute all passing EM candidates."""
    logger.info("=" * 80)
    logger.info("EM SIGNAL EXECUTOR - Processing EM Screener Output")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 80)

    secret = _webhook_secret()
    if not secret:
        logger.error(
            "Refusing to send webhooks: set MOLT_WEBHOOK_SECRET or TV_WEBHOOK_SECRET "
            "(must match webhook_listener) — no default secret"
        )
        return

    watchlist = load_em_watchlist()
    if not watchlist:
        logger.error("No EM watchlist data available")
        return
    
    long_candidates = watchlist.get('long_candidates', [])
    short_candidates = watchlist.get('short_candidates', [])
    
    executed_count = 0
    failed_count = 0
    
    # Process LONG candidates
    logger.info(f"Processing {len(long_candidates)} LONG candidates...")
    for candidate in long_candidates:
        symbol = candidate.get('symbol')
        price = candidate.get('price')
        comp_score = candidate.get('comp_score')
        rs = candidate.get('rs')
        rvol = candidate.get('rvol')
        struct_q = candidate.get('struct_q')
        
        logger.info(f"Executing LONG: {symbol} @ ${price}")
        if send_webhook_signal(
            symbol, "long", price, comp_score, rs, rvol, struct_q, webhook_secret=secret
        ):
            executed_count += 1
        else:
            failed_count += 1
    
    # Process SHORT candidates
    logger.info(f"Processing {len(short_candidates)} SHORT candidates...")
    for candidate in short_candidates:
        symbol = candidate.get('symbol')
        price = candidate.get('price')
        comp_score = candidate.get('comp_score')
        rs = candidate.get('rs')
        rvol = candidate.get('rvol')
        struct_q = candidate.get('struct_q')
        
        logger.info(f"Executing SHORT: {symbol} @ ${price}")
        if send_webhook_signal(
            symbol, "short", price, comp_score, rs, rvol, struct_q, webhook_secret=secret
        ):
            executed_count += 1
        else:
            failed_count += 1
    
    # Summary
    logger.info("=" * 80)
    logger.info(f"EXECUTION SUMMARY")
    logger.info(f"✅ Executed: {executed_count}")
    logger.info(f"❌ Failed: {failed_count}")
    logger.info(f"Total candidates: {len(long_candidates) + len(short_candidates)}")
    logger.info("=" * 80)

if __name__ == "__main__":
    execute_em_candidates()
