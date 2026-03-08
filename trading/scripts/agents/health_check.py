#!/usr/bin/env python3
"""
Health Check Agent — HTTP endpoint for system status.

Reports: IBKR connection state, last signal received, open orders, current positions,
risk utilization, kill switch status. Run with: uvicorn agents.health_check:app --host 0.0.0.0 --port 8000
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from agents._paths import KILL_SWITCH_FILE, LAST_SIGNAL_FILE, TRADING_DIR
from agents.risk_monitor import is_kill_switch_active

PORTFOLIO_JSON = TRADING_DIR / "portfolio.json"

# Optional FastAPI
try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def _get_last_signal() -> Optional[Dict[str, Any]]:
    if not LAST_SIGNAL_FILE.exists():
        return None
    try:
        return json.loads(LAST_SIGNAL_FILE.read_text())
    except (OSError, ValueError):
        return None


def _get_portfolio_summary() -> Dict[str, Any]:
    if not PORTFOLIO_JSON.exists():
        return {}
    try:
        data = json.loads(PORTFOLIO_JSON.read_text())
        return data.get("summary") or {}
    except (OSError, ValueError):
        return {}


def get_health_status(ib: Optional[Any] = None) -> Dict[str, Any]:
    """
    Build health status dict. If ib is None, connection and live orders/positions are omitted.
    """
    status: Dict[str, Any] = {
        "kill_switch_active": is_kill_switch_active(),
        "last_signal": _get_last_signal(),
        "portfolio_summary": _get_portfolio_summary(),
    }
    if ib is not None:
        try:
            status["ib_connected"] = ib.isConnected()
            if ib.isConnected():
                try:
                    open_trades = ib.openTrades()
                    status["open_orders_count"] = len(open_trades)
                except Exception:
                    status["open_orders_count"] = None
                try:
                    positions = ib.positions()
                    status["positions_count"] = len(positions)
                except Exception:
                    status["positions_count"] = None
            else:
                status["open_orders_count"] = None
                status["positions_count"] = None
        except Exception as e:
            status["ib_connected"] = False
            status["ib_error"] = str(e)
    else:
        status["ib_connected"] = None
        status["open_orders_count"] = None
        status["positions_count"] = None
    return status


if HAS_FASTAPI:
    app = FastAPI(title="Trading system health", version="0.1.0")
    _ib_ref: Optional[Any] = None

    def set_ib(ib: Any) -> None:
        global _ib_ref
        _ib_ref = ib

    @app.get("/health")
    def health() -> Any:
        return JSONResponse(get_health_status(_ib_ref))

    @app.get("/status")
    def status() -> Any:
        return JSONResponse(get_health_status(_ib_ref))
else:
    app = None


def main() -> None:
    """Run health check server (requires FastAPI and uvicorn)."""
    if not HAS_FASTAPI:
        print("Install fastapi and uvicorn to run the health server: pip install fastapi uvicorn")
        return
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
