#!/usr/bin/env python3
"""
Entry Validator - Pre-Trade Risk Checks
Integrated with webhook_listener.py
Checks:
1. Will this push any sector > 20%?
2. Is this correlated > 0.7 with existing holdings?
Blocks entry or recommends size reduction
"""

import json
import logging
from pathlib import Path
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TRADING_DIR = Path(__file__).resolve().parents[0]

# Import sector and correlation monitors
try:
    from sector_monitor import (
        get_sector, 
        get_open_positions as get_sector_positions,
        calculate_sector_allocation,
        MAX_SECTOR_ALLOCATION,
        ALERT_THRESHOLD
    )
    SECTOR_MONITOR_AVAILABLE = True
except ImportError:
    SECTOR_MONITOR_AVAILABLE = False
    logger.warning("sector_monitor not available")

try:
    from correlation_monitor import (
        get_open_positions as get_correlation_positions,
        calculate_correlation_matrix,
        identify_correlated_pairs,
        HIGH_CORRELATION_THRESHOLD
    )
    CORRELATION_MONITOR_AVAILABLE = True
except ImportError:
    CORRELATION_MONITOR_AVAILABLE = False
    logger.warning("correlation_monitor not available")

class EntryValidationResult:
    """Result of entry validation check"""
    def __init__(self, allowed=True, checks=None):
        self.allowed = allowed
        self.checks = checks or []
        self.violations = []
        self.warnings = []
    
    def add_violation(self, message):
        """Add a hard violation (blocks entry)"""
        self.violations.append(message)
        self.allowed = False
    
    def add_warning(self, message):
        """Add a warning (allows entry but flags risk)"""
        self.warnings.append(message)
    
    def to_dict(self):
        return {
            'allowed': self.allowed,
            'violations': self.violations,
            'warnings': self.warnings,
            'checks_performed': self.checks
        }

def check_sector_limits(ticker, proposed_size=1.0):
    """
    Check 1: Will this position exceed sector limits?
    
    Returns: (allowed: bool, sector: str, message: str, current_pct: float, would_be_pct: float)
    """
    if not SECTOR_MONITOR_AVAILABLE:
        return True, 'Unknown', 'Sector check unavailable', 0, 0
    
    try:
        sector = get_sector(ticker)
        current_positions = get_sector_positions()
        
        # Simulate adding the position
        test_positions = current_positions.copy()
        if ticker not in test_positions:
            test_positions[ticker] = {'quantity': 0, 'value': 0}
        test_positions[ticker]['value'] += proposed_size
        
        allocation = calculate_sector_allocation(test_positions)
        
        if sector not in allocation:
            return True, sector, f"✅ {sector} sector fresh", 0, 0
        
        pct = allocation[sector]['pct']
        current_pct = allocation.get(sector, {}).get('pct', 0)
        
        if pct > MAX_SECTOR_ALLOCATION:
            msg = f"❌ BLOCKED: {sector} would be {pct*100:.1f}% (limit {MAX_SECTOR_ALLOCATION*100:.0f}%)"
            return False, sector, msg, current_pct, pct
        
        if pct > ALERT_THRESHOLD:
            msg = f"⚠️ WARNING: {sector} would be {pct*100:.1f}% (approaching {MAX_SECTOR_ALLOCATION*100:.0f}% limit)"
            return True, sector, msg, current_pct, pct
        
        return True, sector, f"✅ OK: {sector} would be {pct*100:.1f}%", current_pct, pct
    
    except Exception as e:
        logger.error(f"Error in sector check: {e}")
        return True, 'Unknown', f"Sector check failed: {e}", 0, 0

