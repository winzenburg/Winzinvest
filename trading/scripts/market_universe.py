#!/usr/bin/env python3
"""
Market Universe - Get S&P 500, Nasdaq 100, Russell 2000 constituents
"""

import logging

logger = logging.getLogger(__name__)

def get_sp500_tickers():
    """Get S&P 500 constituents"""
    import pandas as pd
    try:
        # Get from Wikipedia (most up-to-date)
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        df = tables[0]
        return df['Symbol'].str.replace('.', '-').tolist()
    except Exception as e:
        logger.warning("Error fetching S&P 500: %s", e)
        return []

def get_nasdaq100_tickers():
    """Get Nasdaq 100 constituents"""
    import pandas as pd
    try:
        url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        tables = pd.read_html(url)
        df = tables[4]  # The constituents table
        return df['Ticker'].str.replace('.', '-').tolist()
    except Exception as e:
        print(f"Error fetching Nasdaq 100: {e}")
        return []

def get_russell2000_sample():
    """Get Russell 2000 sample (top liquid names)
    Note: Full Russell 2000 list requires subscription. Using high-volume subset.
    """
    # High-volume Russell 2000 names (manually curated subset)
    return [
        'IWM',  # Russell 2000 ETF itself
        'CRWD', 'PLTR', 'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST',
        'MARA', 'RIOT', 'RBLX', 'PATH', 'DKNG', 'SNAP', 'DASH',
        'ABNB', 'UBER', 'LYFT', 'ZM', 'DOCU', 'NET', 'DDOG',
        'MDB', 'SNOW', 'U', 'TTD', 'ROKU', 'SQ', 'SHOP'
    ]

def get_major_etfs():
    """Get major ETFs worth scanning"""
    return [
        'SPY', 'QQQ', 'IWM', 'DIA',  # Major indices
        'XLK', 'XLF', 'XLE', 'XLV', 'XLI', 'XLP', 'XLY', 'XLU', 'XLB', 'XLRE',  # Sectors
        'GLD', 'SLV', 'TLT', 'HYG',  # Commodities & bonds
        'EEM', 'EWJ', 'FXI', 'EWZ',  # International
        'ARK', 'ARKK', 'ARKW'  # Innovation
    ]

def get_full_universe():
    """Get complete market universe for scanning"""
    logger.info("Building market universe...")

    sp500 = get_sp500_tickers()
    logger.info("  S&P 500: %d stocks", len(sp500))

    nasdaq100 = get_nasdaq100_tickers()
    logger.info("  Nasdaq 100: %d stocks", len(nasdaq100))

    russell_sample = get_russell2000_sample()
    logger.info("  Russell 2000 sample: %d stocks", len(russell_sample))

    etfs = get_major_etfs()
    logger.info("  Major ETFs: %d", len(etfs))

    universe = list(set(sp500 + nasdaq100 + russell_sample + etfs))
    logger.info("Total universe: %d symbols", len(universe))

    return universe

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
    universe = get_full_universe()
    print(f"Sample: {universe[:20]}")
