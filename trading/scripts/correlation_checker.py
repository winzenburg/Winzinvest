#!/usr/bin/env python3
"""
Position Correlation Checker
Warns if adding a new position would create high correlation risk
"""
import os, json, sys
from pathlib import Path

TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'

MAX_CORRELATION = 0.7  # Alert if correlation exceeds this

def get_open_positions():
    """Get list of currently open positions"""
    if not LOGS_DIR.exists():
        return []
    
    positions = []
    for log_file in LOGS_DIR.glob('*.json'):
        try:
            with open(log_file) as f:
                data = json.load(f)
                intent = data.get('intent', {})
                
                # Check if this is a stock trade (not options)
                if not intent.get('option_type') and intent.get('ticker'):
                    positions.append(intent.get('ticker'))
        except Exception:
            continue
    
    return list(set(positions))  # Unique tickers

def check_correlation(new_ticker, existing_positions):
    """
    Check correlation between new ticker and existing positions
    Returns: (ok: bool, warnings: list)
    """
    if not existing_positions:
        return True, []
    
    try:
        import yfinance as yf
        import pandas as pd
        import numpy as np
        
        # Download 60 days of data for all tickers
        all_tickers = existing_positions + [new_ticker]
        data = yf.download(all_tickers, period='60d', progress=False)['Close']
        
        if data.empty:
            return True, ["Correlation check failed: no price data"]
        
        # Calculate daily returns
        returns = data.pct_change().dropna()
        
        # Calculate correlation matrix
        corr_matrix = returns.corr()
        
        # Check correlation of new ticker with existing positions
        warnings = []
        for existing in existing_positions:
            if existing in corr_matrix.index and new_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[existing, new_ticker]
                
                if abs(corr) > MAX_CORRELATION:
                    warnings.append(f"{new_ticker} highly correlated with {existing}: {corr:.2f}")
        
        ok = len(warnings) == 0
        return ok, warnings
        
    except Exception as e:
        # If check fails, allow trade (fail open)
        return True, [f"Correlation check failed: {e}"]

def main():
    if len(sys.argv) < 2:
        print("Usage: correlation_checker.py <ticker>")
        sys.exit(1)
    
    new_ticker = sys.argv[1]
    open_positions = get_open_positions()
    
    print(f"Checking correlation for {new_ticker}")
    print(f"Open positions: {', '.join(open_positions) if open_positions else 'None'}")
    
    ok, warnings = check_correlation(new_ticker, open_positions)
    
    if warnings:
        print("\n⚠️ Correlation warnings:")
        for w in warnings:
            print(f"  - {w}")
    
    if not ok:
        print(f"\n❌ High correlation detected (>{MAX_CORRELATION})")
        sys.exit(1)
    else:
        print("\n✅ Correlation acceptable")
        sys.exit(0)

if __name__ == '__main__':
    main()
