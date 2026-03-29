#!/usr/bin/env python3
"""
Winzinvest Dashboard API - Full Backend Service

Serves all dashboard data via HTTP API for remote access (Vercel).
Replaces filesystem reads with API calls when deployed to VPS.

Endpoints:
  /health - System health check
  /api/dashboard - Full dashboard snapshot
  /api/public-performance - Public performance metrics
  /api/alerts - System alerts and risk warnings
  /api/journal - Trade journal (closed and open trades)
  /api/audit - Audit trail of gate rejections and system events
  /api/screeners - Latest screener results
  /api/strategy-attribution - Strategy performance breakdown

Usage:
  uvicorn agents.dashboard_api:app --host 0.0.0.0 --port 8000
  
  Or with systemd:
    /etc/systemd/system/trading-api.service
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Path resolution
TRADING_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = TRADING_DIR / "logs"
CONFIG_DIR = TRADING_DIR / "config"

# Load .env for API key and other config
_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

API_KEY = os.getenv("DASHBOARD_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Lifespan event handler for startup/shutdown
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info("Winzinvest Dashboard API started")
    logger.info("Trading directory: %s", TRADING_DIR)
    logger.info("API key auth: %s", "enabled" if API_KEY else "disabled (open access)")
    yield

# Create FastAPI app with lifespan
app = FastAPI(
    title="Winzinvest Dashboard API",
    description="Trading system backend for winzinvest.com dashboard",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.winzinvest.com",
        "https://winzinvest.com",
        "http://localhost:3000",  # Local dev
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)


# ── Authentication ───────────────────────────────────────────────────────────


async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from request header. Skip if API_KEY not configured."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ── Helper Functions ─────────────────────────────────────────────────────────


def load_json_safe(file_path: Path) -> Any:
    """Load JSON file safely, return None if missing or invalid."""
    try:
        if file_path.exists():
            return json.loads(file_path.read_text())
    except (OSError, ValueError) as e:
        logger.warning("Failed to load %s: %s", file_path, e)
    return None


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    """Health check - no auth required."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "winzinvest-dashboard-api",
    }


@app.get("/api/dashboard")
async def get_dashboard(
    mode: Optional[str] = Query(None),
    x_api_key: str = Header(None),
):
    """
    Full dashboard snapshot - requires API key.
    Returns all metrics, positions, performance, regime, etc.
    """
    await verify_api_key(x_api_key)
    
    # Determine which snapshot file to read
    if mode:
        snapshot_path = LOGS_DIR / f"dashboard_snapshot_{mode}.json"
    else:
        active_mode = os.getenv("TRADING_MODE", "live")
        snapshot_path = LOGS_DIR / f"dashboard_snapshot_{active_mode}.json"
        if not snapshot_path.exists():
            snapshot_path = LOGS_DIR / "dashboard_snapshot.json"
    
    data = load_json_safe(snapshot_path)
    if not data:
        return JSONResponse(
            {"error": "Dashboard snapshot unavailable"},
            status_code=503,
        )
    
    return data


@app.get("/api/public-performance")
def get_public_performance():
    """
    Public performance metrics - no auth required.
    Returns sanitized aggregate metrics only (no positions or account details).
    """
    snapshot_path = LOGS_DIR / "dashboard_snapshot.json"
    data = load_json_safe(snapshot_path)
    
    if not data:
        return JSONResponse(
            {"error": "Performance data unavailable"},
            status_code=503,
        )
    
    # Extract only public-safe metrics
    perf = data.get("performance", {})
    return {
        "last_updated": data.get("timestamp"),
        "portfolio": {
            "daily_pnl_pct": perf.get("daily_return_pct"),
        },
        "performance": {
            "total_return_pct": perf.get("total_return_pct"),
            "total_return_30d_pct": perf.get("total_return_30d_pct"),
            "portfolio_return_pct": perf.get("portfolio_return_pct"),
            "portfolio_return_since": perf.get("portfolio_return_since"),
            "sharpe_ratio": perf.get("sharpe_ratio"),
            "max_drawdown_pct": perf.get("max_drawdown_pct"),
            "daily_return_pct": perf.get("daily_return_pct"),
            "win_rate": perf.get("win_rate"),
            "profit_factor": perf.get("profit_factor"),
            "total_trades": perf.get("total_trades"),
        },
        "market_regime": data.get("market_regime", {}),
    }


