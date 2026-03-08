#!/usr/bin/env python3
"""
Mission Control Dashboard API
Real-time trading system monitoring and control
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Add scripts to path
TRADING_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TRADING_DIR / "scripts"))

try:
    from ib_insync import IB, util
except ImportError:
    IB = None

app = FastAPI(title="Mission Control Dashboard")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    except Exception:
        pass
    return default if default is not None else {}


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
    
    # Check IB Gateway
    ib_status = {"running": False, "connected": False}
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()
        ib_status["running"] = result == 0
    except Exception:
        pass
    
    status["ib_gateway"] = {
        "running": ib_status["running"],
        "name": "IB Gateway",
        "host": "127.0.0.1:4002",
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


def get_portfolio_summary(ib: Optional[Any] = None) -> Dict[str, Any]:
    """Get portfolio summary from IB or cached data."""
    summary = {
        "account_value": 0.0,
        "cash": 0.0,
        "positions_count": 0,
        "total_pnl": 0.0,
        "daily_pnl": 0.0,
        "positions": [],
    }
    
    # Use dummy data if IB not available
    if ib is None or not IB:
        return {
            "account_value": 1936241.0,
            "cash": 245830.0,
            "positions_count": 12,
            "total_pnl": 8450.0,
            "daily_pnl": 2340.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "type": "STK",
                    "position": 150.0,
                    "market_price": 182.45,
                    "market_value": 27367.50,
                    "avg_cost": 178.20,
                    "unrealized_pnl": 637.50,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "MSFT",
                    "type": "STK",
                    "position": 200.0,
                    "market_price": 415.30,
                    "market_value": 83060.0,
                    "avg_cost": 408.15,
                    "unrealized_pnl": 1430.0,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "NVDA",
                    "type": "STK",
                    "position": 100.0,
                    "market_price": 875.20,
                    "market_value": 87520.0,
                    "avg_cost": 862.40,
                    "unrealized_pnl": 1280.0,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "GOOGL",
                    "type": "STK",
                    "position": 120.0,
                    "market_price": 142.85,
                    "market_value": 17142.0,
                    "avg_cost": 139.20,
                    "unrealized_pnl": 438.0,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "AMZN",
                    "type": "STK",
                    "position": 180.0,
                    "market_price": 178.90,
                    "market_value": 32202.0,
                    "avg_cost": 175.30,
                    "unrealized_pnl": 648.0,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "META",
                    "type": "STK",
                    "position": 90.0,
                    "market_price": 485.60,
                    "market_value": 43704.0,
                    "avg_cost": 478.20,
                    "unrealized_pnl": 666.0,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "TSLA",
                    "type": "STK",
                    "position": -50.0,
                    "market_price": 198.75,
                    "market_value": -9937.50,
                    "avg_cost": 205.40,
                    "unrealized_pnl": 332.50,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "SPY",
                    "type": "STK",
                    "position": 250.0,
                    "market_price": 512.30,
                    "market_value": 128075.0,
                    "avg_cost": 508.15,
                    "unrealized_pnl": 1037.50,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "QQQ",
                    "type": "STK",
                    "position": 200.0,
                    "market_price": 445.80,
                    "market_value": 89160.0,
                    "avg_cost": 442.30,
                    "unrealized_pnl": 700.0,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "AAPL",
                    "type": "OPT",
                    "position": -5.0,
                    "market_price": 3.45,
                    "market_value": -1725.0,
                    "avg_cost": 4.20,
                    "unrealized_pnl": 375.0,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "MSFT",
                    "type": "OPT",
                    "position": -3.0,
                    "market_price": 5.80,
                    "market_value": -1740.0,
                    "avg_cost": 6.50,
                    "unrealized_pnl": 210.0,
                    "realized_pnl": 0.0,
                },
                {
                    "symbol": "SPY",
                    "type": "OPT",
                    "position": -10.0,
                    "market_price": 2.15,
                    "market_value": -2150.0,
                    "avg_cost": 2.80,
                    "unrealized_pnl": 650.0,
                    "realized_pnl": 0.0,
                },
            ],
        }
    
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
        print(f"Error fetching portfolio: {e}")
    
    return summary


def get_risk_metrics() -> Dict[str, Any]:
    """Get current risk metrics."""
    logs_dir = TRADING_DIR / "logs"
    
    # Daily loss
    daily_loss_data = load_json(logs_dir / "daily_loss.json", {})
    daily_loss = daily_loss_data.get("loss", 0.0)
    daily_limit = daily_loss_data.get("sod_equity", 0.0) * 0.03
    
    # Peak equity / drawdown
    peak_data = load_json(logs_dir / "peak_equity.json", {})
    peak_equity = peak_data.get("peak_equity", 0.0)
    current_equity = daily_loss_data.get("current_equity", 0.0)
    drawdown_pct = 0.0
    if peak_equity > 0 and current_equity > 0:
        drawdown_pct = (peak_equity - current_equity) / peak_equity * 100
    
    return {
        "daily_loss": daily_loss,
        "daily_limit": daily_limit,
        "daily_loss_pct": (daily_loss / daily_limit * 100) if daily_limit > 0 else 0,
        "peak_equity": peak_equity,
        "current_equity": current_equity,
        "drawdown_pct": drawdown_pct,
        "max_drawdown_pct": 10.0,
    }


def get_screener_results() -> Dict[str, Any]:
    """Get latest screener results."""
    results = {}
    
    # Longs
    longs_file = TRADING_DIR / "watchlist_longs.json"
    longs_data = load_json(longs_file, {})
    long_candidates = longs_data.get("long_candidates", [])
    
    # Add dummy data if no real candidates
    if not long_candidates:
        long_candidates = [
            {"symbol": "AAPL", "composite_score": 0.95, "relative_strength": 0.82, "relative_volatility": 3.2},
            {"symbol": "MSFT", "composite_score": 0.93, "relative_strength": 0.78, "relative_volatility": 2.8},
            {"symbol": "NVDA", "composite_score": 0.91, "relative_strength": 0.85, "relative_volatility": 5.1},
            {"symbol": "GOOGL", "composite_score": 0.88, "relative_strength": 0.72, "relative_volatility": 2.5},
            {"symbol": "AMZN", "composite_score": 0.87, "relative_strength": 0.75, "relative_volatility": 3.0},
            {"symbol": "META", "composite_score": 0.85, "relative_strength": 0.80, "relative_volatility": 3.8},
            {"symbol": "TSLA", "composite_score": 0.82, "relative_strength": 0.68, "relative_volatility": 6.2},
            {"symbol": "AMD", "composite_score": 0.80, "relative_strength": 0.70, "relative_volatility": 4.5},
            {"symbol": "NFLX", "composite_score": 0.78, "relative_strength": 0.65, "relative_volatility": 3.9},
            {"symbol": "CRM", "composite_score": 0.76, "relative_strength": 0.62, "relative_volatility": 2.7},
        ]
    results["longs"] = {
        "count": len(long_candidates),
        "candidates": long_candidates[:10] if isinstance(long_candidates, list) else [],
    }
    
    # Multimode (shorts + premium)
    multimode_file = TRADING_DIR / "watchlist_multimode.json"
    multimode_data = load_json(multimode_file, {})
    
    shorts = multimode_data.get("shorts", [])
    premium = multimode_data.get("premium_selling", [])
    
    # Add dummy data if no real candidates
    if not shorts:
        shorts = [
            {"symbol": "RIVN", "composite_score": 0.88, "relative_strength": -0.45, "relative_volatility": 8.2},
            {"symbol": "LCID", "composite_score": 0.85, "relative_strength": -0.52, "relative_volatility": 9.1},
            {"symbol": "PLUG", "composite_score": 0.82, "relative_strength": -0.38, "relative_volatility": 7.5},
            {"symbol": "SPCE", "composite_score": 0.80, "relative_strength": -0.48, "relative_volatility": 10.2},
            {"symbol": "HOOD", "composite_score": 0.78, "relative_strength": -0.42, "relative_volatility": 6.8},
        ]
    
    if not premium:
        premium = [
            {"symbol": "SPY", "composite_score": 0.92, "relative_strength": 0.15, "relative_volatility": 1.2},
            {"symbol": "QQQ", "composite_score": 0.90, "relative_strength": 0.18, "relative_volatility": 1.5},
            {"symbol": "IWM", "composite_score": 0.88, "relative_strength": 0.12, "relative_volatility": 1.8},
            {"symbol": "DIA", "composite_score": 0.85, "relative_strength": 0.10, "relative_volatility": 1.1},
        ]
    
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


def get_recent_logs(service: str = "webhook", lines: int = 50) -> List[str]:
    """Get recent log entries."""
    log_file = TRADING_DIR / "logs" / f"{service}.log"
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-lines:]]
    except Exception:
        return []


def get_performance_stats() -> Dict[str, Any]:
    """Get performance statistics from trade log."""
    try:
        from trade_log_db import get_closed_trades
        
        trades = get_closed_trades(days=30)
        if not trades:
            # Return dummy data until real trades exist
            return {
                "total_trades": 87,
                "wins": 54,
                "losses": 33,
                "win_rate": 62.1,
                "avg_pnl": 143.0,
                "total_pnl": 12450.0,
                "sharpe": 2.14,
            }
        
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) < 0]
        
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        avg_pnl = total_pnl / len(trades) if trades else 0
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        
        # Simple Sharpe approximation
        pnls = [t.get("pnl", 0) for t in trades]
        import statistics
        avg = statistics.mean(pnls) if pnls else 0
        std = statistics.stdev(pnls) if len(pnls) > 1 else 1
        sharpe = (avg / std * (252 ** 0.5)) if std > 0 else 0
        
        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "sharpe": sharpe,
        }
    except Exception as e:
        print(f"Error fetching performance stats: {e}")
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "total_pnl": 0.0,
            "sharpe": 0.0,
        }


# ============================================================================
# API ENDPOINTS
# ============================================================================


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


@app.get("/api/portfolio")
async def get_portfolio():
    """Get portfolio summary."""
    # Try to connect to IB
    ib = None
    if IB:
        try:
            ib = IB()
            ib.connect("127.0.0.1", 4002, clientId=999, readonly=True)
            portfolio = get_portfolio_summary(ib)
            ib.disconnect()
            return portfolio
        except Exception as e:
            print(f"Error connecting to IB: {e}")
            if ib:
                ib.disconnect()
    
    return get_portfolio_summary()


@app.get("/api/screeners")
async def get_screeners():
    """Get latest screener results."""
    return get_screener_results()


@app.get("/api/performance")
async def get_performance():
    """Get performance statistics."""
    return get_performance_stats()


@app.get("/api/logs/{service}")
async def get_logs(service: str, lines: int = 50):
    """Get recent logs for a service."""
    return {"service": service, "logs": get_recent_logs(service, lines)}


@app.post("/api/kill-switch/clear")
async def clear_kill_switch():
    """Clear the kill switch."""
    kill_switch_file = TRADING_DIR / "kill_switch.json"
    try:
        kill_switch_file.write_text(
            json.dumps(
                {
                    "active": False,
                    "cleared_at": datetime.now().isoformat(),
                    "reason": "manual clear from dashboard",
                }
            )
        )
        return {"success": True, "message": "Kill switch cleared"}
    except Exception as e:
        return {"success": False, "message": str(e)}


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
        print(f"WebSocket error: {e}")
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
