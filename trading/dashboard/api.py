#!/usr/bin/env python3
"""
Mission Control Dashboard API
Real-time trading system monitoring and control
"""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Body, Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("dashboard.api")

# Add scripts to path
TRADING_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TRADING_DIR / "scripts"))

try:
    from ib_insync import IB, util
except ImportError:
    IB = None

# --- API key for mutating endpoints ---
_DASHBOARD_API_KEY: Optional[str] = os.environ.get("DASHBOARD_API_KEY")
if not _DASHBOARD_API_KEY:
    _env_path = TRADING_DIR / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text().splitlines():
            if _line.startswith("DASHBOARD_API_KEY="):
                _DASHBOARD_API_KEY = _line.split("=", 1)[1].strip()
                break


def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Dependency that enforces API key on mutating endpoints.

    If DASHBOARD_API_KEY is not configured, all requests are allowed (open mode).
    """
    if _DASHBOARD_API_KEY and x_api_key != _DASHBOARD_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


app = FastAPI(title="Mission Control Dashboard")

# CORS — restrict to localhost and LAN
_allowed_origins = [
    "http://localhost:8002",
    "http://127.0.0.1:8002",
]
_extra_origin = os.environ.get("DASHBOARD_CORS_ORIGIN")
if _extra_origin:
    _allowed_origins.append(_extra_origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections for live updates
active_connections: List[WebSocket] = []


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def load_json(file_path: Path, default: Any = None) -> Any:
    """Load JSON file with fallback."""
    try:
        if file_path.exists():
            return json.loads(file_path.read_text())
    except Exception as exc:
        logger.warning("Failed to load %s: %s", file_path.name, exc)
    return default if default is not None else {}


REGIME_CONTEXT_FILE = TRADING_DIR / "logs" / "regime_context.json"

_REGIME_CONTEXT_DEFAULTS: Dict[str, Any] = {
    "regime": None,
    "note": "",
    "catalysts": [],
    "updated_at": None,
}


def get_regime_context() -> Dict[str, Any]:
    """Load regime context (note, catalysts, regime) from regime_context.json. Returns defaults if missing or invalid."""
    data = load_json(REGIME_CONTEXT_FILE, _REGIME_CONTEXT_DEFAULTS)
    if not isinstance(data, dict):
        return dict(_REGIME_CONTEXT_DEFAULTS)
    return {
        "regime": data.get("regime") if data.get("regime") is not None else _REGIME_CONTEXT_DEFAULTS["regime"],
        "note": data.get("note") if isinstance(data.get("note"), str) else _REGIME_CONTEXT_DEFAULTS["note"],
        "catalysts": data.get("catalysts") if isinstance(data.get("catalysts"), list) else _REGIME_CONTEXT_DEFAULTS["catalysts"],
        "updated_at": data.get("updated_at") if data.get("updated_at") is not None else _REGIME_CONTEXT_DEFAULTS["updated_at"],
    }


def _validate_catalyst(item: Any) -> bool:
    """Return True if item is a dict with date and event (note optional)."""
    if not isinstance(item, dict):
        return False
    date_val = item.get("date")
    event_val = item.get("event")
    return isinstance(date_val, str) and isinstance(event_val, str) and len(date_val) > 0 and len(event_val) > 0


def write_regime_context(
    note: Optional[str] = None,
    catalysts: Optional[List[Dict[str, str]]] = None,
    regime: Optional[str] = None,
    merge: bool = True,
) -> Dict[str, Any]:
    """Write regime context to disk. If merge=True, only provided fields overwrite existing; otherwise replace all. Returns new context."""
    current = get_regime_context() if merge else dict(_REGIME_CONTEXT_DEFAULTS)
    if note is not None:
        current["note"] = str(note)
    if catalysts is not None:
        current["catalysts"] = [c for c in catalysts if _validate_catalyst(c)]
    if regime is not None:
        current["regime"] = str(regime).strip() or None
    current["updated_at"] = datetime.now().isoformat()
    REGIME_CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REGIME_CONTEXT_FILE.write_text(json.dumps(current, indent=2))
    return current


def get_service_status() -> Dict[str, Any]:
    """Check status of all services."""
    pids_dir = TRADING_DIR / ".pids"
    
    services = {
        "webhook": {"name": "Webhook Server", "port": 8001},
        "agents": {"name": "Background Agents", "port": None},
        "scheduler": {"name": "Job Scheduler", "port": None},
    }
    
    status = {}
    for service, info in services.items():
        pid_file = pids_dir / f"{service}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                # Check if process is running
                import os
                import signal
                try:
                    os.kill(pid, 0)
                    status[service] = {"running": True, "pid": pid, "name": info["name"]}
                except OSError:
                    status[service] = {"running": False, "pid": None, "name": info["name"]}
            except Exception:
                status[service] = {"running": False, "pid": None, "name": info["name"]}
        else:
            status[service] = {"running": False, "pid": None, "name": info["name"]}
    
    # Check IB Gateway — port from .env (live=4001, paper=4002)
    _ib_host = os.getenv("IB_HOST", "127.0.0.1")
    _ib_port = int(os.getenv("IB_PORT", "4001"))
    ib_status = {"running": False, "connected": False}
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((_ib_host, _ib_port))
        sock.close()
        ib_status["running"] = result == 0
    except Exception:
        pass

    status["ib_gateway"] = {
        "running": ib_status["running"],
        "name": "IB Gateway",
        "host": f"{_ib_host}:{_ib_port}",
    }
    
    return status


def get_kill_switch_status() -> Dict[str, Any]:
    """Get kill switch status."""
    kill_switch_file = TRADING_DIR / "kill_switch.json"
    data = load_json(kill_switch_file, {"active": False})
    return {
        "active": data.get("active", False),
        "reason": data.get("reason", ""),
        "timestamp": data.get("timestamp", ""),
    }


def _portfolio_from_cache() -> Optional[Dict[str, Any]]:
    """Load portfolio from cached files (portfolio.json or dashboard_snapshot.json). Returns None if no cache."""
    # 1. Prefer portfolio.json (from portfolio_snapshot.py – all position types)
    portfolio_file = TRADING_DIR / "portfolio.json"
    if portfolio_file.exists():
        data = load_json(portfolio_file)
        if data and "summary" in data and "positions" in data:
            s = data["summary"]
            positions = []
            for p in data.get("positions") or []:
                positions.append({
                    "symbol": p.get("symbol", ""),
                    "type": p.get("secType", "STK"),
                    "position": p.get("position", 0),
                    "market_price": p.get("marketPrice", 0) or 0,
                    "market_value": p.get("marketValue", 0) or 0,
                    "avg_cost": p.get("averageCost", 0) or 0,
                    "unrealized_pnl": p.get("unrealizedPNL", 0) or 0,
                    "realized_pnl": p.get("realizedPNL", 0) or 0,
                })
            total_pnl = sum(float(p.get("unrealizedPNL", 0) or 0) for p in data.get("positions") or [])
            return {
                "account_value": float(s["net_liquidation"]) if s.get("net_liquidation") is not None else (float(s.get("short_notional") or 0) + float(s.get("long_notional") or 0)),
                "cash": float(s.get("total_cash_value") or 0),
                "positions_count": len(positions),
                "total_pnl": round(total_pnl, 2),
                "daily_pnl": 0.0,
                "positions": positions,
                "_source": "portfolio.json",
                "timestamp": data.get("timestamp"),
            }

    # 2. Fall back to dashboard_snapshot.json (from dashboard_data_aggregator.py)
    snapshot_file = TRADING_DIR / "logs" / "dashboard_snapshot.json"
    if snapshot_file.exists():
        data = load_json(snapshot_file)
        if data and "account" in data and "positions" in data:
            acc = data["account"]
            pos_data = data["positions"]
            plist = pos_data.get("list") or []
            positions = []
            for p in plist:
                qty = p.get("quantity", p.get("position", 0))
                positions.append({
                    "symbol": p.get("symbol", ""),
                    "type": p.get("secType", p.get("type", "STK")),
                    "position": qty,
                    "market_price": p.get("market_price", 0) or 0,
                    "market_value": p.get("market_value", 0) or 0,
                    "avg_cost": p.get("avg_cost", 0) or 0,
                    "unrealized_pnl": p.get("unrealized_pnl", 0) or 0,
                    "realized_pnl": p.get("realized_pnl", 0) or 0,
                })
            return {
                "account_value": float(acc.get("net_liquidation") or 0),
                "cash": float(acc.get("total_cash") or 0),
                "positions_count": len(positions),
                "total_pnl": sum((p.get("unrealized_pnl") or 0) for p in plist),
                "daily_pnl": 0.0,
                "positions": positions,
                "_source": "dashboard_snapshot.json",
                "timestamp": data.get("timestamp"),
            }
    return None


def _apply_daily_pnl_from_log(summary: Dict[str, Any]) -> None:
    """Overlay daily_pnl using the most up-to-date equity source available.

    Priority:
    1. portfolio.json NLV — most current (written every 5 min by portfolio_snapshot)
    2. daily_loss.json current_equity — fallback if portfolio.json is missing/older
    3. summary account_value — last resort
    SOD equity always comes from daily_loss.json (authoritative start-of-day baseline).
    """
    daily_loss_file = TRADING_DIR / "logs" / "daily_loss.json"
    if not daily_loss_file.exists():
        return
    try:
        loss_data = json.loads(daily_loss_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(loss_data, dict):
        return
    sod = loss_data.get("sod_equity")
    if sod is None:
        return
    try:
        sod_f = float(sod)
    except (TypeError, ValueError):
        return

    summary["sod_equity"] = round(sod_f, 2)

    # Prefer portfolio.json NLV when it is newer than daily_loss.json
    portfolio_nlv: Optional[float] = None
    portfolio_file = TRADING_DIR / "portfolio.json"
    if portfolio_file.exists() and daily_loss_file.exists():
        try:
            if portfolio_file.stat().st_mtime >= daily_loss_file.stat().st_mtime:
                pdata = json.loads(portfolio_file.read_text(encoding="utf-8"))
                nlv = (pdata.get("summary") or {}).get("net_liquidation")
                if nlv is not None:
                    portfolio_nlv = float(nlv)
        except (OSError, ValueError, TypeError):
            pass

    if portfolio_nlv is not None and portfolio_nlv > 0:
        summary["daily_pnl"] = round(portfolio_nlv - sod_f, 2)
        # Also update account_value to reflect latest snapshot
        summary["account_value"] = round(portfolio_nlv, 2)
        return

    # Fallback: use current_equity from daily_loss.json
    current = loss_data.get("current_equity")
    if current is not None:
        try:
            summary["daily_pnl"] = round(float(current) - sod_f, 2)
            return
        except (TypeError, ValueError):
            pass

    # Last resort: use whatever account_value was in the summary
    account_value = summary.get("account_value") or 0.0
    try:
        summary["daily_pnl"] = round(float(account_value) - sod_f, 2)
    except (TypeError, ValueError):
        pass


def get_portfolio_summary(ib: Optional[Any] = None) -> Dict[str, Any]:
    """Get portfolio summary from IB, then cached data (portfolio.json / dashboard_snapshot.json), then dummy."""
    summary = {
        "account_value": 0.0,
        "cash": 0.0,
        "positions_count": 0,
        "total_pnl": 0.0,
        "daily_pnl": 0.0,
        "positions": [],
    }

    # When no live IB: use cached real data if available, else dummy
    if ib is None or not IB:
        cached = _portfolio_from_cache()
        if cached:
            result = {k: v for k, v in cached.items() if k != "_source"}
            # Overlay daily P&L from logs/daily_loss.json (sod_equity vs current account_value) so it updates
            _apply_daily_pnl_from_log(result)
            return result
        return summary
    
    try:
        # Account value
        for av in ib.accountValues():
            if av.tag == "NetLiquidation" and av.currency == "USD":
                summary["account_value"] = float(av.value)
            elif av.tag == "TotalCashValue" and av.currency == "USD":
                summary["cash"] = float(av.value)
            elif av.tag == "UnrealizedPnL" and av.currency == "USD":
                summary["total_pnl"] = float(av.value)
            elif av.tag == "DailyPnL" and av.currency == "USD":
                summary["daily_pnl"] = float(av.value)
        
        # Positions
        positions = []
        for item in ib.portfolio():
            contract = item.contract
            positions.append({
                "symbol": contract.symbol,
                "type": contract.secType,
                "position": item.position,
                "market_price": item.marketPrice,
                "market_value": item.marketValue,
                "avg_cost": item.averageCost,
                "unrealized_pnl": item.unrealizedPNL,
                "realized_pnl": item.realizedPNL,
            })
        
        summary["positions"] = positions
        summary["positions_count"] = len(positions)
        
    except Exception as e:
        logger.error("Error fetching portfolio: %s", e)
    
    return summary


def get_risk_metrics() -> Dict[str, Any]:
    """Get current risk metrics."""
    logs_dir = TRADING_DIR / "logs"

    daily_loss_data = load_json(logs_dir / "daily_loss.json", {})
    sod_equity = float(daily_loss_data.get("sod_equity") or 0)
    current_equity = float(daily_loss_data.get("current_equity") or 0)

    # Compute actual loss from equity difference (positive = loss, negative = gain)
    daily_loss = max(0.0, sod_equity - current_equity) if sod_equity > 0 else 0.0

    # Read daily loss limit pct from risk_config (respects risk.live.json override)
    try:
        from risk_config import get_daily_loss_limit_pct
        _daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)
    except Exception:
        _daily_loss_limit_pct = 0.015
    daily_limit = sod_equity * _daily_loss_limit_pct if sod_equity > 0 else 0.0

    peak_data = load_json(logs_dir / "peak_equity.json", {})
    peak_equity = float(peak_data.get("peak_equity") or 0)
    drawdown_pct = 0.0
    if peak_equity > 0 and current_equity > 0:
        drawdown_pct = (peak_equity - current_equity) / peak_equity * 100

    # Read max drawdown pct from risk_config (respects risk.live.json override)
    try:
        from risk_config import get_max_drawdown_pct
        max_dd = get_max_drawdown_pct(TRADING_DIR) * 100
    except Exception:
        risk_cfg = load_json(TRADING_DIR / "risk.json", {})
        max_dd = float(risk_cfg.get("portfolio", {}).get("max_drawdown_pct", 0.1)) * 100

    return {
        "daily_loss": round(daily_loss, 2),
        "daily_limit": round(daily_limit, 2),
        "daily_loss_limit_pct": round(_daily_loss_limit_pct * 100, 2),
        "daily_loss_pct": round((daily_loss / daily_limit * 100), 2) if daily_limit > 0 else 0,
        "peak_equity": round(peak_equity, 2),
        "current_equity": round(current_equity, 2),
        "drawdown_pct": round(drawdown_pct, 4),
        "max_drawdown_pct": round(max_dd, 2),
    }


def get_screener_results() -> Dict[str, Any]:
    """Get latest screener results."""
    results = {}
    
    # Longs
    longs_file = TRADING_DIR / "watchlist_longs.json"
    longs_data = load_json(longs_file, {})
    long_candidates = longs_data.get("long_candidates", [])
    results["longs"] = {
        "count": len(long_candidates),
        "candidates": long_candidates[:10] if isinstance(long_candidates, list) else [],
    }
    
    # Multimode (shorts + premium)
    multimode_file = TRADING_DIR / "watchlist_multimode.json"
    multimode_data = load_json(multimode_file, {})
    modes = multimode_data.get("modes", {})
    
    # Use explicit None checks so an intentional empty list [] isn't skipped
    shorts = multimode_data.get("shorts")
    if shorts is None:
        shorts = multimode_data.get("short_candidates")
    if shorts is None:
        shorts = modes.get("short_opportunities", {}).get("short", [])

    premium = multimode_data.get("premium_selling")
    if premium is None:
        premium = multimode_data.get("premium_candidates")
    if premium is None:
        premium = modes.get("premium_selling", {}).get("short", [])
    
    results["shorts"] = {
        "count": len(shorts),
        "candidates": shorts[:10] if isinstance(shorts, list) else [],
    }
    
    results["premium"] = {
        "count": len(premium),
        "candidates": premium[:10] if isinstance(premium, list) else [],
    }
    
    # Mean reversion
    mr_file = TRADING_DIR / "watchlist_mean_reversion.json"
    mr_data = load_json(mr_file, {})
    mr_candidates = mr_data.get("candidates", [])
    results["mean_reversion"] = {
        "count": len(mr_candidates),
        "candidates": mr_candidates[:10] if isinstance(mr_candidates, list) else [],
    }
    
    # Pairs
    pairs_file = TRADING_DIR / "watchlist_pairs.json"
    pairs_data = load_json(pairs_file, {})
    pairs_candidates = pairs_data.get("pairs", [])
    results["pairs"] = {
        "count": len(pairs_candidates),
        "candidates": pairs_candidates[:10] if isinstance(pairs_candidates, list) else [],
    }
    
    return results


import re as _re

_SAFE_SERVICE_NAME = _re.compile(r"^[a-zA-Z0-9_-]+$")


def get_recent_logs(service: str = "webhook", lines: int = 50) -> List[str]:
    """Get recent log entries (path-traversal safe)."""
    if not _SAFE_SERVICE_NAME.match(service):
        return []
    log_file = TRADING_DIR / "logs" / f"{service}.log"
    if not log_file.exists():
        return []

    try:
        from collections import deque

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            return [line.strip() for line in deque(f, maxlen=lines)]
    except Exception:
        return []


def _get_daily_pnl_from_log() -> Optional[float]:
    """Read today's realised P&L (current_equity - sod_equity) from daily_loss.json."""
    try:
        daily_file = TRADING_DIR / "logs" / "daily_loss.json"
        if not daily_file.exists():
            return None
        data = json.loads(daily_file.read_text(encoding="utf-8"))
        current = data.get("current_equity")
        sod = data.get("sod_equity")
        if current is not None and sod is not None and sod > 0:
            return round(float(current) - float(sod), 2)
    except Exception:
        pass
    return None


