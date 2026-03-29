#!/bin/bash
# Start Dashboard Backend & Cloudflare Tunnel
# Run this script to expose the dashboard API to the internet for Cloudflare Pages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRADING_DIR="$SCRIPT_DIR/trading"
LOGS_DIR="$TRADING_DIR/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Mission Control Dashboard Backend Startup${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Check if already running
if pgrep -f "dashboard_api.py" > /dev/null; then
    echo -e "${YELLOW}⚠ Dashboard API already running${NC}"
    PID=$(pgrep -f "dashboard_api.py")
    echo "  PID: $PID"
else
    echo -e "${BLUE}→ Starting Dashboard API on port 8888...${NC}"
    cd "$TRADING_DIR/scripts/agents"
    nohup python3 dashboard_api.py >> "$LOGS_DIR/dashboard_api.log" 2>&1 &
    API_PID=$!
    echo "  PID: $API_PID"
    sleep 2
    
    # Verify it started
    if curl -s http://localhost:8888/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Dashboard API started successfully${NC}"
    else
        echo -e "${RED}✗ Dashboard API failed to start${NC}"
        echo "  Check: tail -20 $LOGS_DIR/dashboard_api.log"
        exit 1
    fi
fi

echo ""

# Check if cloudflared is already running
if pgrep -f "cloudflared.*tunnel.*8888" > /dev/null; then
    echo -e "${YELLOW}⚠ Cloudflared tunnel already running${NC}"
    
    # Extract URL from existing tunnel
    if [ -f "$LOGS_DIR/cloudflared.log" ]; then
        TUNNEL_URL=$(grep -o "https://[^[:space:]]*\.trycloudflare\.com" "$LOGS_DIR/cloudflared.log" | tail -1)
        if [ -n "$TUNNEL_URL" ]; then
            echo "  URL: $TUNNEL_URL"
        fi
    fi
else
    echo -e "${BLUE}→ Starting Cloudflare Tunnel...${NC}"
    cloudflared tunnel --url http://localhost:8888 > "$LOGS_DIR/cloudflared.log" 2>&1 &
    TUNNEL_PID=$!
    echo "  PID: $TUNNEL_PID"
    
    # Wait for tunnel URL
    echo "  Waiting for tunnel URL..."
    for i in {1..15}; do
        sleep 1
        TUNNEL_URL=$(grep -o "https://[^[:space:]]*\.trycloudflare\.com" "$LOGS_DIR/cloudflared.log" 2>/dev/null | tail -1)
        if [ -n "$TUNNEL_URL" ]; then
            break
        fi
    done
    
    if [ -n "$TUNNEL_URL" ]; then
        echo -e "${GREEN}✓ Tunnel created${NC}"
        echo "  URL: $TUNNEL_URL"
    else
        echo -e "${RED}✗ Tunnel creation failed or timed out${NC}"
        echo "  Check: tail -20 $LOGS_DIR/cloudflared.log"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Backend Ready${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""

if [ -n "$TUNNEL_URL" ]; then
    echo -e "Dashboard API: ${GREEN}http://localhost:8888${NC}"
    echo -e "Public URL:    ${GREEN}$TUNNEL_URL${NC}"
    echo ""
    echo "Test endpoints:"
    echo "  curl $TUNNEL_URL/health"
    echo "  curl $TUNNEL_URL/api/trading-modes"
    echo ""
    echo "Next steps:"
    echo "  1. Add TRADING_API_URL=$TUNNEL_URL to Cloudflare Pages env vars"
    echo "  2. Add TRADING_API_KEY=\$(grep DASHBOARD_API_KEY trading/.env | cut -d= -f2)"
    echo "  3. Redeploy on Cloudflare Pages"
    echo ""
fi

echo "To stop:"
echo "  pkill -f dashboard_api.py"
echo "  pkill -f cloudflared"
