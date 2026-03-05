#!/bin/bash
# Monitor OpenClaw GitHub for security issues

echo "=== OPENCLAW SECURITY ISSUE MONITOR ==="
echo "Timestamp: $(date)"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) not installed"
    echo "Install with: brew install gh"
    exit 1
fi

# Verify gh auth
echo "Checking GitHub authentication..."
gh auth status 2>&1 | head -3

echo ""
echo "Fetching OpenClaw security issues..."

# Monitor OpenClaw repo for security-related issues
gh issue list --repo openclaw/openclaw \
    --label "security" \
    --state open \
    --limit 10 \
    2>/dev/null || echo "Note: Ensure 'gh auth login' is configured"

echo ""
echo "Checking for vulnerability reports..."
gh issue list --repo openclaw/openclaw \
    --search "vulnerability OR CVE OR exploit" \
    --state open \
    --limit 5 \
    2>/dev/null || echo "Note: GitHub API may require auth"

echo ""
echo "✅ GitHub monitoring configured"