def _get_unrealized_pnl_from_portfolio() -> Optional[float]:
    """Sum unrealizedPNL across all open positions from portfolio.json."""
    try:
        portfolio_file = TRADING_DIR / "portfolio.json"
        if not portfolio_file.exists():
            return None
        pf = json.loads(portfolio_file.read_text(encoding="utf-8"))
        positions = pf.get("positions", [])
        if isinstance(positions, list):
            return round(sum(float(p.get("unrealizedPNL", 0) or 0) for p in positions), 2)
    except Exception:
        pass
    return None


def get_performance_stats(since_days: int = 30) -> Dict[str, Any]:
    """Get performance statistics from trade log, enriched with live P&L."""
    import statistics as _stats

    daily_pnl = _get_daily_pnl_from_log()
    unrealized_pnl = _get_unrealized_pnl_from_portfolio()

    try:
        from trade_log_db import get_closed_trades

        trades = get_closed_trades(since_days=since_days if since_days > 0 else None)
        if not trades:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                # Show daily mark-to-market P&L so the tab isn't blank while positions are open
                "total_pnl": daily_pnl if daily_pnl is not None else 0.0,
                "unrealized_pnl": unrealized_pnl if unrealized_pnl is not None else 0.0,
                "daily_pnl": daily_pnl if daily_pnl is not None else 0.0,
                "sharpe": 0.0,
                "pnl_source": "daily_log",
            }

        wins = [t for t in trades if float(t.get("realized_pnl") or 0) > 0]
        losses = [t for t in trades if float(t.get("realized_pnl") or 0) < 0]

        total_pnl = sum(float(t.get("realized_pnl") or 0) for t in trades)
        avg_pnl = total_pnl / len(trades) if trades else 0
        win_rate = len(wins) / len(trades) * 100 if trades else 0

        # Sharpe ratio using % returns, annualised assuming ~252 trading days.
        # Requires at least 2 trades to compute a meaningful standard deviation.
        # Falls back to 0.0 rather than a garbage number when data is insufficient.
        pnl_pcts = [float(t.get("realized_pnl_pct") or 0) for t in trades]
        if len(pnl_pcts) >= 2:
            avg_r = _stats.mean(pnl_pcts)
            std_r = _stats.stdev(pnl_pcts)
            sharpe = round((avg_r / std_r * (252 ** 0.5)), 2) if std_r > 0 else 0.0
        else:
            sharpe = 0.0

        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "unrealized_pnl": unrealized_pnl if unrealized_pnl is not None else 0.0,
            "daily_pnl": daily_pnl if daily_pnl is not None else 0.0,
            "sharpe": sharpe,
            "pnl_source": "closed_trades",
        }
    except Exception as e:
        logger.error("Error fetching performance stats: %s", e)
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "total_pnl": daily_pnl if daily_pnl is not None else 0.0,
            "unrealized_pnl": unrealized_pnl if unrealized_pnl is not None else 0.0,
            "daily_pnl": daily_pnl if daily_pnl is not None else 0.0,
            "sharpe": 0.0,
            "pnl_source": "daily_log",
        }


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.get("/overview")
async def overview():
    """Serve the system overview page."""
    return FileResponse(Path(__file__).parent / "overview.html")


