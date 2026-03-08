#!/bin/bash

# Dashboard Setup Script
# Interactive setup for dashboard data automation

echo "🎛️  Mission Control Dashboard - Setup"
echo "======================================"
echo ""

# Check if .env.dashboard already exists
if [ -f ".env.dashboard" ]; then
    echo "✓ .env.dashboard already exists"
    read -p "Overwrite? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping .env.dashboard creation"
        exit 0
    fi
fi

# Create .env.dashboard
echo "Creating .env.dashboard..."
cp .env.dashboard.template .env.dashboard

echo ""
echo "📋 Setup Instructions:"
echo "====================="
echo ""

echo "1️⃣  GitHub Token (Required)"
echo "   - Go to: https://github.com/settings/tokens"
echo "   - Create a new token"
echo "   - Select scopes: repo, public_repo"
echo "   - Copy token and edit .env.dashboard"
echo ""

echo "2️⃣  Vercel Token (Optional)"
echo "   - Go to: https://vercel.com/account/tokens"
echo "   - Create new token with Full Access"
echo "   - Copy token and edit .env.dashboard"
echo ""

echo "3️⃣  Substack API Key (Optional)"
echo "   - Usually only available with official API access"
echo "   - Or use manual updates: node scripts/fetch-substack-data.mjs --manual"
echo ""

echo "📝 Next Steps:"
echo "============="
echo ""
echo "1. Edit .env.dashboard and add your tokens:"
echo "   nano .env.dashboard"
echo ""
echo "2. Test the setup:"
echo "   source .env.dashboard"
echo "   node scripts/dashboard-scheduler.mjs --quick"
echo ""
echo "3. Add to crontab for hourly updates:"
echo "   crontab -e"
echo "   # Add this line:"
echo "   0 * * * * source ~/.openclaw/.env.dashboard && cd ~/.openclaw/workspace && node scripts/dashboard-scheduler.mjs --quick >> logs/dashboard-scheduler.log 2>&1"
echo ""
echo "4. View the dashboard:"
echo "   open dashboard.html"
echo ""

echo "✓ Setup scaffolding complete!"