@app.get("/api/snapshot")
async def get_snapshot(
    mode: Optional[str] = Query(None),
    x_api_key: str = Header(None),
):
    """Alias for /api/dashboard - used by lib/data-access.ts getSnapshot()."""
    return await get_dashboard(mode=mode, x_api_key=x_api_key)


@app.get("/api/alerts")
async def get_alerts(x_api_key: str = Header(None)):
    """
    System alerts - requires API key.
    Returns assignment risk, drawdown state, kill switch, macro events, news sentiment.
    """
    await verify_api_key(x_api_key)
    
    alerts: List[Dict[str, Any]] = []
    now = datetime.utcnow().isoformat()
    
    # Assignment risk alerts
    assign_data = load_json_safe(LOGS_DIR / "assignment_alerts_today.json")
    if assign_data and assign_data.get("date") == now[:10]:
        alerted = assign_data.get("alerted", {})
        itm_keys = [
            (k, level)
            for k, level in alerted.items()
            if level in ("ITM", "DEEP_ITM", "DIVIDEND")
        ]
        if itm_keys:
            symbols = list({k.split("_")[0] for k, _ in itm_keys})
            has_deep = any(level in ("DEEP_ITM", "DIVIDEND") for _, level in itm_keys)
            alerts.append({
                "id": "assignment-risk",
                "severity": "critical" if has_deep else "warning",
                "message": f"{len(symbols)} option(s) ITM — assignment risk: {', '.join(symbols)}",
                "timestamp": now,
                "category": "risk",
            })
    
    # Drawdown circuit breaker
    breaker = load_json_safe(LOGS_DIR / "drawdown_breaker_state.json")
    if breaker:
        tier = breaker.get("tier", 0)
        dd = breaker.get("drawdown_pct", 0)
        if tier >= 3:
            alerts.append({
                "id": "drawdown-breaker",
                "severity": "critical",
                "message": f"Drawdown breaker TIER 3 — kill switch activated ({dd:.1f}% daily loss)",
                "timestamp": breaker.get("last_checked", now),
                "category": "risk",
            })
        elif tier == 2:
            alerts.append({
                "id": "drawdown-breaker",
                "severity": "critical",
                "message": f"Drawdown breaker TIER 2 — all new entries HALTED ({dd:.1f}% daily loss)",
                "timestamp": breaker.get("last_checked", now),
                "category": "risk",
            })
        elif tier == 1:
            alerts.append({
                "id": "drawdown-breaker",
                "severity": "warning",
                "message": f"Drawdown breaker TIER 1 — position sizes reduced 50% ({dd:.1f}% daily loss)",
                "timestamp": breaker.get("last_checked", now),
                "category": "risk",
            })
    
    # Kill switch
    ks = load_json_safe(TRADING_DIR / "kill_switch.json")
    if ks and ks.get("active"):
        alerts.append({
            "id": "kill-switch",
            "severity": "critical",
            "message": f"Kill switch active: {ks.get('reason', 'Manual trigger')}",
            "timestamp": ks.get("timestamp", now),
            "category": "risk",
        })
    
    # Macro events
    macro_events = load_json_safe(CONFIG_DIR / "macro_events.json")
    if isinstance(macro_events, list):
        today = now[:10]
        for ev in macro_events:
            if not ev.get("active"):
                continue
            start = ev.get("start_date", "")
            end = ev.get("end_date", "")
            if start and today < start:
                continue
            if end and today > end:
                continue
            
            cap_info = ""
            if ev.get("sector_caps_override"):
                caps = [
                    f"{s} cap → {int(c * 100)}%"
                    for s, c in ev["sector_caps_override"].items()
                ]
                cap_info = f" — {', '.join(caps)}"
            
            alerts.append({
                "id": f"macro-event-{ev.get('id', '')}",
                "severity": "info",
                "message": f"Active macro event: {ev.get('event', '')}{cap_info}",
                "timestamp": now,
                "category": "macro",
            })
    
    # News sentiment
    news = load_json_safe(LOGS_DIR / "news_sentiment.json")
    if news:
        macro_sent = news.get("macro_sentiment")
        if isinstance(macro_sent, (int, float)) and macro_sent <= -0.5:
            alerts.append({
                "id": "news-macro-sentiment",
                "severity": "warning" if macro_sent <= -0.7 else "info",
                "message": f"Macro news sentiment {macro_sent:.3f} — {news.get('articles_analyzed', 0)} articles analyzed",
                "timestamp": news.get("timestamp", now),
                "category": "macro",
            })
    
    return alerts