@app.get("/universe")
async def universe():
    """Serve the trading universe reference page."""
    return FileResponse(Path(__file__).parent / "universe.html")


@app.get("/")
async def root():
    """Serve the dashboard HTML."""
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/status")
async def get_status():
    """Get overall system status."""
    services = get_service_status()
    kill_switch = get_kill_switch_status()
    risk = get_risk_metrics()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "services": services,
        "kill_switch": kill_switch,
        "risk": risk,
        "healthy": not kill_switch["active"] and services["ib_gateway"]["running"],
    }


@app.get("/api/regime-context")
async def get_regime_context_endpoint():
    """Get regime context (regime label, market note, upcoming catalysts). For display in Mission Control."""
    return get_regime_context()


@app.post("/api/regime-context", dependencies=[Depends(require_api_key)])
async def post_regime_context_endpoint(body: Dict[str, Any] = Body(...)):
    """Update regime context (note, catalysts, optional regime). Requires API key. Merges with existing; only provided fields overwrite."""
    note = body.get("note")
    catalysts = body.get("catalysts")
    regime = body.get("regime")
    if note is None and catalysts is None and regime is None:
        raise HTTPException(status_code=400, detail="Provide at least one of: note, catalysts, regime")
    if note is not None and not isinstance(note, str):
        raise HTTPException(status_code=400, detail="note must be a string")
    if catalysts is not None:
        if not isinstance(catalysts, list):
            raise HTTPException(status_code=400, detail="catalysts must be an array")
        for i, c in enumerate(catalysts):
            if not _validate_catalyst(c):
                raise HTTPException(status_code=400, detail=f"catalysts[{i}] must be {{ date, event, note? }}")
    if regime is not None and not isinstance(regime, str):
        raise HTTPException(status_code=400, detail="regime must be a string")
    updated = write_regime_context(note=note, catalysts=catalysts, regime=regime, merge=True)
    return updated


