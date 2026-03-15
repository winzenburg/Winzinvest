#!/usr/bin/env python3
"""
Reconnection Agent — monitors IBKR connection and handles reconnects with exponential backoff.

Logs every disconnect/reconnect. Order execution should be paused while disconnected
(executors naturally fail without a connection; this agent restores it).
"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default connection params (override via env or args in production)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4001
DEFAULT_CLIENT_ID = 107
MIN_BACKOFF_SEC = 2
MAX_BACKOFF_SEC = 300


async def run_reconnection_loop(
    ib: Any,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    client_id: int = DEFAULT_CLIENT_ID,
    check_interval_sec: int = 30,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Loop: check ib.isConnected(); if disconnected, reconnect with exponential backoff.
    Log every disconnect and reconnect.
    """
    backoff = MIN_BACKOFF_SEC
    was_connected = ib.isConnected()
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            connected = ib.isConnected()
            if was_connected and not connected:
                logger.warning("Reconnection agent: IB disconnected")
                was_connected = False
            if not connected:
                try:
                    try:
                        # Cancel any lingering account summary subscriptions before
                        # disconnecting — prevents Error 322 accumulation across reconnects
                        try:
                            ib.cancelAccountSummary()
                        except Exception:
                            pass
                        ib.disconnect()
                    except Exception:
                        pass
                    await asyncio.sleep(1)
                    await ib.connectAsync(host, port, clientId=client_id, timeout=60)
                    logger.info("Reconnection agent: IB reconnected")
                    was_connected = True
                    backoff = MIN_BACKOFF_SEC
                except Exception as e:
                    logger.warning("Reconnection agent: reconnect failed (backoff %ds): %s", backoff, e)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_SEC)
                    continue
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Reconnection agent error: %s", e)
        if stop_event is not None and stop_event.is_set():
            break
        await asyncio.sleep(check_interval_sec)


if __name__ == "__main__":
    import sys
    from ib_insync import IB

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    ib = IB()
    try:
        asyncio.run(run_reconnection_loop(ib, check_interval_sec=30))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error("Fatal: %s", e)
        sys.exit(1)
    finally:
        if ib.isConnected():
            ib.disconnect()
