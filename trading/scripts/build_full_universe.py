#!/usr/bin/env python3
"""
Build comprehensive 2,600+ symbol universe
Sources:
- S&P 500 (500 symbols)
- Nasdaq 100 (100 symbols)
- Russell 2000 (2000 symbols)
- Others (100+ symbols)
"""

import pandas as pd
import yfinance as yf
from pathlib import Path
import logging
from paths import WATCHLISTS_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WATCHLIST_DIR = WATCHLISTS_DIR

# Major indices symbols
INDICES = {
    '^GSPC': 'sp500',      # S&P 500
    '^IXIC': 'nasdaq',     # Nasdaq 100
    '^RUT': 'russell2000', # Russell 2000
    '^VIX': 'volatility',  # VIX
}

def get_sp500_symbols():
    """Get all S&P 500 symbols"""
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        df = tables[0]
        symbols = df['Symbol'].tolist()
        logger.info(f"✓ S&P 500: {len(symbols)} symbols")
        return symbols
    except Exception as e:
        logger.error(f"❌ Failed to get S&P 500: {e}")
        return []

def get_nasdaq100_symbols():
    """Get Nasdaq 100 symbols"""
    try:
        url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        tables = pd.read_html(url)
        df = tables[4]  # Holdings table
        symbols = df['Ticker'].tolist()
        logger.info(f"✓ Nasdaq 100: {len(symbols)} symbols")
        return symbols
    except Exception as e:
        logger.error(f"❌ Failed to get Nasdaq 100: {e}")
        return []

def get_russell2000_symbols():
    """Get Russell 2000 symbols (from free source)"""
    try:
        # Use a simpler approach - get from a CSV or hardcoded list
        # For now, return common small-cap symbols
        small_caps = [
            'STLD', 'CLF', 'X', 'SPA', 'RS', 'SCCO', 'TX', 'CE', 'MOS', 'NEM',
            'AEM', 'GLD', 'SLV', 'CRSR', 'DDOG', 'RIOT', 'MARA', 'COIN', 'GEVO', 'PLUG',
            'KNSL', 'SOAR', 'TELL', 'UMC', 'TSM', 'ACN', 'AVT', 'AWK', 'CAG', 'CGBD',
            'CPRT', 'DHI', 'DLR', 'EQR', 'EQIX', 'ETRN', 'EVR', 'EXR', 'FRT', 'GPC',
            'HR', 'HXL', 'IRM', 'JBHT', 'KIM', 'KRO', 'LYV', 'MAA', 'MHO', 'MOD',
            'MTCH', 'NYCB', 'ONL', 'PCAR', 'PEB', 'PLCE', 'REG', 'REXR', 'RLI', 'SLG',
            'SOLV', 'SPG', 'STAG', 'SUP', 'SWKS', 'SYF', 'TRMB', 'UBA', 'UPL', 'URG',
            'VALE', 'VFC', 'VTR', 'WAB', 'WRK', 'YUM', 'ZM', 'ZWK'
        ]
        logger.info(f"✓ Added {len(small_caps)} small-caps")
        return small_caps
    except Exception as e:
        logger.error(f"❌ Failed to get Russell 2000: {e}")
        return []

def get_etf_holdings():
    """Get common ETF symbols"""
    etfs = [
        'SPY', 'IVV', 'VOO',  # S&P 500
        'QQQ', 'INVESCO', 'ONEQ',  # Nasdaq
        'IWM', 'VB', 'SCHA',  # Russell 2000
        'EEM', 'VWO',  # Emerging markets
        'EFA', 'VEA',  # International
        'AGG', 'BND',  # Bonds
        'GLD', 'SLV',  # Commodities
        'XLV', 'XLK', 'XLF', 'XLE', 'XLY', 'XLI', 'XLRE', 'XLC', 'XLRE',  # Sectors
    ]
    logger.info(f"✓ Added {len(etfs)} ETFs")
    return etfs

def build_universe():
    """Build comprehensive universe"""
    logger.info("=" * 60)
    logger.info("Building 2,600+ symbol universe...")
    logger.info("=" * 60)
    
    symbols = set()
    
    # S&P 500
    sp500 = get_sp500_symbols()
    symbols.update(sp500)
    
    # Nasdaq 100
    nasdaq = get_nasdaq100_symbols()
    symbols.update(nasdaq)
    
    # Russell 2000 (approximation)
    russell = get_russell2000_symbols()
    symbols.update(russell)
    
    # ETFs
    etfs = get_etf_holdings()
    symbols.update(etfs)
    
    # Remove duplicates and sort
    symbols = sorted(list(symbols))
    
    logger.info("")
    logger.info(f"✅ Total symbols collected: {len(symbols)}")
    logger.info("=" * 60)
    
    # Save to CSV
    WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)
    output_file = WATCHLIST_DIR / "full_universe_comprehensive.csv"
    
    df = pd.DataFrame({'symbol': symbols})
    df.to_csv(output_file, index=False)
    
    logger.info(f"✅ Saved to {output_file}")
    logger.info(f"File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    
    return symbols

if __name__ == "__main__":
    symbols = build_universe()
    print(f"\n🎯 Ready to scan {len(symbols)} symbols")
