#!/usr/bin/env python3
"""
TradingView webhook server — receive alerts, validate, then queue or trigger execution.

- POST /webhook/tradingview: body = { symbol?, action?, secret?, trigger? }
  - If secret != TV_WEBHOOK_SECRET: 401
  - If trigger == "run": validate (no symbol required), then spawn execute_dual_mode
  - Else: validate signal (symbol + action), then spawn execute_webhook_signal
- Uses TV_WEBHOOK_SECRET from env (or .env) so only your alerts are accepted.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

# Optional: load .env
def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        for p in [Path.cwd() / ".env", Path.home() / ".cursor" / ".env.local"]:
            if p.exists():
                env_path = p
                break
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if k and v and os.environ.get(k) is None:
                        os.environ[k] = v
        except OSError:
            pass


def get_webhook_secret() -> Optional[str]:
    """TV_WEBHOOK_SECRET from environment."""
    return os.environ.get("TV_WEBHOOK_SECRET") or os.environ.get("WEBHOOK_SECRET")


def get_scripts_dir() -> Path:
    """trading/scripts directory (where execute_webhook_signal.py and execute_dual_mode.py live)."""
    return Path(__file__).resolve().parent.parent


def load_portfolio_shorts() -> Set[str]:
    """Load current short symbols from workspace file (no IB)."""
    try:
        from agents._paths import TRADING_DIR
        from position_filter import load_current_short_symbols
        return load_current_short_symbols(TRADING_DIR, ib=None)
    except Exception as e:
        logger.warning("Could not load portfolio shorts: %s", e)
        return set()


def load_portfolio_longs() -> Set[str]:
    """Load current long symbols if a file exists; otherwise empty."""
    try:
        from agents._paths import TRADING_DIR
        path = TRADING_DIR / "current_long_symbols.json"
        if not path.exists():
            return set()
        data = json.loads(path.read_text())
        if isinstance(data, dict) and isinstance(data.get("symbols"), list):
            return {str(s).strip().upper() for s in data["symbols"] if s}
        return set()
    except Exception:
        return set()


try:
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    FastAPI = None  # type: ignore
    Request = None  # type: ignore
    Response = None  # type: ignore
    JSONResponse = None  # type: ignore

if HAS_FASTAPI:
    _load_env()
    app = FastAPI(title="TradingView webhook", version="0.1.0")

    @app.post("/webhook/tradingview")
    async def webhook_tradingview(request: Request) -> Any:
        """
        Accept TradingView alert JSON.
        Body: { "symbol": "AAPL", "action": "sell", "secret": "<TV_WEBHOOK_SECRET>" }
        Or:   { "trigger": "run", "secret": "<TV_WEBHOOK_SECRET>" } to run full pipeline.
        """
        secret = get_webhook_secret()
        if secret is None or secret == "":
            return JSONResponse(
                status_code=503,
                content={"ok": False, "reason": "TV_WEBHOOK_SECRET not configured"},
            )
        try:
            body = await request.json()
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "reason": f"Invalid JSON: {e}"},
            )
        if not isinstance(body, dict):
            return JSONResponse(status_code=400, content={"ok": False, "reason": "Body must be JSON object"})

        trigger = (body.get("trigger") or "").strip().lower()
        if trigger == "run":
            if body.get("secret") != secret:
                return JSONResponse(status_code=401, content={"ok": False, "reason": "invalid or missing secret"})
            scripts_dir = get_scripts_dir()
            proc = subprocess.Popen(
                [sys.executable, "execute_dual_mode.py"],
                cwd=str(scripts_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(),
            )
            return JSONResponse(
                status_code=202,
                content={
                    "ok": True,
                    "reason": "triggered",
                    "message": "execute_dual_mode started",
                    "pid": proc.pid,
                },
            )

        # Handle pullback entry type (1H pullback alert from TradingView)
        entry_type = (body.get("entry_type") or "").strip().lower()
        if entry_type == "pullback":
            if body.get("secret") != secret:
                return JSONResponse(status_code=401, content={"ok": False, "reason": "invalid secret"})
            symbol = (body.get("symbol") or "").strip().upper()
            if not symbol:
                return JSONResponse(status_code=400, content={"ok": False, "reason": "missing symbol"})
            logger.info("Pullback entry alert received: %s", symbol)
            scripts_dir = get_scripts_dir()
            pullback_payload = json.dumps({
                "symbol": symbol,
                "entry_type": "pullback",
                "action": body.get("action", "BUY"),
                "price": body.get("price"),
                "timeframe": body.get("timeframe", "1H"),
            })
            proc = subprocess.Popen(
                [sys.executable, "execute_webhook_signal.py", pullback_payload],
                cwd=str(scripts_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(),
            )
            return JSONResponse(
                status_code=202,
                content={
                    "ok": True,
                    "reason": "pullback_accepted",
                    "message": f"Pullback entry for {symbol} queued",
                    "pid": proc.pid,
                },
            )

        from agents.signal_validator import validate_and_record_last
        portfolio_shorts = load_portfolio_shorts()
        portfolio_longs = load_portfolio_longs()
        allowed, reason = validate_and_record_last(
            body,
            secret=secret,
            portfolio_shorts=portfolio_shorts,
            portfolio_longs=portfolio_longs,
            check_market_hours=True,
            check_dedup=True,
        )
        if not allowed:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "reason": reason},
            )

        scripts_dir = get_scripts_dir()
        payload_json = json.dumps(body)
        proc = subprocess.Popen(
            [sys.executable, "execute_webhook_signal.py", payload_json],
            cwd=str(scripts_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
        )
        return JSONResponse(
            status_code=202,
            content={
                "ok": True,
                "reason": "accepted",
                "message": "execute_webhook_signal started",
                "pid": proc.pid,
            },
        )

    @app.get("/webhook/health")
    def webhook_health() -> Any:
        return JSONResponse({"ok": True, "service": "webhook"})

    @app.get("/candidates/pullback")
    def get_pullback_candidates() -> Any:
        """Return current MTF pullback candidates for TradingView monitoring.

        The daily screener exports candidates to mtf_pullback_candidates.json.
        TradingView (or any client) can poll this endpoint to know which symbols
        to monitor for 1H pullback entries.
        """
        try:
            from paths import TRADING_DIR
            workspace = TRADING_DIR
            json_path = workspace / "tradingview_exports" / "mtf_pullback_candidates.json"
            if not json_path.exists():
                return JSONResponse(
                    status_code=200,
                    content={"ok": True, "total": 0, "candidates": [],
                             "message": "No candidates exported yet. Run export_tv_watchlist.py."},
                )
            data = json.loads(json_path.read_text())
            return JSONResponse(status_code=200, content={"ok": True, **data})
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": str(exc)},
            )

    @app.get("/candidates/symbols")
    def get_candidate_symbols() -> Any:
        """Return just the symbol list (comma-separated) for quick reference."""
        try:
            from paths import TRADING_DIR
            workspace = TRADING_DIR
            txt_path = workspace / "tradingview_exports" / "mtf_pullback_candidates.txt"
            if not txt_path.exists():
                return JSONResponse(
                    status_code=200,
                    content={"ok": True, "symbols": [], "total": 0},
                )
            lines = [ln.strip() for ln in txt_path.read_text().splitlines() if ln.strip()]
            return JSONResponse(
                status_code=200,
                content={"ok": True, "symbols": lines, "total": len(lines)},
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": str(exc)},
            )
else:
    app = None


def main() -> None:
    """Run webhook server (requires FastAPI and uvicorn)."""
    _load_env()
    if not HAS_FASTAPI:
        print("Install: pip install fastapi uvicorn")
        sys.exit(1)
    import uvicorn
    host = os.environ.get("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.environ.get("WEBHOOK_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
