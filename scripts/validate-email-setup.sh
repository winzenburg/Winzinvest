#!/bin/bash

# OpenClaw Email Setup Validation Script
# ======================================
#
# Run this monthly to ensure email system is still configured correctly
# Checks: API key, domain, environment variables, and launchd jobs
#
# Usage: bash scripts/validate-email-setup.sh

set -e

WORKSPACE_DIR="${WORKSPACE_DIR:=$HOME/.openclaw/workspace}"
TRADING_DIR="$WORKSPACE_DIR/trading"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((CHECKS_PASSED++))
}

log_fail() {
    echo -e "${RED}[✗]${NC} $1"
    ((CHECKS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
    ((CHECKS_WARNING++))
}

log_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Main validation
main() {
    log_section "OpenClaw Email System Validation"
    log_info "Workspace: $WORKSPACE_DIR"
    log_info "Running: $(date)"
    echo ""
    
    # Check 1: .env files exist
    log_section "Check 1: Environment Files"
    
    if [[ -f "$WORKSPACE_DIR/.env" ]]; then
        log_pass ".env file exists"
    else
        log_fail ".env file missing at $WORKSPACE_DIR/.env"
    fi
    
    if [[ -f "$TRADING_DIR/.env" ]]; then
        log_pass "trading/.env file exists"
    else
        log_fail "trading/.env missing at $TRADING_DIR/.env"
    fi
    
    # Check 2: Required environment variables
    log_section "Check 2: Environment Variables"
    
    # Load .env files
    if [[ -f "$WORKSPACE_DIR/.env" ]]; then
        source "$WORKSPACE_DIR/.env"
    fi
    if [[ -f "$TRADING_DIR/.env" ]]; then
        source "$TRADING_DIR/.env"
    fi
    
    # Check RESEND_API_KEY
    if [[ -n "$RESEND_API_KEY" ]]; then
        if [[ $RESEND_API_KEY =~ ^re_ ]]; then
            log_pass "RESEND_API_KEY configured (${RESEND_API_KEY:0:10}...)"
        else
            log_fail "RESEND_API_KEY has invalid format (should start with 're_')"
        fi
    else
        log_fail "RESEND_API_KEY not set"
    fi
    
    # Check FROM_EMAIL
    if [[ -n "$FROM_EMAIL" ]]; then
        if [[ $FROM_EMAIL =~ @.*\. ]]; then
            log_pass "FROM_EMAIL configured ($FROM_EMAIL)"
        else
            log_fail "FROM_EMAIL has invalid format ($FROM_EMAIL)"
        fi
    else
        log_fail "FROM_EMAIL not set"
    fi
    
    # Check TO_EMAIL
    if [[ -n "$TO_EMAIL" ]]; then
        if [[ $TO_EMAIL =~ @.*\. ]]; then
            log_pass "TO_EMAIL configured ($TO_EMAIL)"
        else
            log_fail "TO_EMAIL has invalid format ($TO_EMAIL)"
        fi
    else
        log_fail "TO_EMAIL not set"
    fi
    
    # Check TELEGRAM_BOT_TOKEN
    if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
        log_pass "TELEGRAM_BOT_TOKEN configured"
    else
        log_warning "TELEGRAM_BOT_TOKEN not set (optional)"
    fi
    
    # Check 3: Python dependencies
    log_section "Check 3: Python Dependencies"
    
    if python3 -c "import requests" 2>/dev/null; then
        log_pass "Python 'requests' module available"
    else
        log_warning "Python 'requests' module not found (install: pip3 install requests)"
    fi
    
    # Check 4: Script files
    log_section "Check 4: Script Files"
    
    scripts=(
        "$TRADING_DIR/scripts/email_helper.py"
        "$TRADING_DIR/scripts/daily_portfolio_report.py"
        "$TRADING_DIR/scripts/regime_alert.py"
        "$WORKSPACE_DIR/scripts/morning-brief.mjs"
    )
    
    for script in "${scripts[@]}"; do
        if [[ -f "$script" ]]; then
            log_pass "$(basename $script) found"
        else
            log_fail "$(basename $script) missing at $script"
        fi
    done
    
    # Check 5: LaunchAgent plists
    log_section "Check 5: LaunchAgent Configuration"
    
    plist_files=(
        "$HOME/Library/LaunchAgents/ai.openclaw.morning-brief.plist"
        "$HOME/Library/LaunchAgents/com.pinchy.trading.daily-report.plist"
    )
    
    for plist in "${plist_files[@]}"; do
        name=$(basename "$plist")
        if [[ -f "$plist" ]]; then
            # Check if loaded
            if launchctl list | grep -q "$(basename $plist .plist)"; then
                log_pass "$name is loaded"
            else
                log_warning "$name exists but not loaded (run: launchctl load $plist)"
            fi
        else
            log_warning "$name missing at $plist"
        fi
    done
    
    # Check 6: Log directories
    log_section "Check 6: Log Directories"
    
    if [[ -d "$WORKSPACE_DIR/logs" ]]; then
        log_pass "Workspace logs directory exists"
    else
        log_warning "Creating logs directory at $WORKSPACE_DIR/logs"
        mkdir -p "$WORKSPACE_DIR/logs"
    fi
    
    if [[ -d "$TRADING_DIR/logs" ]]; then
        log_pass "Trading logs directory exists"
    else
        log_warning "Creating logs directory at $TRADING_DIR/logs"
        mkdir -p "$TRADING_DIR/logs"
    fi
    
    # Check 7: Email delivery test (optional, can be slow)
    log_section "Check 7: Email Delivery Test (Optional)"
    
    read -p "Run email delivery test? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Testing email delivery..."
        if cd "$TRADING_DIR/scripts" && python3 email_helper.py --test 2>&1; then
            log_pass "Email delivery test passed"
        else
            log_fail "Email delivery test failed"
        fi
    fi
    
    # Summary
    log_section "Validation Summary"
    
    echo -e "${GREEN}Passed: $CHECKS_PASSED${NC}"
    echo -e "${YELLOW}Warnings: $CHECKS_WARNING${NC}"
    
    if [[ $CHECKS_FAILED -gt 0 ]]; then
        echo -e "${RED}Failed: $CHECKS_FAILED${NC}"
        echo ""
        log_warning "Some checks failed. Review configuration and re-run setup."
        echo ""
        log_info "For help: bash scripts/setup-email-config.sh"
        exit 1
    else
        echo ""
        log_pass "All critical checks passed!"
        echo ""
        log_info "Email system is ready for production"
        exit 0
    fi
}

# Run main
main "$@"