@app.get("/api/journal")
async def get_journal(x_api_key: str = Header(None)):
    """Trade journal - requires API key."""
    await verify_api_key(x_api_key)
    
    journal_path = LOGS_DIR / "trades_journal.json"
    data = load_json_safe(journal_path)
    
    if not data:
        return {
            "closed": [],
            "open": [],
            "total_closed": 0,
            "total_open": 0,
            "error": "Journal not yet generated",
        }
    
    return data


@app.get("/api/audit")
async def get_audit(x_api_key: str = Header(None)):
    """Audit trail - requires API key."""
    await verify_api_key(x_api_key)
    
    audit_path = LOGS_DIR / "audit_trail.json"
    data = load_json_safe(audit_path)
    
    if not data:
        return []
    
    return data


@app.get("/api/screeners")
async def get_screeners(x_api_key: str = Header(None)):
    """Latest screener results - requires API key."""
    await verify_api_key(x_api_key)
    
    # Find most recent screener files
    screeners = {}
    
    # Long candidates
    long_files = sorted(LOGS_DIR.glob("long_candidates_*.json"), reverse=True)
    if long_files:
        screeners["longs"] = load_json_safe(long_files[0])
    
    # Short candidates
    short_files = sorted(LOGS_DIR.glob("short_candidates_*.json"), reverse=True)
    if short_files:
        screeners["shorts"] = load_json_safe(short_files[0])
    
    # Mean reversion
    mr_files = sorted(LOGS_DIR.glob("mr_candidates_*.json"), reverse=True)
    if mr_files:
        screeners["mean_reversion"] = load_json_safe(mr_files[0])
    
    # Pairs
    pairs_files = sorted(LOGS_DIR.glob("pairs_candidates_*.json"), reverse=True)
    if pairs_files:
        screeners["pairs"] = load_json_safe(pairs_files[0])
    
    # Episodic pivots
    ep_files = sorted(LOGS_DIR.glob("ep_candidates_*.json"), reverse=True)
    if ep_files:
        screeners["episodic_pivots"] = load_json_safe(ep_files[0])
    
    return screeners


@app.get("/api/strategy-attribution")
async def get_strategy_attribution(x_api_key: str = Header(None)):
    """Strategy performance attribution - requires API key."""
    await verify_api_key(x_api_key)
    
    # Find most recent attribution file
    attr_files = sorted(LOGS_DIR.glob("strategy_attribution_*.json"), reverse=True)
    
    if not attr_files:
        return {"error": "Attribution data not yet generated"}
    
    return load_json_safe(attr_files[0]) or {}


@app.get("/api/backtest-results")
async def get_backtest_results(x_api_key: str = Header(None)):
    """Backtest benchmark results - requires API key."""
    await verify_api_key(x_api_key)
    
    backtest_path = LOGS_DIR / "equity_backtest_benchmark.json"
    data = load_json_safe(backtest_path)
    
    if not data:
        return {"error": "Backtest results unavailable"}
    
    return data


