#!/usr/bin/env bash
#
# Start the fully automated trading system.
#
# Launches four background processes:
#   1. Dashboard         — web UI on http://localhost:8002
#   2. Webhook Server   — receives TradingView pullback alerts
#   3. Background Agents — risk monitor, reconnection, trade outcome resolver
#   4. Scheduler         — runs screeners + executors on market-hours cron
#
# Usage:
#   ./start.sh          # Start everything
#   ./start.sh stop     # Stop all processes
#   ./start.sh status   # Show running processes
#   ./start.sh logs     # Tail all logs
#
# Prerequisites:
#   pip install apscheduler fastapi uvicorn ib_insync yfinance
#   IB Gateway running on 127.0.0.1:4002
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
LOGS_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/.pids"
PYTHON="${PYTHON:-python3}"

mkdir -p "$LOGS_DIR" "$PID_DIR"

export PYTHONPATH="$SCRIPTS_DIR:${PYTHONPATH:-}"

# Load .env if present (project root or trading/)
if [ -f "$SCRIPT_DIR/../.env" ]; then
    set -a
    source "$SCRIPT_DIR/../.env"
    set +a
fi
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi
# Load Cursor local env (e.g. TV_WEBHOOK_SECRET) so all services see it
if [ -f "$HOME/.cursor/.env.local" ]; then
    set -a
    source "$HOME/.cursor/.env.local"
    set +a
fi
# Also load workspace-local overrides (.cursor/.env.local next to this repo)
if [ -f "$SCRIPT_DIR/../.cursor/.env.local" ]; then
    set -a
    source "$SCRIPT_DIR/../.cursor/.env.local"
    set +a
fi

_pid_file() { echo "$PID_DIR/$1.pid"; }