def check_correlation_risk(ticker, threshold=HIGH_CORRELATION_THRESHOLD):
    """
    Check 2: Is this correlated > threshold with existing positions?
    
    Returns: (allowed: bool, correlated_tickers: list, message: str)
    """
    if not CORRELATION_MONITOR_AVAILABLE:
        return True, [], 'Correlation check unavailable'
    
    try:
        open_tickers = get_correlation_positions()
        
        if len(open_tickers) == 0:
            return True, [], f"✅ No existing positions to correlate with"
        
        # Add new ticker to check
        tickers_to_check = open_tickers.union({ticker})
        
        corr_matrix, _ = calculate_correlation_matrix(tickers_to_check)
        
        if corr_matrix.empty:
            return True, [], "Correlation data unavailable"
        
        # Check correlations with new ticker
        correlated_with = []
        
        if ticker in corr_matrix.columns:
            for existing in open_tickers:
                if existing in corr_matrix.columns and ticker in corr_matrix.index:
                    corr = corr_matrix.loc[ticker, existing]
                    
                    if abs(corr) > threshold:
                        correlated_with.append({
                            'ticker': existing,
                            'correlation': float(corr)
                        })
        
        if correlated_with:
            # High correlation - but don't block, just warn
            # User can choose to enter with reduced size
            sorted_corr = sorted(correlated_with, key=lambda x: abs(x['correlation']), reverse=True)
            pairs_str = ', '.join([f"{t['ticker']}({t['correlation']:.2f})" for t in sorted_corr[:3]])
            msg = f"⚠️ WARNING: {ticker} correlated {pairs_str}"
            
            # Only block if extremely correlated (>0.85)
            if any(abs(c['correlation']) > 0.85 for c in correlated_with):
                msg = f"❌ BLOCKED: {ticker} highly correlated (>0.85) with existing holdings"
                return False, correlated_with, msg
            
            return True, correlated_with, msg
        
        return True, [], f"✅ Low correlation with existing holdings"
    
    except Exception as e:
        logger.error(f"Error in correlation check: {e}")
        return True, [], f"Correlation check failed: {e}"

def validate_entry(ticker, size=1.0):
    """
    Comprehensive entry validation
    Performs all pre-entry checks
    
    Args:
        ticker: Symbol to validate
        size: Position size (used for sector calculation)
    
    Returns:
        EntryValidationResult object
    """
    result = EntryValidationResult(checks=['sector_limits', 'correlation'])
    
    logger.info(f"Validating entry: {ticker} (size={size})")
    
    # Check 1: Sector limits
    sector_ok, sector, sector_msg, current_sector_pct, would_be_pct = check_sector_limits(ticker, size)
    
    if sector_ok:
        if 'WARNING' in sector_msg:
            result.add_warning(sector_msg)
        logger.info(sector_msg)
    else:
        result.add_violation(sector_msg)
        logger.error(sector_msg)
    
    # Check 2: Correlation risk
    corr_ok, correlated_tickers, corr_msg = check_correlation_risk(ticker)
    
    if corr_ok:
        if 'WARNING' in corr_msg:
            result.add_warning(corr_msg)
        logger.info(corr_msg)
    else:
        result.add_violation(corr_msg)
        logger.error(corr_msg)
    
    # Summary
    if result.allowed:
        logger.info(f"✅ Entry validation PASSED for {ticker}")
    else:
        logger.error(f"❌ Entry validation FAILED for {ticker}")
    
    return result

def format_entry_check_message(ticker, result, size=1.0):
    """Format validation result as alert message"""
    lines = [f"🔍 *ENTRY VALIDATION: {ticker}*\n"]
    
    if result.allowed:
        lines.append("✅ *ENTRY ALLOWED*\n")
    else:
        lines.append("❌ *ENTRY BLOCKED*\n")
    
    if result.violations:
        lines.append("*VIOLATIONS:*")
        for v in result.violations:
            lines.append(f"  ❌ {v}")
        lines.append("")
    
    if result.warnings:
        lines.append("*WARNINGS:*")
        for w in result.warnings:
            lines.append(f"  ⚠️ {w}")
        lines.append("")
    
    if result.allowed and result.warnings:
        lines.append("_Entry allowed but consider reducing size or using smaller position._")
    
    return "\n".join(lines)

# CLI usage
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: entry_validator.py <ticker> [size]")
        sys.exit(1)
    
    ticker = sys.argv[1].upper()
    size = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    
    result = validate_entry(ticker, size)
    
    print(json.dumps(result.to_dict(), indent=2))
    
    sys.exit(0 if result.allowed else 1)