@app.get("/api/portfolio")
async def get_portfolio():
    """Get portfolio summary from cache (portfolio.json / dashboard_snapshot.json). Use POST /api/portfolio/refresh to update from IB."""
    # Avoid connecting to IB from this async process: ib_insync conflicts with FastAPI's event loop and can crash the server.
    return get_portfolio_summary(None)


@app.post("/api/portfolio/refresh", dependencies=[Depends(require_api_key)])
async def refresh_portfolio_from_ib():
    """Pull latest positions and account from IBKR and update cache (portfolio.json + dashboard_snapshot.json)."""
    import subprocess
    scripts_dir = TRADING_DIR / "scripts"
    # Run from trading/ with "python3 scripts/..." so cwd and behavior match running manually.
    env = {"PYTHONPATH": str(scripts_dir), **__import__("os").environ}
    env_run = {**env, "PYTHONUNBUFFERED": "1"}
    cwd = str(TRADING_DIR)
    results = {}
    # 1. portfolio_snapshot.py → portfolio.json
    try:
        r = subprocess.run(
            [__import__("sys").executable, "-u", "scripts/portfolio_snapshot.py"],
            cwd=cwd,
            env=env_run,
            timeout=60,
            capture_output=True,
            text=True,
        )
        stderr = (r.stderr or "").strip()
        stdout = (r.stdout or "").strip()
        results["portfolio_snapshot"] = {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stderr": stderr[-500:] if stderr else None,
            "stdout": stdout[-500:] if stdout else None,
        }
    except Exception as e:
        results["portfolio_snapshot"] = {"ok": False, "error": str(e), "returncode": None}
    # 2. dashboard_data_aggregator.py → logs/dashboard_snapshot.json
    try:
        r = subprocess.run(
            [__import__("sys").executable, "-u", "scripts/dashboard_data_aggregator.py"],
            cwd=cwd,
            env=env_run,
            timeout=120,
            capture_output=True,
            text=True,
        )
        stderr = (r.stderr or "").strip()
        stdout = (r.stdout or "").strip()
        results["dashboard_aggregator"] = {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stderr": stderr[-500:] if stderr else None,
            "stdout": stdout[-500:] if stdout else None,
        }
    except Exception as e:
        results["dashboard_aggregator"] = {"ok": False, "error": str(e), "returncode": None}
    return {
        "success": results.get("portfolio_snapshot", {}).get("ok", False) or results.get("dashboard_aggregator", {}).get("ok", False),
        "results": results,
    }


