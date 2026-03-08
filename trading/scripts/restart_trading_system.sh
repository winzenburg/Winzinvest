#!/bin/bash

# Restart the complete trading system (webhook listener + cloudflare tunnel)

TRADING_DIR="$HOME/.openclaw/workspace/trading"
cd "$TRADING_DIR"

echo "🛑 Stopping existing processes..."
pkill -f webhook_listener.py
pkill -f cloudflared

sleep 2

echo "🚀 Starting Cloudflare tunnel..."
cloudflared tunnel --url http://127.0.0.1:5001 > logs/tunnel.log 2>&1 &

sleep 5

echo "📡 Getting tunnel URL..."
TUNNEL_URL=$(grep -o "https://.*\.trycloudflare\.com" logs/tunnel.log | head -1)

if [ -z "$TUNNEL_URL" ]; then
    echo "❌ Failed to get tunnel URL"
    exit 1
fi

echo "✅ Tunnel URL: $TUNNEL_URL"

echo "📝 Updating .env with new tunnel URL..."
# Update BASE_URL in .env
sed -i.bak "s|BASE_URL=.*|BASE_URL=$TUNNEL_URL|" .env

echo "🚀 Starting webhook listener..."
scripts/start_webhook.sh > logs/webhook_listener.log 2>&1 &

sleep 3

echo "✅ System started!"
echo ""
echo "Tunnel URL: $TUNNEL_URL"
echo "Webhook: http://127.0.0.1:5001"
echo ""
echo "Check status: curl http://127.0.0.1:5001/health"
