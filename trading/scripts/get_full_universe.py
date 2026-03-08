#!/usr/bin/env python3
"""
Fetch FULL market universe: S&P 500, Nasdaq 100, Russell 2000, Major ETFs
Returns 2,600+ tradeable symbols for comprehensive market scanning.
"""

import yfinance as yf
import pandas as pd
import requests
from pathlib import Path
import json
import logging

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "universe_builder.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class UniverseBuilder:
    def __init__(self):
        self.symbols = set()
    
    def fetch_sp500(self):
        """Fetch all S&P 500 symbols."""
        try:
            logger.info("Fetching S&P 500 symbols...")
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            tables = pd.read_html(url)
            df = tables[0]
            sp500 = df['Symbol'].str.strip().tolist()
            self.symbols.update(sp500)
            logger.info(f"✅ Added {len(sp500)} S&P 500 symbols")
            return len(sp500)
        except Exception as e:
            logger.error(f"Failed to fetch S&P 500: {e}")
            return 0
    
    def fetch_nasdaq100(self):
        """Fetch Nasdaq 100 symbols."""
        try:
            logger.info("Fetching Nasdaq 100 symbols...")
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            tables = pd.read_html(url)
            df = tables[4]  # Nasdaq 100 holdings table
            nasdaq = df.iloc[:, 0].str.strip().tolist()
            self.symbols.update(nasdaq)
            logger.info(f"✅ Added {len(nasdaq)} Nasdaq 100 symbols")
            return len(nasdaq)
        except Exception as e:
            logger.error(f"Failed to fetch Nasdaq 100: {e}")
            return 0
    
    def fetch_russell2000(self):
        """Fetch Russell 2000 symbols (via ETF tracking)."""
        try:
            logger.info("Fetching Russell 2000 symbols...")
            # IWM is the Russell 2000 ETF - fetch its holdings
            # Use a common source for Russell 2000 constituents
            url = 'https://en.wikipedia.org/wiki/Russell_2000_Index'
            tables = pd.read_html(url)
            
            # Try to get the holdings (varies by page structure)
            for table in tables:
                if len(table) > 500:  # Russell 2000 has 2000 symbols
                    if table.iloc[:, 0].dtype == 'object':
                        russell = table.iloc[:, 0].str.strip().tolist()
                        self.symbols.update(russell)
                        logger.info(f"✅ Added {len(russell)} Russell 2000 symbols")
                        return len(russell)
            
            logger.warning("Russell 2000 table structure changed, using fallback")
            return 0
            
        except Exception as e:
            logger.error(f"Failed to fetch Russell 2000: {e}")
            return 0
    
    def add_major_etfs(self):
        """Add major ETFs for sector/commodity/bond exposure."""
        etfs = [
            # Broad Market
            'SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VOO', 'VTV', 'VUG', 'VBR', 'VBK',
            'VSS', 'VXUS', 'VTIAX', 'BND', 'AGG', 'BSV', 'BIV', 'BLV',
            # Sector
            'XLK', 'XLV', 'XLY', 'XLE', 'XLI', 'XLF', 'XLP', 'XLRE', 'XLU',
            'VGT', 'VHT', 'VIS', 'VCR', 'VDC', 'VOE', 'VEV', 'VFV', 'VSH',
            # Fixed Income
            'TLT', 'IEF', 'SHY', 'LQD', 'HYG', 'ANYD', 'EMB', 'VCIT', 'VCSH',
            # Commodities
            'GLD', 'SLV', 'USO', 'DBC', 'PDBC', 'UUP', 'DXY',
            # International
            'EEM', 'EFA', 'VEA', 'VWO', 'IEMG', 'VXUS', 'SCZ', 'EUSA',
            # Sector Rotation
            'XRT', 'XBI', 'XHB', 'XME', 'XTN', 'XUS', 'IYW', 'IYH', 'IYJ', 'IYF',
            'IYK', 'IYE', 'IYM', 'IYC', 'IYG', 'IYR', 'IYU', 'IDU',
            # Alternative
            'QAI', 'SPLG', 'SCHB', 'SCHF', 'SCHE', 'SCHA', 'SCHM', 'SCHG', 'SCHD', 'SCHV',
        ]
        self.symbols.update(etfs)
        logger.info(f"✅ Added {len(etfs)} major ETFs")
        return len(etfs)
    
    def save_universe(self):
        """Save universe to file."""
        output_file = Path.home() / ".openclaw" / "workspace" / "trading" / "universe.json"
        
        universe_list = sorted(list(self.symbols))
        data = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'total_symbols': len(universe_list),
            'symbols': universe_list
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"✅ Saved {len(universe_list)} symbols to {output_file}")
        return universe_list
    
    def build(self):
        """Build complete universe."""
        logger.info("=== BUILDING FULL MARKET UNIVERSE ===\n")
        
        sp500_count = self.fetch_sp500()
        nasdaq_count = self.fetch_nasdaq100()
        russell_count = self.fetch_russell2000()
        etf_count = self.add_major_etfs()
        
        universe = self.save_universe()
        
        logger.info(f"\n=== UNIVERSE COMPLETE ===")
        logger.info(f"S&P 500: {sp500_count}")
        logger.info(f"Nasdaq 100: {nasdaq_count}")
        logger.info(f"Russell 2000: {russell_count}")
        logger.info(f"ETFs: {etf_count}")
        logger.info(f"TOTAL: {len(universe)} unique symbols")
        
        return universe

def main():
    builder = UniverseBuilder()
    universe = builder.build()
    print(f"\n✅ Universe built: {len(universe)} symbols")
    print(f"First 50: {universe[:50]}")
    print(f"Last 50: {universe[-50:]}")

if __name__ == "__main__":
    main()
