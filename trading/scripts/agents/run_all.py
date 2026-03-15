#!/usr/bin/env python3
"""
Run Risk Monitor and Reconnection Agent in the background (shared IB connection).

Starts both agents as asyncio tasks. Use this for a single process that keeps
risk checks and reconnection running. Stop with Ctrl+C or SIGTERM.

  From project root (trading/scripts on PYTHONPATH):
    python -m agents.run_all

  Or from trading/scripts:
    python -m agents.run_all

  Optional env:
    IB_HOST=127.0.0.1  IB_PORT=4001  AGENTS_CLIENT_ID=150
    RISK_MONITOR_INTERVAL=60  RECONNECT_CHECK_INTERVAL=30
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_TRADING_DIR = Path(__file__).resolve().parents[2]
_env_path = _TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4001
# Use 150+ range to avoid conflicts with portfolio_snapshot (111-119) and executors
AGENTS_CLIENT_ID = 150


async def _run_agents() -> None:
    from ib_insync import IB
    from agents.risk_monitor import run_loop as risk_run_loop
    from agents.reconnection_agent import run_reconnection_loop
    from agents.trade_outcome_resolver import run_loop as outcome_run_loop

    stop = asyncio.Event()
    host = os.environ.get("IB_HOST", DEFAULT_HOST)
    port = int(os.environ.get("IB_PORT", str(DEFAULT_PORT)))
    client_id = int(os.environ.get("AGENTS_CLIENT_ID", str(AGENTS_CLIENT_ID)))
    risk_interval = int(os.environ.get("RISK_MONITOR_INTERVAL", "60"))
    reconnect_interval = int(os.environ.get("RECONNECT_CHECK_INTERVAL", "30"))
    outcome_interval = int(os.environ.get("OUTCOME_RESOLVER_INTERVAL", "1800"))

    def shutdown() -> None:
        logger.info("Shutdown requested; stopping agents")
        stop.set()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, shutdown)
        loop.add_signal_handler(signal.SIGTERM, shutdown)
    except NotImplementedError:
        pass

    client_ids_to_try = [client_id, 151, 152, 153, 154]
    ib = IB()
    connected = False
    used_cid = client_id
    for cid in client_ids_to_try:
        try:
            await ib.connectAsync(host, port, clientId=cid, timeout=90)
            logger.info("Agents connected to IB (clientId=%s)", cid)
            connected = True
            used_cid = cid
            break
        except (asyncio.TimeoutError, Exception) as e:
            if ib.isConnected():
                logger.warning(
                    "ClientId %s: initial sync timed out but TCP connected — proceeding anyway", cid
                )
                connected = True
                used_cid = cid
                break
            if ib.client and getattr(ib.client, '_socket', None):
                ib.disconnect()
            logger.warning("ClientId %s failed: %s, trying next...", cid, e)
    if not connected:
        logger.error("Failed to connect to IB with any client id in %s", client_ids_to_try)
        sys.exit(1)

    async def risk_with_stop() -> None:
        await risk_run_loop(ib, interval_sec=risk_interval, stop_event=stop)
        stop.set()

    try:
        await asyncio.gather(
            risk_with_stop(),
            run_reconnection_loop(ib, host=host, port=port, client_id=used_cid,
                                 check_interval_sec=reconnect_interval, stop_event=stop),
            outcome_run_loop(ib, interval_sec=outcome_interval, stop_event=stop),
        )
    except asyncio.CancelledError:
        pass
    finally:
        if ib.isConnected():
            ib.disconnect()
        logger.info("Agents stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    try:
        asyncio.run(_run_agents())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error("Fatal: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
