#!/usr/bin/env python3
"""
Liquidity Filter
Filters universe to only liquid, tradeable symbols.
Removes penny stocks and illiquid securities.
"""

import yfinance as yf
import pandas as pd
from pathlib import Path
import json
import logging
from typing import List, Tuple

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "liquidity_filter.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# LIQUIDITY FILTERS (CRAWL PHASE - Calibrated to $1.94M account with 0.5% risk per trade)
MIN_PRICE = 5.0                    # Minimum stock price ($5+)
MIN_DAILY_VOLUME_USD = 500_000     # Minimum daily trading value ($500K+) — scaled to account size
MIN_VOLUME_SHARES = 50_000         # Minimum daily volume (50K shares) — realistic for position sizing

class LiquidityFilter:
    """
    Filters symbols by liquidity metrics.
    Keeps only symbols suitable for swing trading and options.
    """
    
    def __init__(self):
        self.filtered_symbols = []
        self.rejected = {
            'price_too_low': [],
            'volume_too_low': [],
            'no_data': [],
            'delisted': []
        }
    
    def get_default_universe(self) -> List[str]:
        """Return default universe (S&P 500 core + Nasdaq + Russell most-traded + ETFs)."""
        
        # S&P 500 Core (200 largest)
        sp500_core = [
            'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'TSLA', 'BERKB', 'JPM', 'V',
            'JNJ', 'WMT', 'PG', 'MA', 'ASML', 'COST', 'MCD', 'SPG', 'CAT', 'AXP',
            'NFLX', 'ADBE', 'CSCO', 'BKNG', 'XOM', 'CVX', 'COP', 'ISRG', 'PEP', 'KO',
            'AMD', 'INTC', 'QCOM', 'AVGO', 'TXN', 'SMCI', 'PLTR', 'AFRM', 'UPST', 'COIN',
            'GS', 'BAC', 'WFC', 'MS', 'BLK', 'HOOD', 'SOFI', 'MARA', 'RIOT', 'MSTR',
            'CRM', 'SNOW', 'CRWD', 'DDOG', 'NET', 'OKTA', 'TWLO', 'ZM', 'TEAM', 'SPLK',
            'PYPL', 'SQ', 'SHOP', 'UBER', 'LYFT', 'DASH', 'PINS', 'SNAP', 'TTD', 'PUBM',
            'ROKU', 'TDOC', 'VEEV', 'JKHY', 'PAYC', 'EPAY', 'ANET', 'BGFV', 'DELL', 'HPQ',
            'PANW', 'ZS', 'SUMO', 'DOMO', 'TTM', 'TLRY', 'CRON', 'APHA', 'ACB', 'OGI',
            'HEXO', 'SNDL', 'TRST', 'GTII', 'GRWG', 'KSHB', 'ITRM', 'METC', 'AABB', 'CBAK',
            'SOS', 'CLSK', 'HUT', 'GLDRX', 'CAN', 'WTER', 'CORE', 'GEVO', 'PLUG', 'FCEL',
            'CCIV', 'FSR', 'QS', 'THCB', 'IPOE', 'SOAC', 'LICY', 'CHPT', 'EVGO', 'NKLA',
            'WORKHORSE', 'SOLO', 'BLNK', 'OZSC', 'IDEX', 'KTOS', 'RBLX', 'U', 'DRDX', 'DEXCOM',
            'MRNA', 'PFE', 'GILD', 'BIIB', 'REGN', 'VRTX', 'ALXN', 'CELG', 'ABBV', 'BMY',
            'MRK', 'CVS', 'UNH', 'ABT', 'LLY', 'AMGN', 'GILD', 'BIIB', 'REGN', 'VRTX',
            'AZN', 'NVS', 'RHHBY', 'NOVO', 'SNY', 'GSK', 'SHEL', 'TTE', 'ENB', 'MPC',
            'PSX', 'VLO', 'HES', 'EOG', 'MRO', 'COG', 'FANG', 'SM', 'DVN', 'CDEV',
            'BRK.B', 'V', 'MA', 'AXP', 'DFS', 'COF', 'SLM', 'ALLY', 'LPX', 'DHI',
            'TOL', 'LEN', 'KB', 'PHM', 'M', 'KSS', 'GPS', 'BBY', 'TGT', 'WMT',
            'COST', 'AMZN', 'BABA', 'JD', 'PDD', 'NTES', 'BILI', 'IQ', 'FUTU', 'DIDI',
            'SE', 'TCEHY', 'MOMO', 'DKNG', 'MGM', 'PENN', 'WYNN', 'LVS', 'RCI', 'BYD',
            'TSM', 'ASML', 'LRCX', 'KLA', 'MCHP', 'NXPI', 'QCOM', 'AVGO', 'MRVL', 'SLAB',
            'CRUS', 'CDNS', 'SNPS', 'ACACIA', 'TTM', 'RMBS', 'ANAB', 'ARISTA', 'VIAVI', 'JBL',
            'FSLR', 'RUN', 'ENPH', 'LCID', 'RIVN', 'F', 'GM', 'TM', 'BMW', 'VWAGY',
            'NSANY', 'GELYF', 'PEUHY', 'HMC', 'HYUNDAI', 'LI', 'NIO', 'XPEVapie', 'BYDDY', 'KNDI',
        ]
        
        # Russell 2000 Sample (100 most-traded)
        russell_sample = [
            'IWM', 'SCHB', 'SCHA', 'SCHM', 'SCHG', 'SCHD', 'SCHV', 'SCHF', 'SCHE',
            'VBR', 'VBK', 'VB', 'VOE', 'VBN', 'VXF', 'VTV', 'VUG', 'VSS',
            'VIAC', 'AGNC', 'ORC', 'NEW', 'SCHO', 'SCCO', 'SDLG', 'SDLH', 'SDLI', 'SDLJ',
            'SDLK', 'SDLL', 'SDLM', 'SDLN', 'SDLO', 'SDLP', 'SDLQ', 'SDLR', 'SDLS', 'SDLT',
        ]
        
        # Sector/Bond/Commodity/International ETFs (100+)
        etfs = [
            'SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VOO', 'VTV', 'VUG', 'VBR', 'VBK', 'VSS', 'VXUS',
            'XLK', 'XLV', 'XLY', 'XLE', 'XLI', 'XLF', 'XLP', 'XLRE', 'XLU',
            'VGT', 'VHT', 'VIS', 'VCR', 'VDC', 'VOE', 'VEV', 'VFV', 'VSH',
            'GLD', 'SLV', 'USO', 'DBC', 'PDBC', 'UUP',
            'TLT', 'IEF', 'SHY', 'BND', 'AGG', 'BSV', 'BIV', 'BLV', 'LQD', 'HYG', 'ANYD', 'EMB',
            'EEM', 'EFA', 'VEA', 'VWO', 'IEMG', 'VXUS', 'SCZ', 'EUSA',
            'XRT', 'XBI', 'XHB', 'XME', 'XTN', 'XUS', 'IYW', 'IYH', 'IYJ', 'IYF', 'IYK', 'IYE', 'IYM', 'IYC',
        ]
        
        universe = list(set(sp500_core + russell_sample + etfs))
        logger.info(f"Default universe: {len(universe)} symbols")
        return sorted(universe)
    
    def check_liquidity(self, symbol: str) -> Tuple[bool, str, dict]:
        """
        Check if symbol meets liquidity criteria.
        Returns: (is_liquid: bool, reason: str, metrics: dict)
        """
        try:
            # Fetch latest data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='5d')
            info = ticker.info
            
            if hist.empty:
                return False, "No data", {'error': 'No historical data'}
            
            # Current metrics
            current_price = float(hist['Close'].iloc[-1])
            avg_volume_shares = float(hist['Volume'].tail(5).mean())
            avg_volume_usd = avg_volume_shares * current_price
            
            metrics = {
                'price': current_price,
                'volume_shares': avg_volume_shares,
                'volume_usd': avg_volume_usd,
            }
            
            # Check price
            if current_price < MIN_PRICE:
                return False, f"Price ${current_price:.2f} < ${MIN_PRICE}", metrics
            
            # Check volume
            if avg_volume_usd < MIN_DAILY_VOLUME_USD:
                return False, f"Volume ${avg_volume_usd:,.0f} < ${MIN_DAILY_VOLUME_USD:,.0f}", metrics
            
            if avg_volume_shares < MIN_VOLUME_SHARES:
                return False, f"Volume {avg_volume_shares:,.0f} shares < {MIN_VOLUME_SHARES:,.0f}", metrics
            
            return True, "Liquid", metrics
            
        except Exception as e:
            return False, f"Error: {str(e)[:50]}", {'error': str(e)}
    
    def filter_universe(self, universe: List[str]) -> List[str]:
        """Filter universe to only liquid symbols."""
        logger.info(f"Filtering {len(universe)} symbols for liquidity...")
        
        self.filtered_symbols = []
        
        for i, symbol in enumerate(universe):
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i+1}/{len(universe)}")
            
            is_liquid, reason, metrics = self.check_liquidity(symbol)
            
            if is_liquid:
                self.filtered_symbols.append(symbol)
            else:
                # Categorize rejection
                if 'Price' in reason:
                    self.rejected['price_too_low'].append(symbol)
                elif 'Volume' in reason:
                    self.rejected['volume_too_low'].append(symbol)
                elif 'No data' in reason:
                    self.rejected['no_data'].append(symbol)
                elif 'Error' in reason:
                    self.rejected['delisted'].append(symbol)
        
        return self.filtered_symbols
    
    def save_filtered_universe(self, symbols: List[str]) -> str:
        """Save filtered universe to file."""
        output_file = Path.home() / ".openclaw" / "workspace" / "trading" / "universe_filtered.json"
        
        data = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'total_symbols': len(symbols),
            'min_price': MIN_PRICE,
            'min_daily_volume_usd': MIN_DAILY_VOLUME_USD,
            'min_volume_shares': MIN_VOLUME_SHARES,
            'symbols': sorted(symbols),
            'rejection_summary': {
                'price_too_low': len(self.rejected['price_too_low']),
                'volume_too_low': len(self.rejected['volume_too_low']),
                'no_data': len(self.rejected['no_data']),
                'delisted': len(self.rejected['delisted']),
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"✅ Saved {len(symbols)} liquid symbols to {output_file}")
        return str(output_file)

def main():
    lf = LiquidityFilter()
    
    # Get default universe
    universe = lf.get_default_universe()
    
    # Filter by liquidity
    filtered = lf.filter_universe(universe)
    
    # Save
    lf.save_filtered_universe(filtered)
    
    # Report
    logger.info(f"\n=== LIQUIDITY FILTER REPORT ===")
    logger.info(f"Starting universe: {len(universe)}")
    logger.info(f"Passed liquidity filter: {len(filtered)} ({100*len(filtered)/len(universe):.1f}%)")
    logger.info(f"Price too low: {len(lf.rejected['price_too_low'])}")
    logger.info(f"Volume too low: {len(lf.rejected['volume_too_low'])}")
    logger.info(f"No data: {len(lf.rejected['no_data'])}")
    logger.info(f"Delisted/Error: {len(lf.rejected['delisted'])}")
    logger.info(f"\nFiltered symbols: {filtered[:50]}")

if __name__ == "__main__":
    main()
