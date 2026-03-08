#!/bin/bash
# FRED API Setup Helper

echo "========================================="
echo "FRED API Setup"
echo "========================================="
echo ""
echo "To use the regime monitoring system, you need a free FRED API key."
echo ""
echo "Steps:"
echo "1. Go to: https://fred.stlouisfed.org/docs/api/api_key.html"
echo "2. Click 'Request API Key'"
echo "3. Sign in or create account (free)"
echo "4. Copy your API key"
echo "5. Add to trading/.env:"
echo ""
echo "   FRED_API_KEY=your_key_here"
echo ""
echo "========================================="
echo ""

# Check if already configured
if [ -f "trading/.env" ]; then
    if grep -q "FRED_API_KEY=" trading/.env; then
        echo "✅ FRED_API_KEY already present in .env"
    else
        echo "⚠️  FRED_API_KEY not found in .env"
        echo ""
        read -p "Enter your FRED API key (or press Enter to skip): " api_key
        if [ -n "$api_key" ]; then
            echo "" >> trading/.env
            echo "# FRED API for macro data" >> trading/.env
            echo "FRED_API_KEY=$api_key" >> trading/.env
            echo "✅ Added FRED_API_KEY to .env"
        fi
    fi
else
    echo "❌ trading/.env not found"
fi
