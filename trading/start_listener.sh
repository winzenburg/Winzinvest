#!/bin/bash
# Start the TradingView webhook listener
# Make sure IB Gateway is running first!

cd "$(dirname "$0")"

# Load environment
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy .env.template and configure it first."
    exit 1
fi

export $(cat .env | grep -v '^#' | xargs)

# Check if IB Gateway is running (basic check)
echo "🔍 Checking IB Gateway connection..."
nc -z 127.0.0.1 4002 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Cannot connect to IB Gateway on port 4002"
    echo "   Make sure IB Gateway is running and API is enabled"
else
    echo "✅ IB Gateway detected on port 4002"
fi

echo "🚀 Starting webhook listener on http://127.0.0.1:5001"
echo "📊 Webhook endpoint: http://127.0.0.1:5001/webhook"
echo "💓 Health check: http://127.0.0.1:5001/health"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 scripts/webhook_listener.py
