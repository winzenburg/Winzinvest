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

# Load .env if present
if [ -f "$SCRIPT_DIR/../.env" ]; then
    set -a
    source "$SCRIPT_DIR/../.env"
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

cmd_start() {
    echo ""
    echo "  MISSION CONTROL — Automated Trading System"
    echo "  ============================================"
    echo ""

    # Verify IB Gateway is reachable
    if ! nc -z 127.0.0.1 4002 2>/dev/null; then
        echo "  [WARN] IB Gateway not detected on 127.0.0.1:4002"
        echo "         Start IB Gateway before trading can execute."
        echo ""
    fi

    echo "  Starting services..."
    echo ""

    _start_process "dashboard" \
        "$PYTHON" "$SCRIPT_DIR/dashboard/api.py"

    _start_process "webhook" \
        "$PYTHON" "$SCRIPTS_DIR/agents/webhook_server.py"

    _start_process "agents" \
        "$PYTHON" -m agents.run_all

    _start_process "scheduler" \
        "$PYTHON" "$SCRIPTS_DIR/scheduler.py"

    echo ""
    echo "  All services started."
    echo ""
    echo "  📊 Dashboard: http://localhost:8002"
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
    for svc in dashboard webhook agents scheduler; do
        if _is_running "$svc"; then
            echo "  $svc: RUNNING (PID $(cat "$(_pid_file "$svc")"))"
        else
            echo "  $svc: STOPPED"
        fi
    done

    # Check IB Gateway
    if nc -z 127.0.0.1 4002 2>/dev/null; then
        echo "  ib_gateway: REACHABLE (127.0.0.1:4002)"
    else
        echo "  ib_gateway: NOT REACHABLE"
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