def _load_executions_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load executions from JSONL file (one JSON object per line)."""
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    try:
        text = path.read_text()
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return out


def _is_options_trade(t: Dict[str, Any]) -> bool:
    """True if this execution record is options-related."""
    if t.get("type") == "OPTIONS":
        return True
    src = (t.get("source_script") or "").lower()
    if "option" in src or "premium" in src:
        return True
    if t.get("strategy") == "options":
        return True
    return False


def get_options_data() -> Dict[str, Any]:
    """Options positions (from portfolio.json only; dashboard_snapshot excludes OPT) and options trades."""
    options_positions: List[Dict[str, Any]] = []
    options_trades: List[Dict[str, Any]] = []
    summary = {"options_count": 0, "options_notional": 0.0, "trades_count": 0}
    debug: Dict[str, Any] = {}

    # Options positions only exist in portfolio.json (portfolio_snapshot). Try TRADING_DIR first, then cwd.
    portfolio_file = TRADING_DIR / "portfolio.json"
    if not portfolio_file.exists():
        import os
        cwd_file = Path(os.getcwd()) / "portfolio.json"
        if cwd_file.exists():
            portfolio_file = cwd_file
    debug["portfolio_path"] = str(portfolio_file)
    debug["portfolio_exists"] = portfolio_file.exists()

    if portfolio_file.exists():
        try:
            data = json.loads(portfolio_file.read_text(encoding="utf-8"))
        except Exception as e:
            data = None
            debug["load_error"] = str(e)
        positions_raw = data.get("positions") if data and isinstance(data, dict) else None
        debug["total_positions_in_file"] = len(positions_raw) if isinstance(positions_raw, list) else 0

        if data and isinstance(positions_raw, list):
            for p in positions_raw:
                ptype = (p.get("secType") or p.get("type") or "").strip().upper()
                if ptype == "OPT":
                    avg_cost = p.get("averageCost", p.get("avg_cost", 0)) or 0
                    unrealized = p.get("unrealizedPNL", p.get("unrealized_pnl", 0)) or 0
                    realized = p.get("realizedPNL", p.get("realized_pnl", 0)) or 0
                    options_positions.append({
                        "symbol": p.get("symbol", ""),
                        "description": p.get("description", "") or p.get("localSymbol", ""),
                        "position": p.get("position", 0),
                        "market_value": p.get("marketValue", p.get("market_value", 0)) or 0,
                        "market_price": p.get("marketPrice", p.get("market_price", 0)) or 0,
                        "avg_cost": avg_cost,
                        "unrealized_pnl": unrealized,
                        "realized_pnl": realized,
                    })
            summary["options_count"] = len(options_positions)
            summary["options_notional"] = round(sum(abs(p.get("market_value") or 0) for p in options_positions), 2)
        debug["options_filtered"] = len(options_positions)

    exec_path = TRADING_DIR / "logs" / "executions.json"
    all_exec = _load_executions_jsonl(exec_path)
    for t in all_exec:
        if _is_options_trade(t):
            options_trades.append(t)
    options_trades.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    options_trades = options_trades[:100]
    summary["trades_count"] = len(options_trades)

    for path, key in [
        (TRADING_DIR / "direct_execution_results.json", "executions"),
        (TRADING_DIR / "premium_execution_log.json", "executions"),
    ]:
        data = load_json(path)
        if not data or not isinstance(data, dict):
            continue
        entries = data.get(key)
        if isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict):
                    options_trades.append({**e, "_source": path.name})
    options_trades.sort(key=lambda x: x.get("timestamp") or x.get("execution_time") or "", reverse=True)
    options_trades = options_trades[:100]
    summary["trades_count"] = len(options_trades)

    return {
        "summary": summary,
        "options_positions": options_positions,
        "options_trades": options_trades,
    }


@app.get("/api/options")
async def get_options():
    """Options positions and options trades for the Options tab."""
    return get_options_data()


@app.get("/api/screeners")
async def get_screeners():
    """Get latest screener results."""
    return get_screener_results()


@app.get("/api/performance")
async def get_performance(days: int = 30):
    """Get performance statistics. Use ?days=7|30|90|0 (0=all-time)."""
    return get_performance_stats(since_days=days)


@app.get("/api/logs/list")
async def list_log_files():
    """Return available log file names (without extension) from logs/ directory."""
    logs_dir = TRADING_DIR / "logs"
    if not logs_dir.exists():
        return {"services": []}
    names = sorted(p.stem for p in logs_dir.glob("*.log"))
    return {"services": names}


@app.get("/api/logs/{service}")
async def get_logs(service: str, lines: int = 50):
    """Get recent logs for a service."""
    return {"service": service, "logs": get_recent_logs(service, lines)}


_ERROR_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[,\d]*\s.*?(ERROR|CRITICAL)[:\s]+(.+)",
)

# Benign or transient errors; loaded from config/ignored_errors.json with
# a 30-second file cache so the self-healer can add patterns at runtime
# without requiring an API restart.

_IGNORED_ERRORS_PATH = TRADING_DIR / "config" / "ignored_errors.json"
_ignored_cache: Dict[str, Any] = {"patterns": [], "ts": 0.0}
_IGNORED_CACHE_TTL = 30.0


def _load_ignored_patterns() -> list[str]:
    """Return the combined patterns + auto_added lists, cached for 30s."""
    now = __import__("time").time()
    if now - _ignored_cache["ts"] < _IGNORED_CACHE_TTL and _ignored_cache["patterns"]:
        return _ignored_cache["patterns"]
    try:
        if _IGNORED_ERRORS_PATH.exists():
            data = json.loads(_IGNORED_ERRORS_PATH.read_text())
            combined = list(data.get("patterns", [])) + list(data.get("auto_added", []))
        else:
            combined = []
    except Exception:
        combined = _ignored_cache["patterns"] or []
    _ignored_cache["patterns"] = combined
    _ignored_cache["ts"] = now
    return combined


def _is_ignored_error_message(message: str) -> bool:
    """True if this error is known benign (e.g. IB 162 with fallback)."""
    stripped = message.strip()
    if not stripped or stripped == "-":
        return True
    if stripped in ("yfinance:", "yfinance: "):
        return True
    return any(p in message for p in _load_ignored_patterns())


@app.get("/api/errors")
async def get_errors(minutes: int = 60):
    """Scan all log files in logs/ for ERROR/CRITICAL lines in the last `minutes`. Excludes known benign IB errors (e.g. 162)."""
    cutoff = datetime.now() - timedelta(minutes=minutes)
    errors: List[Dict[str, str]] = []
    logs_dir = TRADING_DIR / "logs"
    log_files = sorted(logs_dir.glob("*.log")) if logs_dir.exists() else []
    for log_path in log_files:
        service = log_path.stem
        try:
            tail = log_path.read_text(errors="replace").splitlines()[-200:]
        except Exception:
            continue
        for line in tail:
            m = _ERROR_RE.match(line)
            if not m:
                continue
            try:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                if ts < cutoff:
                    continue
            except ValueError:
                continue
            msg = m.group(3).strip()[:300]
            if _is_ignored_error_message(msg):
                continue
            errors.append({
                "timestamp": m.group(1),
                "service": service,
                "level": m.group(2),
                "message": msg,
            })
    errors.sort(key=lambda e: e["timestamp"], reverse=True)
    return {"errors": errors[:50]}


@app.get("/api/audit")
async def get_audit_trail(limit: int = 50):
    """Return recent entries from audit_trail.json (gate rejections + order events).

    audit_trail.json is a JSON array written by audit_logger.py.
    """
    audit_file = TRADING_DIR / "logs" / "audit_trail.json"
    entries: List[Dict[str, Any]] = []
    if audit_file.exists():
        try:
            raw = audit_file.read_text(errors="replace").strip()
            if not raw:
                return {"entries": []}
            data = json.loads(raw)
            if isinstance(data, list):
                raw_entries = data
            elif isinstance(data, dict):
                # Wrapped format: {"entries": [...]}
                raw_entries = data.get("entries", [data])
            else:
                raw_entries = []
            for obj in raw_entries:
                if not isinstance(obj, dict):
                    continue
                # Normalise to the shape the frontend table expects
                failed = obj.get("failed_gates") or []
                reason = (
                    obj.get("reason")
                    or obj.get("message")
                    or (", ".join(failed) if failed else "")
                    or obj.get("detail", "")
                )
                entries.append({
                    "timestamp": obj.get("timestamp", ""),
                    "symbol": obj.get("symbol") or obj.get("ticker") or "—",
                    "event": obj.get("event_type") or obj.get("event") or obj.get("gate") or obj.get("action") or "—",
                    "reason": reason[:300],
                    "_raw": obj,
                })
        except Exception as exc:
            logger.warning("Failed to read audit_trail.json: %s", exc)
    # Most recent first
    entries.reverse()
    return {"entries": entries[:limit]}


@app.get("/api/performance/history")
async def get_performance_history():
    """Return daily equity snapshot + cumulative closed P&L from trades.db.

    sod_equity.json holds only today's snapshot (single object), so the equity
    series is anchored there.  The P&L curve is built from all closed trades in
    trades.db grouped by exit date.
    """
    # --- equity series from sod_equity_history.jsonl (real daily snapshots) ---
    equity_series: List[Dict[str, Any]] = []
    history_file = TRADING_DIR / "logs" / "sod_equity_history.jsonl"
    if history_file.exists():
        try:
            for line in history_file.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and "date" in obj and "equity" in obj:
                        equity_series.append({"date": obj["date"], "equity": float(obj["equity"])})
                except (json.JSONDecodeError, ValueError):
                    continue
        except Exception as exc:
            logger.warning("Failed to read sod_equity_history.jsonl: %s", exc)

    # Fallback: if no history yet, use today's snapshot from sod_equity.json
    if not equity_series:
        sod_file = TRADING_DIR / "logs" / "sod_equity.json"
        if sod_file.exists():
            try:
                obj = json.loads(sod_file.read_text(errors="replace"))
                if isinstance(obj, dict) and "equity" in obj:
                    equity_series.append({
                        "date": obj.get("date", datetime.now().date().isoformat()),
                        "equity": float(obj["equity"]),
                    })
            except Exception:
                pass

    equity_series.sort(key=lambda x: x["date"])

    # --- cumulative P&L from closed trades (all-time) ---
    cumulative_pnl: List[Dict[str, Any]] = []
    try:
        from trade_log_db import get_closed_trades
        trades = get_closed_trades(since_days=None)
        pnl_by_date: Dict[str, float] = {}
        for t in trades:
            d = (t.get("exit_timestamp") or "")[:10]
            if d:
                pnl_by_date[d] = pnl_by_date.get(d, 0.0) + float(t.get("realized_pnl") or 0)
        running = 0.0
        for d, pnl in sorted(pnl_by_date.items()):
            running += pnl
            cumulative_pnl.append({"date": d, "cumulative_pnl": round(running, 2)})
    except Exception:
        pass

    return {"equity_series": equity_series[-252:], "cumulative_pnl": cumulative_pnl[-252:]}


def _attribution_from_db() -> Dict[str, Any]:
    """Build a basic strategy attribution directly from trades.db (all trades, open + closed).

    Returns a dict keyed by source_script with trade_count, closed_count, open_count,
    and P&L metrics for closed trades when available.
    """
    import sqlite3
    db_path = TRADING_DIR / "logs" / "trades.db"
    if not db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC").fetchall()
        conn.close()
    except Exception:
        return {}

    try:
        groups: Dict[str, List[Any]] = {}
        for row in rows:
            src = str(row["source_script"] or "unknown").replace(".py", "")
            groups.setdefault(src, []).append(dict(row))

        result: Dict[str, Any] = {}
        for src, trades in groups.items():
            closed = [t for t in trades if t.get("exit_price") is not None]
            open_trades = [t for t in trades if t.get("exit_price") is None]
            entry: Dict[str, Any] = {
                "trade_count": len(trades),
                "closed_count": len(closed),
                "open_count": len(open_trades),
            }
            if closed:
                wins = [t for t in closed if float(t.get("realized_pnl") or 0) > 0]
                entry["win_rate"] = round(len(wins) / len(closed), 4)
                total_pnl = sum(float(t.get("realized_pnl") or 0) for t in closed)
                entry["total_pnl"] = round(total_pnl, 2)
                pnls = [float(t.get("realized_pnl") or 0) for t in closed]
                entry["avg_pnl"] = round(sum(pnls) / len(pnls), 2)
                gross_wins = sum(p for p in pnls if p > 0)
                gross_losses = abs(sum(p for p in pnls if p < 0))
                entry["profit_factor"] = round(gross_wins / gross_losses, 2) if gross_losses > 0 else None
                pnl_pcts = [float(t.get("realized_pnl_pct") or 0) for t in closed]
                mean_r = sum(pnl_pcts) / len(pnl_pcts)
                if len(pnl_pcts) > 1:
                    import math
                    std_r = math.sqrt(sum((r - mean_r) ** 2 for r in pnl_pcts) / (len(pnl_pcts) - 1))
                    # Annualised (~252 trading days), consistent with get_performance_stats
                    entry["sharpe"] = round(mean_r / std_r * math.sqrt(252), 4) if std_r > 0 else 0.0
                else:
                    entry["sharpe"] = 0.0
                r_mults = [float(t["r_multiple"]) for t in closed if t.get("r_multiple") is not None]
                entry["expectancy_r"] = round(sum(r_mults) / len(r_mults), 4) if r_mults else None
            result[src] = entry
        return result
    except Exception as e:
        logger.error("Error building attribution from DB: %s", e)
        return {}


@app.get("/api/performance/by-source")
async def get_performance_by_source():
    """Return strategy performance breakdown by source_script.

    Priority: (1) analytics/strategy_scorecard.json if available,
    (2) direct read from trades.db (all trades, open + closed).
    """
    scorecard_path = TRADING_DIR / "analytics" / "strategy_scorecard.json"
    if scorecard_path.exists():
        try:
            data = json.loads(scorecard_path.read_text(errors="replace"))
            by_source = data.get("by_source_script", {})
            if by_source:
                return {"by_source_script": by_source, "source": "scorecard"}
        except Exception as exc:
            logger.warning("Failed to read scorecard for by-source: %s", exc)

    # Fall back to live DB read
    by_source = _attribution_from_db()
    has_closed = any(v.get("closed_count", 0) > 0 for v in by_source.values())
    return {
        "by_source_script": by_source,
        "source": "live_db",
        "has_closed_trades": has_closed,
        "note": "P&L metrics available once positions close. Showing all trades (open + closed)." if not has_closed else None,
    }


@app.post("/api/kill-switch/activate", dependencies=[Depends(require_api_key)])
async def activate_kill_switch(reason: str = "manual activation from dashboard"):
    """Activate the kill switch to halt all new trade entries."""
    kill_switch_file = TRADING_DIR / "kill_switch.json"
    try:
        kill_switch_file.write_text(
            json.dumps(
                {
                    "active": True,
                    "timestamp": datetime.now().isoformat(),
                    "reason": reason,
                }
            )
        )
        logger.warning("Kill switch ACTIVATED via dashboard: %s", reason)
        try:
            from notifications import notify_critical
            notify_critical("Kill Switch Activated", f"Manual activation from dashboard.\nReason: {reason}")
        except Exception:
            pass
        return {"success": True, "message": "Kill switch activated"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/kill-switch/clear", dependencies=[Depends(require_api_key)])
async def clear_kill_switch():
    """Clear the kill switch."""
    kill_switch_file = TRADING_DIR / "kill_switch.json"
    try:
        kill_switch_file.write_text(
            json.dumps(
                {
                    "active": False,
                    "timestamp": datetime.now().isoformat(),
                    "reason": "manual clear from dashboard",
                }
            )
        )
        return {"success": True, "message": "Kill switch cleared"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/eod-analysis")
async def get_eod_analysis(date: Optional[str] = None):
    """Return the latest (or date-specific) end-of-day analysis report."""
    logs_dir = TRADING_DIR / "logs"
    if date:
        path = logs_dir / f"eod_analysis_{date}.json"
    else:
        path = logs_dir / "eod_analysis_latest.json"

    if not path.exists():
        return {"available": False, "message": "No EOD analysis available yet."}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"available": True, **data}
    except Exception as e:
        return {"available": False, "message": str(e)}


@app.get("/api/eod-analysis/history")
async def get_eod_analysis_history(days: int = 30):
    """Return health scores and gap counts for the last N days."""
    logs_dir = TRADING_DIR / "logs"
    history: List[Dict[str, Any]] = []
    for i in range(days):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        path = logs_dir / f"eod_analysis_{d}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                history.append({
                    "date": d,
                    "health_score": data.get("health_score"),
                    "gap_count": data.get("gap_count"),
                    "trade_count": data.get("trade_activity", {}).get("today", {}).get("new_entries"),
                    "daily_pnl_pct": data.get("daily_pnl", {}).get("pnl_pct"),
                })
            except Exception:
                continue
    return {"history": history}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for live updates."""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Send updates every 2 seconds
            await asyncio.sleep(2)
            
            data = {
                "type": "update",
                "timestamp": datetime.now().isoformat(),
                "status": await get_status(),
            }
            
            await websocket.send_json(data)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
        if websocket in active_connections:
            active_connections.remove(websocket)


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Run the dashboard server."""
    print("\n🚀 Mission Control Dashboard starting on http://localhost:8002\n")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")


if __name__ == "__main__":
    main()
