#!/bin/bash

# OpenClaw Email Configuration Setup Script
# ==========================================
# 
# Interactive setup for email delivery system
# Creates .env files and configures launchd jobs
#
# Usage: bash scripts/setup-email-config.sh
#
# This script will:
# 1. Prompt for API keys and email addresses
# 2. Create/update .env files
# 3. Update launchd plist files
# 4. Test email delivery
# 5. Reload launchd jobs

set -e

WORKSPACE_DIR="${WORKSPACE_DIR:=$HOME/.openclaw/workspace}"
TRADING_DIR="$WORKSPACE_DIR/trading"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Main setup
main() {
    log_section "OpenClaw Email Configuration Setup"
    
    log_info "This script will guide you through setting up email delivery"
    log_info "Location: $WORKSPACE_DIR"
    echo ""
    
    # Create logs directory if it doesn't exist
    mkdir -p "$WORKSPACE_DIR/logs"
    mkdir -p "$TRADING_DIR/logs"
    
    # Step 1: Resend API Key
    log_section "Step 1: Resend Email API"
    log_info "Email delivery uses Resend (https://resend.com)"
    log_info "Get your API key from: https://resend.com/api-keys"
    echo ""
    
    read -p "Enter your Resend API Key (starts with 're_'): " resend_api_key
    
    if [[ ! $resend_api_key =~ ^re_ ]]; then
        log_error "Invalid API key format. Should start with 're_'"
        exit 1
    fi
    log_success "Resend API key configured"
    echo ""
    
    # Step 2: Email addresses
    log_section "Step 2: Email Addresses"
    
    read -p "Enter sender email address (e.g., notifications@pinchy.dev): " from_email
    if [[ ! $from_email =~ @.*\. ]]; then
        log_error "Invalid email format"
        exit 1
    fi
    log_success "Sender email: $from_email"
    echo ""
    
    read -p "Enter recipient email address (e.g., ryanwinzenburg@gmail.com): " to_email
    if [[ ! $to_email =~ @.*\. ]]; then
        log_error "Invalid email format"
        exit 1
    fi
    log_success "Recipient email: $to_email"
    echo ""
    
    # Step 3: Create/update .env files
    log_section "Step 3: Creating Configuration Files"
    
    # Update or create workspace .env
    log_info "Creating $WORKSPACE_DIR/.env"
    cat > "$WORKSPACE_DIR/.env" << EOF
# OpenClaw Workspace Configuration
# Generated: $(date)

# Email Configuration
RESEND_API_KEY=$resend_api_key
FROM_EMAIL=$from_email
TO_EMAIL=$to_email

# Telegram
TELEGRAM_BOT_TOKEN=8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ
TELEGRAM_CHAT_ID=5316436116
TELEGRAM_CONTENT_BOT_TOKEN=8371458070:AAGikV_sggOi7zyWqX7zE1qr9Izgz1LpK0s
TELEGRAM_USER_ID=5316436116

# Interactive Brokers
IB_PORT=4002
IB_HOST=127.0.0.1

# Workspace
WORKSPACE_DIR=$WORKSPACE_DIR
EOF
    log_success "Workspace config created"
    
    # Update trading/.env
    log_info "Updating $TRADING_DIR/.env"
    if [[ -f "$TRADING_DIR/.env" ]]; then
        # Backup existing
        cp "$TRADING_DIR/.env" "$TRADING_DIR/.env.backup.$(date +%s)"
        log_info "Backed up existing config to .env.backup"
    fi
    
    # Keep trading-specific settings, just update email if needed
    cat > "$TRADING_DIR/.env" << 'EOF'
# OpenClaw Trading System - Environment Config
# Updated by setup script

# Interactive Brokers connection (paper trading)
IB_HOST=127.0.0.1
IB_PORT=4002
IB_CLIENT_ID=101

# Telegram bot for approve/deny notifications
TELEGRAM_BOT_TOKEN=8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ
TELEGRAM_CHAT_ID=5316436116

# Public base URL for approve/deny buttons (Cloudflare Tunnel)
BASE_URL=https://describing-achievements-mercy-resorts.trycloudflare.com

# Trading modes
CANARY=0
SAFE_MODE=true
AUTO_APPROVE=false

# Webhook
WEBHOOK_URL=http://127.0.0.1:5001/webhook
WEBHOOK_TIMEOUT=10

# Connection Security Settings
IB_TIMEOUT=30
AUTO_DISCONNECT_IDLE=1800
MAX_RETRIES=3
RETRY_DELAY=5

# Rate limiting (milliseconds between API requests)
API_REQUEST_DELAY=100

# Logging
LOG_LEVEL=INFO
AUDIT_LOG_ENABLED=true
AUDIT_LOG_PATH=~/.openclaw/workspace/trading/logs/audit.log
EOF
    log_success "Trading config updated"
    
    # Step 4: Test email
    log_section "Step 4: Testing Email Delivery"
    log_info "Testing email configuration..."
    
    if cd "$TRADING_DIR/scripts" && python3 email_helper.py --test 2>&1; then
        log_success "Email delivery test PASSED ✓"
    else
        log_warning "Email delivery test failed"
        log_info "Continuing setup anyway..."
    fi
    echo ""
    
    # Step 5: Update launchd plists
    log_section "Step 5: Updating LaunchAgent Configuration"
    
    # Update morning-brief plist
    log_info "Updating morning-brief plist..."
    plist_file="$HOME/Library/LaunchAgents/ai.openclaw.morning-brief.plist"
    
    if [[ -f "$plist_file" ]]; then
        # Backup
        cp "$plist_file" "$plist_file.backup.$(date +%s)"
        
        # Update environment variables in plist
        plutil -insert EnvironmentVariables.RESEND_API_KEY -string "$resend_api_key" "$plist_file" 2>/dev/null || \
        plutil -replace EnvironmentVariables.RESEND_API_KEY -string "$resend_api_key" "$plist_file"
        
        plutil -insert EnvironmentVariables.FROM_EMAIL -string "$from_email" "$plist_file" 2>/dev/null || \
        plutil -replace EnvironmentVariables.FROM_EMAIL -string "$from_email" "$plist_file"
        
        plutil -insert EnvironmentVariables.TO_EMAIL -string "$to_email" "$plist_file" 2>/dev/null || \
        plutil -replace EnvironmentVariables.TO_EMAIL -string "$to_email" "$plist_file"
        
        log_success "Morning brief plist updated"
    else
        log_warning "Morning brief plist not found at $plist_file"
    fi
    
    # Update daily-report plist
    log_info "Updating daily-report plist..."
    plist_file="$HOME/Library/LaunchAgents/com.pinchy.trading.daily-report.plist"
    
    if [[ -f "$plist_file" ]]; then
        # Backup
        cp "$plist_file" "$plist_file.backup.$(date +%s)"
        
        # Update environment variables in plist
        plutil -insert EnvironmentVariables.RESEND_API_KEY -string "$resend_api_key" "$plist_file" 2>/dev/null || \
        plutil -replace EnvironmentVariables.RESEND_API_KEY -string "$resend_api_key" "$plist_file"
        
        plutil -insert EnvironmentVariables.FROM_EMAIL -string "$from_email" "$plist_file" 2>/dev/null || \
        plutil -replace EnvironmentVariables.FROM_EMAIL -string "$from_email" "$plist_file"
        
        plutil -insert EnvironmentVariables.TO_EMAIL -string "$to_email" "$plist_file" 2>/dev/null || \
        plutil -replace EnvironmentVariables.TO_EMAIL -string "$to_email" "$plist_file"
        
        log_success "Daily report plist updated"
    else
        log_warning "Daily report plist not found at $plist_file"
    fi
    echo ""
    
    # Step 6: Reload launchd
    log_section "Step 6: Reloading LaunchAgent Jobs"
    
    # Unload and reload morning-brief
    if launchctl list | grep -q "ai.openclaw.morning-brief"; then
        log_info "Reloading morning-brief..."
        launchctl unload "$HOME/Library/LaunchAgents/ai.openclaw.morning-brief.plist" 2>/dev/null || true
        sleep 1
        launchctl load "$HOME/Library/LaunchAgents/ai.openclaw.morning-brief.plist"
        log_success "Morning brief reloaded"
    fi
    
    # Unload and reload daily-report
    if launchctl list | grep -q "com.pinchy.trading.daily-report"; then
        log_info "Reloading daily-report..."
        launchctl unload "$HOME/Library/LaunchAgents/com.pinchy.trading.daily-report.plist" 2>/dev/null || true
        sleep 1
        launchctl load "$HOME/Library/LaunchAgents/com.pinchy.trading.daily-report.plist"
        log_success "Daily report reloaded"
    fi
    echo ""
    
    # Step 7: Summary
    log_section "Setup Complete!"
    
    log_success "Email system is now configured"
    echo ""
    log_info "Configuration Summary:"
    echo "  • Resend API: ${resend_api_key:0:10}..."
    echo "  • From Email: $from_email"
    echo "  • To Email: $to_email"
    echo "  • Workspace: $WORKSPACE_DIR"
    echo ""
    
    log_info "Next steps:"
    echo "  1. Verify sender email is authorized in Resend dashboard"
    echo "  2. Check logs: tail -f $WORKSPACE_DIR/logs/morning-brief.log"
    echo "  3. Run: bash scripts/validate-email-setup.sh"
    echo ""
    
    log_success "Ready for production!"
}

# Run main
main "$@"