_is_running() {
    local pid_file
    pid_file="$(_pid_file "$1")"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

_start_process() {
    local name="$1"
    shift
    if _is_running "$name"; then
        echo "  [SKIP] $name already running (PID $(cat "$(_pid_file "$name")"))"
        return
    fi
    "$@" >> "$LOGS_DIR/${name}.log" 2>&1 &
    local pid=$!
    disown -h "$pid" 2>/dev/null || true
    echo "$pid" > "$(_pid_file "$name")"
    echo "  [START] $name (PID $pid) → logs/$name.log"
}

_stop_process() {
    local name="$1"
    if _is_running "$name"; then
        local pid
        pid=$(cat "$(_pid_file "$name")")
        echo "  [STOP] $name (PID $pid)"
        kill "$pid" 2>/dev/null || true
        rm -f "$(_pid_file "$name")"
    else
        echo "  [SKIP] $name not running"
    fi
}

# Kill process(es) holding a port if not our managed PID (so we can bind).
_free_port() {
    local port="$1"
    local managed_name="$2"
    local managed_pid=""
    if [ -f "$(_pid_file "$managed_name")" ]; then
        managed_pid=$(cat "$(_pid_file "$managed_name")")
    fi
    local pids
    pids=$(lsof -ti ":$port" 2>/dev/null || true)
    if [ -z "$pids" ]; then
        return
    fi
    for pid in $pids; do
        [ -z "$pid" ] && continue
        [ "$pid" = "$managed_pid" ] && continue
        echo "  [FREE] Killing process $pid on port $port (so $managed_name can bind)"
        kill "$pid" 2>/dev/null || true
    done
    if [ -n "$pids" ]; then
        sleep 2
    fi
}

cmd_start() {
    echo ""
    echo "  MISSION CONTROL — Automated Trading System"
    echo "  ============================================"
    echo ""

    # Verify IB Gateway connectivity for active mode
    local live_port="${IB_PORT:-4001}"
    local paper_port="4002"

    if nc -z 127.0.0.1 "$live_port" 2>/dev/null; then
        echo "  [OK]   Live  gateway: 127.0.0.1:${live_port}"
    else
        echo "  [WARN] Live  gateway NOT reachable on 127.0.0.1:${live_port}"
        echo "         Start IB Gateway (live) before trading can execute."
    fi

    if nc -z 127.0.0.1 "$paper_port" 2>/dev/null; then
        echo "  [OK]   Paper gateway: 127.0.0.1:${paper_port}"
    else
        echo "  [INFO] Paper gateway not running on 127.0.0.1:${paper_port} (optional)"
        echo "         Run ./trading/start_paper_gateway.sh to enable paper mode."
    fi
    echo ""

    # Free ports 8001 and 8002 if another process (not our managed one) holds them
    _free_port 8001 "webhook"
    _free_port 8002 "dashboard"
    # Brief wait so the OS releases the ports before we start new processes
    sleep 1

    # Ensure trades.db is initialized (idempotent — safe to call every start)
    echo "  [INIT] Ensuring trades.db schema exists..."
    "$PYTHON" -c "
import sys; sys.path.insert(0, '$SCRIPTS_DIR')
from trade_log_db import init_db
init_db()
" 2>/dev/null && echo "  [OK]   trades.db ready" || echo "  [WARN] trades.db init failed (non-fatal)"

    echo ""
    echo "  Starting services..."
    echo ""

    _start_process "dashboard" \
        "$PYTHON" "$SCRIPT_DIR/dashboard/api.py"

    _start_process "health" \
        uvicorn agents.health_check:app --host 0.0.0.0 --port 8000 \
        --app-dir "$SCRIPTS_DIR"

    _start_process "frontend" \
        env PORT=3001 npm --prefix "$SCRIPT_DIR/../trading-dashboard-public" run dev

    _start_process "webhook" \
        "$PYTHON" "$SCRIPTS_DIR/agents/webhook_server.py"

    _start_process "agents" \
        "$PYTHON" -m agents.run_all

    _start_process "scheduler" \
        "$PYTHON" "$SCRIPTS_DIR/scheduler.py"

    _start_process "watchdog" \
        "$PYTHON" "$SCRIPTS_DIR/watchdog.py"

    _start_process "gateway_watchdog" \
        bash "$SCRIPTS_DIR/gateway_watchdog.sh" --port "${IB_PORT:-4001}"

    # Cloudflare Tunnel (if configured) — enables secure remote access
    if command -v cloudflared &>/dev/null && [ -f "$HOME/.cloudflared/config.yml" ]; then
        _start_process "tunnel" \
            cloudflared tunnel run mission-control
        local _domain_file="$HOME/.cloudflared/mission-control-domain.txt"
        local _remote_url=""
        if [ -f "$_domain_file" ]; then
            _remote_url="https://$(cat "$_domain_file")"
        fi
        echo ""
        echo "  All services started."
        echo ""
        echo "  📊 Dashboard: http://localhost:3001/institutional"
        if [ -n "$_remote_url" ]; then
            echo "  📱 Remote:    $_remote_url/institutional"
        fi
    else
        echo ""
        echo "  All services started."
        echo ""
        echo "  📊 Dashboard: http://localhost:3001/institutional"
        echo "  📱 Remote:    Not configured. Run ./setup_tunnel.sh to enable."
    fi
    echo "  🔗 Webhook:   http://localhost:8001"
    echo ""
    echo "  Use './start.sh status' to check service status."
    echo "  Use './start.sh logs' to follow output."
    echo "  Use './start.sh stop' to shut down."
    echo ""
}

cmd_stop() {
    echo ""
    echo "  Stopping services..."
    echo ""
    _stop_process "tunnel"
    _stop_process "frontend"
    _stop_process "health"
    _stop_process "gateway_watchdog"
    _stop_process "watchdog"
    _stop_process "scheduler"
    _stop_process "agents"
    _stop_process "webhook"
    _stop_process "dashboard"
    echo ""
    echo "  All services stopped."
    echo ""
}

cmd_status() {
    echo ""
    echo "  SERVICE STATUS"
    echo "  =============="
    for svc in frontend health dashboard webhook agents scheduler watchdog gateway_watchdog tunnel; do
        if _is_running "$svc"; then
            echo "  $svc: RUNNING (PID $(cat "$(_pid_file "$svc")"))"
        else
            echo "  $svc: STOPPED"
        fi
    done

    # Check IB Gateways
    local live_port="${IB_PORT:-4001}"
    if nc -z 127.0.0.1 "$live_port" 2>/dev/null; then
        echo "  ib_gateway_live:  RUNNING (127.0.0.1:${live_port})"
    else
        echo "  ib_gateway_live:  STOPPED"
    fi
    if nc -z 127.0.0.1 4002 2>/dev/null; then
        echo "  ib_gateway_paper: RUNNING (127.0.0.1:4002)"
    else
        echo "  ib_gateway_paper: STOPPED"
    fi
    echo ""
}

cmd_logs() {
    tail -f "$LOGS_DIR/dashboard.log" "$LOGS_DIR/scheduler.log" "$LOGS_DIR/webhook.log" "$LOGS_DIR/agents.log" 2>/dev/null
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

case "${1:-start}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    restart) cmd_restart ;;
    *)
        echo "Usage: $0 {start|stop|status|logs|restart}"
        exit 1
        ;;
esac
