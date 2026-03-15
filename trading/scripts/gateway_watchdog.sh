#!/usr/bin/env bash
# =============================================================================
# IB Gateway Watchdog
# Checks port 4001 (live) every 60s. If unreachable for 2+ consecutive checks,
# attempts to relaunch IB Gateway and notifies via the trading log.
#
# Usage:
#   ./gateway_watchdog.sh [--port 4001] [--interval 60] [--max-restarts 3]
#
# Run in background:
#   nohup ./gateway_watchdog.sh >> logs/gateway_watchdog.log 2>&1 &
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRADING_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$TRADING_DIR/logs/gateway_watchdog.log"
PID_FILE="$TRADING_DIR/.pids/gateway_watchdog.pid"

# --- Config (override via args) ---
PORT="${IB_PORT:-4001}"
CHECK_INTERVAL=60       # seconds between checks
FAIL_THRESHOLD=2        # consecutive failures before restart attempt
MAX_RESTARTS=3          # max restarts per hour before giving up
GATEWAY_APP="IB Gateway"

# --- Arg parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)       PORT="$2";          shift 2 ;;
        --interval)   CHECK_INTERVAL="$2"; shift 2 ;;
        --max-restarts) MAX_RESTARTS="$2"; shift 2 ;;
        *) shift ;;
    esac
done

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PID_FILE")"
echo $$ > "$PID_FILE"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] $*" | tee -a "$LOG_FILE"; }

port_open() {
    # Returns 0 (success) if TCP port is reachable within 3s
    nc -z -w 3 127.0.0.1 "$PORT" >/dev/null 2>&1
}

gateway_pid() {
    # Find PID of IB Gateway process listening on the port
    lsof -t -i "TCP:${PORT}" -s TCP:LISTEN 2>/dev/null | head -1
}

IBC_START_SCRIPT="$HOME/ibc/gatewaystartmacos.sh"

restart_gateway() {
    log "Attempting to relaunch IB Gateway via IBC (port $PORT)..."

    if [[ -x "$IBC_START_SCRIPT" ]]; then
        log "Using IBC: $IBC_START_SCRIPT"
        # IBC opens a new Terminal window and handles login/2FA automatically
        "$IBC_START_SCRIPT" &
        local wait_secs=60   # IBC + 2FA approval can take up to ~60s
        log "Waiting up to ${wait_secs}s for port $PORT to open..."
        for (( i=0; i<wait_secs; i++ )); do
            sleep 1
            if port_open; then
                log "Gateway restarted successfully via IBC (port $PORT open after ${i}s)."
                return 0
            fi
        done
        log "WARNING: Port $PORT still closed after ${wait_secs}s — 2FA may be pending. Will check again next interval."
        return 1
    else
        # Fallback: direct open (no auto-login)
        log "IBC not found at $IBC_START_SCRIPT — falling back to open -a"
        local gw_path
        gw_path=$(find "$HOME/Applications" /Applications -maxdepth 2 -name "IB Gateway*.app" 2>/dev/null | head -1 || true)
        if [[ -z "$gw_path" ]]; then
            log "ERROR: Cannot find IB Gateway app. Manual restart required."
            return 1
        fi
        open -a "$gw_path" &
        sleep 20
        if port_open; then
            log "Gateway restarted via open -a (port $PORT open)."
            return 0
        fi
        log "Gateway launch attempted but port $PORT still closed."
        return 1
    fi
}

log "Gateway watchdog started (port=$PORT, interval=${CHECK_INTERVAL}s, fail_threshold=$FAIL_THRESHOLD, max_restarts=$MAX_RESTARTS/hr)"

consecutive_failures=0
restart_count=0
restart_window_start=$(date +%s)

while true; do
    sleep "$CHECK_INTERVAL"

    # Reset hourly restart counter
    now=$(date +%s)
    if (( now - restart_window_start >= 3600 )); then
        restart_count=0
        restart_window_start=$now
    fi

    if port_open; then
        if (( consecutive_failures > 0 )); then
            log "Gateway recovered on port $PORT (was down for $((consecutive_failures * CHECK_INTERVAL))s)"
        fi
        consecutive_failures=0
        continue
    fi

    consecutive_failures=$((consecutive_failures + 1))
    log "WARNING: port $PORT unreachable (failure #$consecutive_failures)"

    if (( consecutive_failures < FAIL_THRESHOLD )); then
        continue
    fi

    # Reached failure threshold — attempt restart
    if (( restart_count >= MAX_RESTARTS )); then
        log "ERROR: Max restarts ($MAX_RESTARTS/hr) reached. Gateway is down. Manual intervention required."
        # Only log this once per cycle
        consecutive_failures=1
        continue
    fi

    log "Failure threshold reached — initiating restart attempt $((restart_count + 1))/$MAX_RESTARTS"
    if restart_gateway; then
        restart_count=$((restart_count + 1))
        consecutive_failures=0
    else
        restart_count=$((restart_count + 1))
        log "Restart failed ($restart_count/$MAX_RESTARTS). Will retry after next interval."
    fi
done
