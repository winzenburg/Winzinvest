#!/usr/bin/env bash
#
# start_paper_gateway.sh
#
# Launches a second IB Gateway instance in paper-trading mode on port 4002.
# Uses a separate Jts-paper config directory so it can run alongside the live
# gateway (port 4001) without conflicts.
#
# First-time setup
# ----------------
# Run this script once. A second IB Gateway window will open — log in with your
# paper-trading credentials. Once authenticated the gateway stays running in the
# background. Subsequent runs will reuse the same session.
#
# Usage:
#   ./trading/start_paper_gateway.sh          # start paper gateway
#   ./trading/start_paper_gateway.sh status   # check if it's reachable
#   ./trading/start_paper_gateway.sh stop     # kill the paper gateway process
#

set -euo pipefail

JTS_PAPER="$HOME/Jts-paper"
PAPER_PORT=4002
GW_APP="IB Gateway 10.44"

# ── helpers ──────────────────────────────────────────────────────────────────

_gateway_running() {
    nc -z 127.0.0.1 "$PAPER_PORT" 2>/dev/null
}

_status() {
    if _gateway_running; then
        echo "  Paper gateway: RUNNING (127.0.0.1:$PAPER_PORT)"
    else
        echo "  Paper gateway: NOT RUNNING"
    fi
}

# ── bootstrap jts.ini ────────────────────────────────────────────────────────

_bootstrap_jts() {
    mkdir -p "$JTS_PAPER"
    if [ ! -f "$JTS_PAPER/jts.ini" ]; then
        echo "  Creating $JTS_PAPER/jts.ini…"
        cat > "$JTS_PAPER/jts.ini" << 'INIEOF'
[IBGateway]
WriteDebug=false
TrustedIPs=127.0.0.1
RemoteHostOrderRouting=ndc1.ibllc.com
RemotePortOrderRouting=4002
LocalServerPort=4003
ApiOnly=true
MainWindow.Height=550
MainWindow.Width=700

[Logon]
useRemoteSettings=false
TimeZone=America/Denver
tradingMode=p
colorPalletName=dark
Steps=4
Locale=en
os_titlebar=false
UseSSL=true
ibkrBranding=pro

[Communication]
Peer=cdc1.ibllc.com:4001
Region=us
INIEOF
        echo "  jts.ini created."
    else
        echo "  jts.ini already exists — skipping."
    fi
}

# ── subcommands ──────────────────────────────────────────────────────────────

cmd_start() {
    _bootstrap_jts

    if _gateway_running; then
        echo "  Paper gateway already running on port $PAPER_PORT."
        exit 0
    fi

    # Find the IB Gateway app bundle
    GW_PATH=""
    for candidate in \
        "$HOME/Applications/$GW_APP.app" \
        "/Applications/$GW_APP.app" \
        "$HOME/Applications/IB Gateway.app" \
        "/Applications/IB Gateway.app"
    do
        if [ -d "$candidate" ]; then
            GW_PATH="$candidate"
            break
        fi
    done

    if [ -z "$GW_PATH" ]; then
        echo "  ERROR: Could not find IB Gateway app."
        echo "  Expected: $HOME/Applications/$GW_APP.app"
        exit 1
    fi

    echo "  Starting paper IB Gateway from: $GW_PATH"
    echo "  Config dir: $JTS_PAPER"
    echo "  API port:   $PAPER_PORT"
    echo ""
    echo "  A login window will open — use your PAPER trading credentials."
    echo "  (These are separate from your live account credentials.)"
    echo ""

    # Launch with a custom JTSHome so this instance uses ~/Jts-paper/
    # The -DJTS_HOME JVM property overrides the default ~/Jts/ directory.
    open -a "$GW_PATH" --args "-DJTS_HOME=$JTS_PAPER" &

    echo "  Waiting for gateway to start (up to 30s)…"
    for i in $(seq 1 30); do
        if _gateway_running; then
            echo "  Paper gateway is up on port $PAPER_PORT."
            exit 0
        fi
        sleep 1
    done

    echo ""
    echo "  [WARN] Gateway didn't respond on port $PAPER_PORT within 30s."
    echo "         If a login window appeared, complete login and then run:"
    echo "         ./trading/start_paper_gateway.sh status"
}

cmd_stop() {
    # Kill any process listening on the paper port
    local pids
    pids=$(lsof -ti ":$PAPER_PORT" 2>/dev/null || true)
    if [ -z "$pids" ]; then
        echo "  No process found on port $PAPER_PORT."
    else
        for pid in $pids; do
            echo "  Stopping process $pid (port $PAPER_PORT)…"
            kill "$pid" 2>/dev/null || true
        done
        echo "  Paper gateway stopped."
    fi
}

case "${1:-start}" in
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    status) _status ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
