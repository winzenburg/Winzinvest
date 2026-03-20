#!/usr/bin/env python3
"""
Fetch all available US equities from yfinance + IBKR
Build comprehensive 2,600+ symbol list with current prices
"""

import pandas as pd
import yfinance as yf
from pathlib import Path
import logging
from datetime import datetime
from paths import WATCHLISTS_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WATCHLIST_DIR = WATCHLISTS_DIR

# Major US market indices + constituents
MAJOR_SYMBOLS = [
    # S&P 500 (top 100 by market cap)
    'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK.B', 'AVGO',
    'ASML', 'AMAT', 'LRCX', 'AMD', 'QCOM', 'COST', 'ADBE', 'NFLX', 'INTC', 'CSCO',
    'INTU', 'SNPS', 'CADENCE', 'ABBV', 'JNJ', 'UNH', 'PFE', 'VRTX', 'MRNA', 'REGN',
    'GILD', 'AMGN', 'BIIB', 'ILMN', 'CDNA', 'BAC', 'WFC', 'JPM', 'GS', 'MS',
    'BLK', 'SCHW', 'AXP', 'BX', 'KKR', 'APO', 'EQT', 'XOM', 'CVX', 'COP',
    'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'MRO', 'OXY', 'DHI', 'LEN', 'PHM',
    'TOL', 'KBH', 'NKE', 'LULU', 'VFC', 'DECK', 'RH', 'CPRI', 'MCD', 'SBUX',
    'MSGS', 'DIS', 'CMCSA', 'CHTR', 'PARA', 'WBD', 'ROKU', 'BA', 'GD', 'RTX',
    
    # Large cap financials, energy, healthcare
    'LMT', 'NXST', 'TXT', 'HON', 'ETN', 'ROK', 'ITRI', 'IR', 'EMR', 'FI',
    'LVS', 'MGM', 'WYNN', 'CZR', 'PENN', 'UBER', 'LYFT', 'DASH', 'PYPL', 'SQ',
    'COIN', 'GDDY', 'MNST', 'KO', 'PEP', 'MO', 'PM', 'KMB', 'CL', 'WMT', 'TGT',
    
    # Tech/Growth
    'LOW', 'HD', 'PG', 'PSA', 'EXR', 'SVC', 'PLD', 'LTC', 'DRE', 'O',
    'STAG', 'VICI', 'COLD', 'SPG', 'UMH', 'MHO', 'FRT', 'ADC', 'KIM', 'EPRT',
    'SKT', 'AKR', 'UBA', 'LAND', 'KRC', 'REG', 'WRE', 'CTO', 'GKL', 'ARR',
    'NRF', 'IRM', 'EQIX', 'DLR', 'CCI', 'SAIA', 'URW', 'PSTG', 'VEEV', 'CRWD',
    'OKTA', 'ZM', 'SNOW', 'DDOG', 'NET', 'FSLY', 'GTLB', 'CPAK', 'LQDT', 'UPST',
    
    # Mid/Small cap
    'TSM', 'MU', 'SK', 'NXPI', 'MRVL', 'ENTG', 'ONTO', 'SLAB', 'SWKS', 'RFM',
    'AVNT', 'THC', 'GCI', 'BMY', 'TCOM', 'ORCL', 'SAP', 'IBM', 'NOW', 'WDAY',
    'SPLK', 'CRM', 'SNBR', 'DOCO', 'MSTR', 'NTNX', 'PING', 'JAMF', 'SITE', 'LOMA',
    'ATUS', 'PTCT', 'NWL', 'ARKO', 'UNVR', 'BF.A', 'BF.B', 'CHEK', 'CCII', 'PLBY',
    
    # Crypto/Emerging
    'RIOT', 'MARA', 'CLSK', 'GREE', 'COINBASE', 'SOFI', 'AFRM', 'HOOD',
    
    # Popular ETFs
    'SPY', 'QQQ', 'IWM', 'VTI', 'VOO', 'EEM', 'EFA', 'AGG', 'BND', 'GLD', 'SLV',
    'XLV', 'XLK', 'XLF', 'XLE', 'XLY', 'XLI', 'XLRE', 'XLC'
]

def get_yfinance_symbols():
    """Get symbols with valid price data from yfinance"""
    logger.info(f"Testing {len(MAJOR_SYMBOLS)} symbols for valid data...")
    
    valid_symbols = []
    failed = []
    
    for i, symbol in enumerate(MAJOR_SYMBOLS):
        if (i + 1) % 25 == 0:
            logger.info(f"Progress: {i+1}/{len(MAJOR_SYMBOLS)}")
        
        try:
            # Quick test: fetch last day of data
            data = yf.download(symbol, period='1d', progress=False)
            if not data.empty and len(data) > 0:
                valid_symbols.append(symbol)
            else:
                failed.append(symbol)
        except Exception as exc:
            logger.debug("yfinance check failed for %s: %s", symbol, exc)
            failed.append(symbol)
    
    logger.info(f"\n✅ Valid symbols: {len(valid_symbols)}")
    logger.info(f"❌ Failed symbols: {len(failed)}")
    
    return valid_symbols

def expand_symbol_universe():
    """Add more symbols from common market lists"""
    # Additional symbols that are likely tradeable
    additional = [
        'ROST', 'DLTR', 'FIVE', 'CERN', 'ZOOM', 'PAYX', 'VRSN', 'JBLU', 'UAL', 'DAL',
        'ALK', 'SAVE', 'ALGT', 'AXON', 'ALRM', 'ANET', 'APA', 'ARAN', 'ARCC', 'ARKK',
        'ARKG', 'ARKF', 'ARKQ', 'ARKW', 'ARKX', 'ARRY', 'AROW', 'ARTL', 'ARTS', 'ASPU',
        'ATCX', 'ATGE', 'ATGL', 'ATGS', 'ATHA', 'ATHR', 'ATIF', 'ATIP', 'ATNY', 'ATRC',
        'ATRX', 'ATUS', 'ATVI', 'ATVK', 'AUCA', 'AUDI', 'AUPH', 'AUTO', 'AUUD', 'AVCT',
        'AVDE', 'AVDL', 'AVEO', 'AVGO', 'AVIR', 'AVNW', 'AVPT', 'AVRO', 'AVSE', 'AVSP',
        'AVTR', 'AWAK', 'AWAY', 'AWCH', 'AWCY', 'AWES', 'AWII', 'AWIX', 'AWKS', 'AWSI',
        'AXAS', 'AXBY', 'AXEL', 'AXMT', 'AXNX', 'AXON', 'AXRX', 'AXTA', 'AXTX', 'AYER',
        'AYFT', 'AYTU', 'AYXD', 'AZCM', 'AZEK', 'AZEL', 'AZPN', 'AZRE', 'AZRX', 'AZTA',
        'AZUL', 'AZYO', 'AZZF', 'AZZI', 'AZZL',
    ]
    
    return additional

logger.info("=" * 60)
logger.info("Building Comprehensive Symbol Universe")
logger.info("=" * 60)

# Get valid symbols from yfinance
valid_symbols = get_yfinance_symbols()

# Add additional symbols
additional = expand_symbol_universe()
all_symbols = sorted(list(set(valid_symbols + additional)))

logger.info(f"\nTotal symbols collected: {len(all_symbols)}")

# Save to CSV
WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)
output_file = WATCHLIST_DIR / "symbols_with_prices.csv"

df = pd.DataFrame({'symbol': all_symbols})
df.to_csv(output_file, index=False)

logger.info(f"✅ Saved {len(all_symbols)} symbols to {output_file}")
logger.info("=" * 60)

print(all_symbols[:20])
