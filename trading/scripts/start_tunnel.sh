#!/bin/bash

# Start Cloudflare tunnel for webhook approval buttons
# This creates a temporary public URL that forwards to localhost:5001

echo "Starting Cloudflare tunnel for trading webhook..."
echo "This will expose http://127.0.0.1:5001 to the internet temporarily"
echo ""

cloudflared tunnel --url http://127.0.0.1:5001 2>&1 | tee ~/.openclaw/workspace/trading/logs/tunnel.log
