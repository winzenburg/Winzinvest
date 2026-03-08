#!/bin/bash
# Trading Setup Health Check
# Verifies all components are running and configured

echo "🏥 Trading Setup Health Check"
echo "======================================="
echo ""

# 1. Webhook listener
echo "1️⃣  Webhook Listener (port 5001)"
if lsof -i :5001 > /dev/null 2>&1; then
    echo "   ✅ Running"
else
    echo "   ❌ Not running"
    echo "   Start with: python3 ~/.openclaw/workspace/trading/webhook_listener.py"
fi
echo ""

# 2. Telegram credentials
echo "2️⃣  Telegram Configuration"
if [ ! -z "$TELEGRAM_BOT_TOKEN" ] && [ ! -z "$TELEGRAM_CHAT_ID" ]; then
    echo "   ✅ Bot token and chat ID set"
else
    echo "   ❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
    echo "   Set via: export TELEGRAM_BOT_TOKEN=... && export TELEGRAM_CHAT_ID=..."
fi
echo ""

# 3. IB API
echo "3️⃣  Interactive Brokers API (port 7497)"
if lsof -i :7497 > /dev/null 2>&1; then
    echo "   ✅ Port open (API available)"
else
    echo "   ⚠️  Port not open - TWS/IBGateway may not be running"
    echo "   Start TWS/IBGateway and enable API access"
fi
echo ""

# 4. Watchlist file
echo "4️⃣  Watchlist File"
if [ -f ~/.openclaw/workspace/trading/watchlist.json ]; then
    stock_count=$(jq '.stocks | length' ~/.openclaw/workspace/trading/watchlist.json 2>/dev/null || echo "?")
    echo "   ✅ Exists with $stock_count stocks"
else
    echo "   ⚠️  Not created yet"
    echo "   Initialize with: python3 ~/.openclaw/workspace/trading/watchlist_sync.py report"
fi
echo ""

# 5. Python dependencies
echo "5️⃣  Python Dependencies"
python_ok=true

python3 -c "import ib_insync" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ ib_insync installed"
else
    echo "   ❌ ib_insync missing (pip install ib_insync)"
    python_ok=false
fi

python3 -c "import requests" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ requests installed"
else
    echo "   ❌ requests missing (pip install requests)"
    python_ok=false
fi

echo ""

# 6. Scripts executable
echo "6️⃣  Script Permissions"
scripts=("webhook_listener.py" "ib_portfolio_tracker.py" "watchlist_sync.py" "health_check.sh")
for script in "${scripts[@]}"; do
    if [ -x ~/.openclaw/workspace/trading/$script ]; then
        echo "   ✅ $script is executable"
    else
        echo "   ⚠️  $script not executable"
        echo "      Run: chmod +x ~/.openclaw/workspace/trading/$script"
    fi
done
echo ""

# Summary
echo "======================================="
echo ""
if [ "$python_ok" = true ]; then
    echo "✅ Setup looks good!"
    echo ""
    echo "Next steps:"
    echo "1. Start webhook: python3 ~/.openclaw/workspace/trading/webhook_listener.py &"
    echo "2. Test IB connection: python3 ~/.openclaw/workspace/trading/ib_portfolio_tracker.py"
    echo "3. Initialize watchlist: python3 ~/.openclaw/workspace/trading/watchlist_sync.py report"
    echo "4. Set up TradingView alert with webhook URL"
else
    echo "⚠️  Some dependencies missing - install before continuing"
    echo "   pip install ib_insync requests"
fi
