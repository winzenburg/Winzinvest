#!/bin/bash

# Test the Research trigger system
# Usage: ./test-research-trigger.sh "AI agents for traders"

echo ""
echo "🧪 Testing Research Trigger System"
echo "=================================="
echo ""

TOPIC="${1:-AI agents for traders}"
echo "📍 Test topic: \"$TOPIC\""
echo ""

# Navigate to workspace
cd "$(dirname "$0")/.."

echo "Step 1️⃣ : Executing research agent..."
echo "Command: node scripts/research-agent.mjs \"Research: $TOPIC\""
echo ""

node scripts/research-agent.mjs "Research: $TOPIC"

echo ""
echo "Step 2️⃣ : Checking output..."
echo ""

# Find the generated research brief
BRIEF=$(ls -t research/*_*.md 2>/dev/null | head -1)

if [ -z "$BRIEF" ]; then
  echo "❌ No research brief found"
  exit 1
fi

echo "✅ Research brief generated:"
echo "   📄 File: $BRIEF"
echo ""

echo "Step 3️⃣ : Preview of research brief:"
echo "---"
head -n 30 "$BRIEF"
echo "..."
echo "---"
echo ""

echo "✅ Test complete!"
echo ""
echo "Next steps:"
echo "1. Review the full brief at: $BRIEF"
echo "2. To trigger from chat, send: Research: $TOPIC"
echo "3. To prototype, reply with: Build it"
echo ""
