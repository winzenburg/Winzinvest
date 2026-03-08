#!/usr/bin/env python3
"""
Execute filtered premium signals (highest quality only).
"""

import json
from pathlib import Path
import logging
import requests
from datetime import datetime

LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "premium_executor_filtered.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WEBHOOK_URL = "http://127.0.0.1:5001/webhook"

def execute_filtered():
    signals_file = Path.home() / ".openclaw" / "workspace" / "trading" / "premium_signals_filtered.json"
    
    with open(signals_file, "r") as f:
        data = json.load(f)
    
    signals = data.get("signals", [])
    logger.info(f"=== EXECUTING {len(signals)} HIGH-QUALITY PREMIUM SIGNALS ===")
    
    execution_results = []
    
    for signal in signals:
        try:
            payload = {
                "action": "SELL_TO_OPEN",
                "symbol": signal["symbol"],
                "type": "OPTION",
                "option_type": "PUT" if signal["type"] == "SELL_PUT" else "CALL",
                "strike": signal["strike"],
                "dte": signal["dte"],
                "quantity": signal["contracts"],
                "order_type": "MARKET",
                "expected_premium": signal["premium_pct"],
                "regime": signal["regime"],
                "vix": signal["vix"],
                "notes": signal["notes"],
            }
            
            logger.info(f"→ {signal['type']}: {signal['symbol']} ${signal['strike']} @ {signal['premium_pct']:.2f}%")
            
            response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
            
            if response.status_code in [200, 202]:
                logger.info(f"✓ ACCEPTED: {signal['symbol']}")
                execution_results.append({
                    "symbol": signal["symbol"],
                    "type": signal["type"],
                    "status": "ACCEPTED",
                    "premium": signal["premium_pct"],
                })
            else:
                logger.warning(f"✗ REJECTED ({response.status_code}): {signal['symbol']}")
                execution_results.append({
                    "symbol": signal["symbol"],
                    "type": signal["type"],
                    "status": "REJECTED",
                    "error": response.text,
                })
        except Exception as e:
            logger.error(f"✗ ERROR: {signal['symbol']} - {e}")
            execution_results.append({
                "symbol": signal["symbol"],
                "type": signal["type"],
                "status": "ERROR",
                "error": str(e),
            })
    
    # Summary
    accepted = len([r for r in execution_results if r["status"] == "ACCEPTED"])
    rejected = len([r for r in execution_results if r["status"] == "REJECTED"])
    errors = len([r for r in execution_results if r["status"] == "ERROR"])
    
    logger.info(f"=== EXECUTION COMPLETE ===")
    logger.info(f"Accepted: {accepted} | Rejected: {rejected} | Errors: {errors}")
    
    # Save results
    results_file = Path.home() / ".openclaw" / "workspace" / "trading" / "premium_execution_results.json"
    with open(results_file, "w") as f:
        json.dump({
            "execution_time": datetime.now().isoformat(),
            "total": len(execution_results),
            "accepted": accepted,
            "rejected": rejected,
            "errors": errors,
            "results": execution_results,
        }, f, indent=2)
    
    logger.info(f"Results saved to {results_file}")

if __name__ == "__main__":
    execute_filtered()
