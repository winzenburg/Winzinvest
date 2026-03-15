#!/usr/bin/env bash
#
# End-to-end smoke test for Mission Control trading system.
# Verifies: dashboard, webhook, IB Gateway, and (optionally) scheduler dry-run.
# Does NOT place any orders.
#
# Usage: from trading/scripts with PYTHONPATH="." or from trading/ run:
#   ./scripts/e2e_smoke_test.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRADING_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOGS_DIR="$TRADING_DIR/logs"
PID_DIR="$TRADING_DIR/.pids"

PASS=0
FAIL=0

_report() {
    if [ "$1" = "ok" ]; then
        echo "  ✅ $2"
        ((PASS+=1)) || true
    else
        echo "  ❌ $2"
        ((FAIL+=1)) || true
    fi
}

# Check process by name (dashboard, webhook, agents, scheduler)
_is_running() {
    local name="$1"
    local pid_file="$PID_DIR/${name}.pid"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

echo ""
echo "  Mission Control — E2E Smoke Test"
echo "  ================================"
echo ""

# 1. Dashboard (port 8002)
if curl -sf --connect-timeout 3 "http://127.0.0.1:8002/api/status" >/dev/null 2>&1; then
    _report ok "Dashboard responding (http://127.0.0.1:8002)"
else
    _report fail "Dashboard not responding on 8002"
fi

# 2. Webhook (port 8001)
WEBHOOK_RESP=$(curl -sf --connect-timeout 3 "http://127.0.0.1:8001/webhook/health" 2>/dev/null || true)
if echo "$WEBHOOK_RESP" | grep -q '"ok":true'; then
    _report ok "Webhook responding (http://127.0.0.1:8001/webhook/health)"
else
    _report fail "Webhook not responding or unhealthy on 8001"
fi

# 3. IB Gateway (port 4002)
if nc -z 127.0.0.1 4002 2>/dev/null; then
    _report ok "IB Gateway reachable (127.0.0.1:4002)"
else
    _report fail "IB Gateway not reachable on 4002"
fi

# 4. Background agents (process check)
if _is_running "agents"; then
    _report ok "Agents process running (risk monitor, reconnection, outcome resolver)"
else
    _report fail "Agents process not running"
fi

# 5. Scheduler (process check)
if _is_running "scheduler"; then
    _report ok "Scheduler process running"
else
    _report fail "Scheduler process not running"
fi

# 6. Scheduler dry-run (loads jobs, no execution)
if [ -f "$SCRIPT_DIR/scheduler.py" ]; then
    if (cd "$SCRIPT_DIR" && PYTHONPATH="." python3 scheduler.py --dry-run >/dev/null 2>&1); then
        _report ok "Scheduler dry-run OK (schedule loads)"
    else
        _report fail "Scheduler dry-run failed"
    fi
fi

# 7. Dashboard /api/status reports healthy (if we got here with dashboard up)
if [ $FAIL -eq 0 ] || curl -sf --connect-timeout 2 "http://127.0.0.1:8002/api/status" >/tmp/mc_status.json 2>/dev/null; then
    if [ -f /tmp/mc_status.json ] && grep -q '"healthy":true' /tmp/mc_status.json 2>/dev/null; then
        _report ok "System healthy (dashboard aggregate)"
    elif [ $FAIL -gt 0 ]; then
        : # already reported failures
    fi
fi
rm -f /tmp/mc_status.json

echo ""
echo "  Result: $PASS passed, $FAIL failed"
echo ""

if [ $FAIL -gt 0 ]; then
    echo "  Next steps: ./start.sh status   or   ./start.sh start"
    echo ""
    exit 1
fi

echo "  All checks passed. System is running."
echo ""
exit 0