@app.post("/api/kill-switch")
async def toggle_kill_switch(
    body: Dict[str, Any],
    x_api_key: str = Header(None),
):
    """Activate or deactivate kill switch - requires API key."""
    await verify_api_key(x_api_key)
    
    action = body.get("action")
    pin = body.get("pin")
    reason = body.get("reason", "Manual trigger via dashboard")
    
    # Verify PIN
    expected_pin = os.getenv("KILL_SWITCH_PIN")
    if not expected_pin or str(pin) != expected_pin:
        raise HTTPException(status_code=403, detail="Invalid PIN")
    
    ks_path = TRADING_DIR / "kill_switch.json"
    
    if action == "activate":
        ks_path.write_text(json.dumps({
            "active": True,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }, indent=2))
        
        logger.warning("KILL SWITCH ACTIVATED: %s", reason)
        return {"status": "activated", "reason": reason}
    
    elif action == "deactivate":
        ks_path.write_text(json.dumps({
            "active": False,
            "reason": "Deactivated via dashboard",
            "timestamp": datetime.utcnow().isoformat(),
        }, indent=2))
        
        logger.info("Kill switch deactivated")
        return {"status": "deactivated"}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@app.get("/api/system-status")
async def get_system_status(x_api_key: str = Header(None)):
    """System status summary - requires API key."""
    await verify_api_key(x_api_key)
    
    snapshot = load_json_safe(LOGS_DIR / "dashboard_snapshot.json")
    
    if not snapshot:
        return {"status": "offline", "message": "No recent snapshot"}
    
    # Check data freshness
    timestamp = snapshot.get("timestamp", "")
    if timestamp:
        try:
            snap_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            age_minutes = (datetime.utcnow() - snap_time).total_seconds() / 60
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning("Failed to parse snapshot timestamp: %s", e)
            age_minutes = 999
    else:
        age_minutes = 999
    
    health = snapshot.get("system_health", {})
    
    return {
        "status": health.get("status", "unknown"),
        "data_age_minutes": age_minutes,
        "ib_connected": health.get("ib_connected"),
        "last_updated": timestamp,
        "issues": health.get("issues", []),
    }


@app.get("/api/equity-history")
async def get_equity_history(x_api_key: str = Header(None)):
    """30-day equity curve - requires API key."""
    await verify_api_key(x_api_key)
    
    history_path = LOGS_DIR / "sod_equity_history.jsonl"
    
    if not history_path.exists():
        return []
    
    # Read last 30 lines
    try:
        with open(history_path, "r") as f:
            lines = f.readlines()
        
        history = []
        for line in lines[-30:]:
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # Skip malformed JSON lines
        
        return history
    except (OSError, IOError) as e:
        logger.warning("Failed to read equity history: %s", e)
        return []


@app.get("/api/analytics")
def get_analytics(x_api_key: str = Header(None)):
    """Trade analytics (closed trades analysis)."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    analytics_path = LOGS_DIR / "trade_analytics.json"
    if not analytics_path.exists():
        return {
            "generated_at": datetime.now().isoformat(),
            "note": "Analytics file not yet generated. Run trade_analytics.py to produce it.",
            "summary": {"total_closed": 0}
        }
    
    try:
        with open(analytics_path, "r") as f:
            return json.load(f)
    except (OSError, IOError, json.JSONDecodeError) as e:
        logger.warning("Failed to read analytics file: %s", e)
        return {
            "generated_at": datetime.now().isoformat(),
            "error": "Failed to read analytics file",
            "summary": {"total_closed": 0}
        }


@app.get("/api/strategy-attribution")
def get_strategy_attribution(x_api_key: str = Header(None)):
    """Strategy performance attribution (most recent report)."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Find most recent strategy_attribution_YYYYMMDD.json
    try:
        files = [f for f in os.listdir(LOGS_DIR) if f.startswith("strategy_attribution_") and f.endswith(".json")]
        if not files:
            return {"error": "No attribution report found. Run strategy_performance_report.py (or wait for Friday automated run)."}
        
        latest = sorted(files, reverse=True)[0]
        with open(LOGS_DIR / latest, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read strategy attribution: {e}")
        return {"error": "Failed to read attribution file"}


# ── Main ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        log_level="info",
    )
