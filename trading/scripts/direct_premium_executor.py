#!/usr/bin/env python3
"""
Direct Premium Executor
Executes premium selling signals directly via IBKR (not through webhook).
Uses ib_insync for direct API calls.
"""

import json
import os
from pathlib import Path
import logging
from datetime import datetime, date, timedelta
import time
from typing import List, Optional

from risk_config import get_max_options_per_day, get_max_options_per_month

# Try to import ib_insync
try:
    from ib_insync import IB, Contract, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("❌ ib_insync not installed. Install: pip install ib_insync")

from paths import TRADING_DIR as _TD

_env_path = _TD / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
LOG_DIR = _TD / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "direct_premium_executor.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Only send orders for strategies your account is approved for (e.g. Level 3: SELL_PUT).
ALLOWED_STRATEGIES = ["SELL_PUT", "SELL_CALL", "IRON_CONDOR", "PROTECTIVE_PUT"]

# DTE threshold: <= this use next Friday (weekly); > this use next month 3rd Friday (monthly).
DTE_WEEKLY_THRESHOLD = 14


def _next_friday() -> date:
    """Return the next Friday (if today is Friday, return next week's Friday)."""
    today = date.today()
    # 4 = Friday in weekday() (0=Mon, 4=Fri)
    days_ahead = (4 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # next Friday
    return today + timedelta(days=days_ahead)


def _next_monthly_expiration() -> date:
    """Return the third Friday of next month (listed monthly expiration)."""
    today = date.today()
    if today.month == 12:
        next_month = 1
        next_year = today.year + 1
    else:
        next_month = today.month + 1
        next_year = today.year
    third_week_start = date(next_year, next_month, 15)
    days_until_friday = (4 - third_week_start.weekday()) % 7
    third_friday = third_week_start + timedelta(days=days_until_friday)
    return third_friday


def _build_order_detail(trade) -> str:
    """Build a single string from orderStatus.status, whyHeld, and trade.log messages."""
    parts: List[str] = []
    try:
        parts.append(getattr(trade.orderStatus, "status", "") or "")
        why_held = getattr(trade.orderStatus, "whyHeld", "") or ""
        if why_held:
            parts.append(why_held)
        for entry in getattr(trade, "log", []) or []:
            msg = getattr(entry, "message", None)
            if msg:
                parts.append(str(msg))
    except Exception:
        pass
    return " | ".join(p for p in parts if p)


def _is_retryable_error(detail: str) -> bool:
    """
    Return False if the error is permanent (no point retrying).
    Skip retry on "No security definition", "Buying power", "Duplicate order", etc.
    """
    if not detail:
        return True
    d = detail.upper()
    if "NO SECURITY DEFINITION" in d or ("SECURITY DEFINITION" in d and "NOT FOUND" in d):
        return False
    if "BUYING POWER" in d or "INSUFFICIENT" in d and "FUND" in d:
        return False
    if "DUPLICATE" in d and "ORDER" in d:
        return False
    if "INVALID" in d and ("CONTRACT" in d or "STRIKE" in d or "EXPIR" in d):
        return False
    return True


class DirectPremiumExecutor:
    """Execute premium selling signals directly against IBKR."""

    def __init__(self):
        self.ib = None
        self.signals_file = _TD / "premium_signals_filtered.json"
        self.execution_log = []

        if IB_AVAILABLE:
            self.ib = IB()
        else:
            logger.error("ib_insync not available - cannot execute")

    def connect(self):
        """Connect to IB Gateway."""
        try:
            if not self.ib:
                logger.error("IB instance not initialized")
                return False
            self.ib.connect(os.getenv("IB_HOST", "127.0.0.1"), int(os.getenv("IB_PORT", "4001")), clientId=1)
            logger.info("✓ Connected to IB Gateway")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IB Gateway: {e}")
            return False

    def load_signals(self):
        """Load filtered premium signals."""
        try:
            with open(self.signals_file, "r") as f:
                data = json.load(f)
            return data.get("signals", [])
        except Exception as e:
            logger.error(f"Failed to load signals: {e}")
            return []

    def create_options_contract(self, signal) -> Optional[Contract]:
        """Create and qualify an options contract from a premium signal. Uses listed expirations (next Friday or next month 3rd Friday)."""
        if not IB_AVAILABLE or not self.ib or not self.ib.isConnected():
            return None
        try:
            symbol = signal["symbol"]
            strike = signal["strike"]
            dte = signal.get("dte", 30)
            option_type = "P" if signal["type"] == "SELL_PUT" else "C"

            if dte <= DTE_WEEKLY_THRESHOLD:
                exp_date = _next_friday()
            else:
                exp_date = _next_monthly_expiration()
            exp_str = exp_date.strftime("%Y%m%d")

            contract = Contract(
                symbol=symbol,
                secType="OPT",
                exchange="SMART",
                strike=float(strike),
                right=option_type,
                lastTradeDateOrContractMonth=exp_str,
                currency="USD"
            )
            qualified = self.ib.qualifyContracts(contract)
            if not qualified or len(qualified) == 0:
                logger.warning(f"Contract qualification failed for {symbol} {option_type} ${strike} {exp_str}")
                return None
            return qualified[0]
        except Exception as e:
            logger.error(f"Failed to create contract for {signal.get('symbol', '?')}: {e}")
            return None

    def _submit_one(self, contract, order) -> tuple:
        """
        Submit one order to IB. Returns (success: bool, detail: str | None, order_id: int | None, status: str).
        On success, detail is None and order_id/status are set. On failure, detail is the error message.
        """
        try:
            trade = self.ib.placeOrder(contract, order)
            time.sleep(0.5)
            detail = _build_order_detail(trade)
            status = getattr(trade.orderStatus, "status", "") or ""
            is_success = status in ["PendingSubmit", "Submitted", "PreSubmitted", "Filled"]
            order_id = getattr(trade.order, "orderId", None) if trade else None
            if is_success:
                return (True, None, order_id, status)
            return (False, detail or status, None, status)
        except Exception as e:
            return (False, str(e), None, "")

    def place_order(self, contract, signal):
        """Place a sell-to-open order (single attempt)."""
        if not self.ib or not self.ib.isConnected():
            logger.error("Not connected to IB Gateway")
            return False

        symbol = signal["symbol"]
        option_type = "PUT" if signal["type"] == "SELL_PUT" else "CALL"
        contracts = signal["contracts"]
        order = MarketOrder("SELL", contracts)
        logger.info(
            f"Placing order: SELL {contracts} {symbol} {option_type} ${signal['strike']} @ {signal.get('premium_pct', 0):.2f}%"
        )
        success, detail, order_id, status = self._submit_one(contract, order)
        return self._log_order_result(signal, success, detail, order_id, status)

    def place_order_with_retry(
        self,
        contract,
        signal,
        max_retries: int = 3,
        delay_sec: float = 2.0,
    ) -> bool:
        """
        Place order with retries. Skips retry on non-retryable errors
        (e.g. No security definition, Buying power, Duplicate order).
        """
        if not self.ib or not self.ib.isConnected():
            logger.error("Not connected to IB Gateway")
            return False

        symbol = signal["symbol"]
        option_type = "PUT" if signal["type"] == "SELL_PUT" else "CALL"
        contracts = signal["contracts"]
        order = MarketOrder("SELL", contracts)
        logger.info(
            f"Placing order (with retry): SELL {contracts} {symbol} {option_type} ${signal.get('strike')} @ {signal.get('premium_pct', 0):.2f}%"
        )
        for attempt in range(1, max_retries + 1):
            success, detail, order_id, status = self._submit_one(contract, order)
            if success:
                return self._log_order_result(signal, True, None, order_id, status)
            if not _is_retryable_error(detail or ""):
                logger.warning(f"Non-retryable error for {symbol}: {detail}")
                break
            if attempt < max_retries:
                logger.info(f"Attempt {attempt} failed for {symbol}, retrying in {delay_sec}s: {detail}")
                time.sleep(delay_sec)
        return self._log_order_result(signal, False, detail, None, "")

    def _log_order_result(
        self,
        signal: dict,
        success: bool,
        detail: Optional[str],
        order_id: Optional[int],
        status: str,
    ) -> bool:
        """Append one execution_log entry and return success."""
        symbol = signal["symbol"]
        contracts = signal.get("contracts", 0)
        if success:
            logger.info(f"✓ Order submitted: {symbol} - Order ID: {order_id} - Status: {status}")
            self.execution_log.append({
                "symbol": symbol,
                "type": signal["type"],
                "strike": signal.get("strike"),
                "contracts": contracts,
                "premium_pct": signal.get("premium_pct"),
                "status": "SUBMITTED",
                "order_id": order_id,
                "order_status": status or "Submitted",
                "order_detail": detail,
                "timestamp": datetime.now().isoformat(),
            })
            return True
        else:
            logger.warning(f"✗ Order failed: {symbol} - {detail}")
            self.execution_log.append({
                "symbol": symbol,
                "type": signal["type"],
                "strike": signal.get("strike"),
                "contracts": contracts,
                "premium_pct": signal.get("premium_pct"),
                "status": "FAILED" if detail else "ERROR",
                "error": detail or "",
                "rejection_detail": detail or "",
                "order_detail": detail,
                "timestamp": datetime.now().isoformat(),
            })
            return False

    def _count_options_executed(self) -> tuple:
        """Return (today_count, month_count) from direct_execution_results.json."""
        log_file = LOG_DIR.parent / "direct_execution_results.json"
        today = date.today()
        today_count = 0
        month_count = 0
        if not log_file.exists():
            return today_count, month_count
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
            executions = data.get("executions") or []
            for e in executions:
                if e.get("status") != "SUBMITTED":
                    continue
                ts = e.get("timestamp") or ""
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    d = dt.date()
                except (ValueError, TypeError):
                    continue
                if d == today:
                    today_count += 1
                if d.year == today.year and d.month == today.month:
                    month_count += 1
        except (OSError, ValueError, TypeError):
            pass
        return today_count, month_count

    def execute_all_signals(self, signals):
        """Execute all signals (only those in ALLOWED_STRATEGIES), capped by options daily/monthly limits."""
        allowed = [s for s in signals if s.get("type") in ALLOWED_STRATEGIES]
        skipped = len(signals) - len(allowed)
        if skipped > 0:
            logger.info(f"Skipped {skipped} signals: strategy not in ALLOWED_STRATEGIES {ALLOWED_STRATEGIES}")
            for s in signals:
                if s.get("type") not in ALLOWED_STRATEGIES:
                    self.execution_log.append({
                        "symbol": s.get("symbol", "?"),
                        "type": s.get("type", "?"),
                        "status": "SKIPPED",
                        "rejection_detail": "strategy not allowed",
                        "timestamp": datetime.now().isoformat(),
                    })

        _script_trading = Path(__file__).resolve().parents[1]
        trading_dir = _script_trading if (_script_trading / "risk.json").exists() else LOG_DIR.parent
        max_per_day = get_max_options_per_day(trading_dir)
        max_per_month = get_max_options_per_month(trading_dir)
        today_count, month_count = self._count_options_executed()
        remaining_daily = max(0, max_per_day - today_count)
        remaining_monthly = max(0, max_per_month - month_count)
        if remaining_daily <= 0:
            logger.warning("Would exceed max options per day; skipping all")
            for s in allowed:
                self.execution_log.append({
                    "symbol": s.get("symbol", "?"),
                    "type": s.get("type", "?"),
                    "status": "SKIPPED",
                    "rejection_detail": "would exceed max options per day",
                    "timestamp": datetime.now().isoformat(),
                })
            return 0, len(allowed)
        if remaining_monthly <= 0:
            logger.warning("Would exceed max options per month; skipping all")
            for s in allowed:
                self.execution_log.append({
                    "symbol": s.get("symbol", "?"),
                    "type": s.get("type", "?"),
                    "status": "SKIPPED",
                    "rejection_detail": "would exceed max options per month",
                    "timestamp": datetime.now().isoformat(),
                })
            return 0, len(allowed)
        to_run = allowed[: min(remaining_daily, remaining_monthly, len(allowed))]
        if len(to_run) < len(allowed):
            for s in allowed[len(to_run):]:
                self.execution_log.append({
                    "symbol": s.get("symbol", "?"),
                    "type": s.get("type", "?"),
                    "status": "SKIPPED",
                    "rejection_detail": "would exceed max options per day or per month",
                    "timestamp": datetime.now().isoformat(),
                })

        logger.info(f"=== EXECUTING {len(to_run)} PREMIUM SIGNALS (DIRECT IBKR) ===")

        successful = 0
        failed = 0
        for signal in to_run:
            contract = self.create_options_contract(signal)
            if contract:
                if self.place_order_with_retry(contract, signal, max_retries=3, delay_sec=2.0):
                    successful += 1
                else:
                    failed += 1
                time.sleep(0.2)
            else:
                failed += 1

        logger.info(f"Execution complete: {successful} successful, {failed} failed")
        return successful, failed

    def save_execution_log(self):
        """Save execution results."""
        log_file = _TD / "direct_execution_results.json"
        try:
            with open(log_file, "w") as f:
                json.dump({
                    "execution_time": datetime.now().isoformat(),
                    "total": len(self.execution_log),
                    "submitted": len([e for e in self.execution_log if e.get("status") == "SUBMITTED"]),
                    "failed": len([e for e in self.execution_log if e.get("status") == "FAILED"]),
                    "errors": len([e for e in self.execution_log if e.get("status") == "ERROR"]),
                    "skipped": len([e for e in self.execution_log if e.get("status") == "SKIPPED"]),
                    "executions": self.execution_log,
                }, f, indent=2)
            logger.info(f"Execution log saved to {log_file}")
        except Exception as e:
            logger.error(f"Failed to save execution log: {e}")

    def disconnect(self):
        """Disconnect from IB Gateway."""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
                logger.info("Disconnected from IB Gateway")
        except Exception as e:
            logger.warning(f"Error disconnecting: {e}")

    def run(self):
        """Execute signals."""
        logger.info("=== DIRECT PREMIUM EXECUTOR STARTED ===")

        if not IB_AVAILABLE:
            logger.error("ib_insync not available - cannot execute")
            return

        if not self.connect():
            logger.error("Failed to connect to IB Gateway")
            return

        try:
            signals = self.load_signals()
            if not signals:
                logger.info("No signals to execute")
                return

            logger.info(f"Loaded {len(signals)} signals for execution")
            self.execute_all_signals(signals)
            self.save_execution_log()
        finally:
            self.disconnect()

        logger.info("=== DIRECT PREMIUM EXECUTOR COMPLETE ===")


def main():
    executor = DirectPremiumExecutor()
    executor.run()


if __name__ == "__main__":
    main()
