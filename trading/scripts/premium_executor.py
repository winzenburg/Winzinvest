#!/usr/bin/env python3
"""
Premium Seller Executor
Converts premium selling signals to IBKR orders.
Executes sell-to-open for puts and calls.
"""

import json
from pathlib import Path
import logging
from datetime import datetime
import requests

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "premium_executor.log"

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

class PremiumExecutor:
    """Execute premium selling signals via IBKR webhook."""
    
    def __init__(self):
        self.signals_file = Path.home() / ".openclaw" / "workspace" / "trading" / "premium_signals.json"
        self.execution_log = []
        
    def load_signals(self):
        """Load generated signals."""
        try:
            with open(self.signals_file, "r") as f:
                data = json.load(f)
            return data.get("signals", [])
        except Exception as e:
            logger.error(f"Failed to load signals: {e}")
            return []
    
    def create_webhook_payload(self, signal):
        """
        Convert premium signal to webhook payload format.
        For options, we need to specify contract type, strike, and action.
        """
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
            "timestamp": signal["timestamp"],
            "notes": signal["notes"],
        }
        return payload
    
    def execute_signal(self, signal):
        """Send signal to webhook for execution."""
        try:
            payload = self.create_webhook_payload(signal)
            
            # Log the execution attempt
            logger.info(f"Executing: {signal['type']} {signal['symbol']} ${signal['strike']} @ {signal['premium_pct']:.2f}%")
            
            # Send to webhook
            response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
            
            if response.status_code in [200, 202]:
                logger.info(f"✓ Signal accepted: {signal['symbol']}")
                self.execution_log.append({
                    "status": "ACCEPTED",
                    "signal": signal,
                    "timestamp": datetime.now().isoformat(),
                })
                return True
            else:
                logger.warning(f"Webhook returned {response.status_code}: {response.text}")
                self.execution_log.append({
                    "status": "REJECTED",
                    "signal": signal,
                    "error": response.text,
                    "timestamp": datetime.now().isoformat(),
                })
                return False
                
        except Exception as e:
            logger.error(f"Failed to execute {signal['symbol']}: {e}")
            self.execution_log.append({
                "status": "ERROR",
                "signal": signal,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            return False
    
    def execute_all_signals(self, signals):
        """Execute all signals."""
        logger.info(f"=== EXECUTING {len(signals)} PREMIUM SIGNALS ===")
        
        successful = 0
        failed = 0
        
        for signal in signals:
            if self.execute_signal(signal):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Execution complete: {successful} successful, {failed} failed")
        return successful, failed
    
    def save_execution_log(self):
        """Save execution results."""
        log_file = Path.home() / ".openclaw" / "workspace" / "trading" / "premium_execution_log.json"
        
        try:
            with open(log_file, "w") as f:
                json.dump({
                    "execution_time": datetime.now().isoformat(),
                    "total": len(self.execution_log),
                    "accepted": len([e for e in self.execution_log if e["status"] == "ACCEPTED"]),
                    "rejected": len([e for e in self.execution_log if e["status"] == "REJECTED"]),
                    "errors": len([e for e in self.execution_log if e["status"] == "ERROR"]),
                    "executions": self.execution_log,
                }, f, indent=2)
            logger.info(f"Execution log saved to {log_file}")
        except Exception as e:
            logger.error(f"Failed to save execution log: {e}")
    
    def run(self, auto_execute=False):
        """Load signals and optionally execute them."""
        logger.info("=== PREMIUM EXECUTOR STARTED ===")
        
        signals = self.load_signals()
        if not signals:
            logger.info("No signals to execute")
            return
        
        logger.info(f"Loaded {len(signals)} signals for execution")
        
        if auto_execute:
            self.execute_all_signals(signals)
            self.save_execution_log()
        else:
            logger.info("Auto-execution disabled. Review signals and run with --execute flag.")
            logger.info("Sample first signal:")
            logger.info(json.dumps(signals[0], indent=2))
        
        logger.info("=== PREMIUM EXECUTOR COMPLETE ===")

def main():
    import sys
    
    auto_execute = "--execute" in sys.argv
    
    executor = PremiumExecutor()
    executor.run(auto_execute=auto_execute)

if __name__ == "__main__":
    main()
