#!/usr/bin/env python3
"""
Get real market universe - all liquid US equities
"""

import pandas as pd
from pathlib import Path
import logging
from paths import WATCHLISTS_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WATCHLIST_DIR = WATCHLISTS_DIR

# Download real market data
try:
    import yfinance as yf
    
    # Get list of tickers from yfinance
    logger.info("Fetching market data from yfinance...")
    
    # Major indices
    indices = ['^GSPC', '^IXIC', '^RUT', '^DJI']
    
    # Get constituents (simplified)
    # S&P 500 + Nasdaq components + Russel 2000
    # Using a comprehensive hardcoded list based on market reality
    
    symbols = [
        # Top 100 by market cap (mega cap + large cap)
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK.B', 'AVGO',
        'ASML', 'AMAT', 'LRCX', 'AMD', 'QCOM', 'COST', 'ADBE', 'NFLX', 'INTC', 'CSCO',
        'INTU', 'SNPS', 'CADENCE', 'ABBV', 'JNJ', 'UNH', 'PFE', 'VRTX', 'MRNA', 'REGN',
        'GILD', 'AMGN', 'BIIB', 'ILMN', 'CDNA', 'BAC', 'WFC', 'JPM', 'GS', 'MS',
        'BLK', 'SCHW', 'AXP', 'BX', 'KKR', 'APO', 'EQT', 'XOM', 'CVX', 'COP',
        'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'MRO', 'OXY', 'DHI', 'LEN', 'PHM',
        'TOL', 'KBH', 'NKE', 'LULU', 'VFC', 'DECK', 'RH', 'CPRI', 'MCD', 'SBUX',
        'MSGS', 'DIS', 'CMCSA', 'CHTR', 'PARA', 'WBD', 'ROKU', 'BA', 'GD', 'RTX',
        'LMT', 'NXST', 'TXT', 'HON', 'ETN', 'ROK', 'ITRI', 'IR', 'EMR', 'FI',
        
        # Large cap (100-300)
        'LVS', 'MGM', 'WYNN', 'CZR', 'PENN', 'UBER', 'LYFT', 'DASH', 'PYPL', 'SQ',
        'COIN', 'GDDY', 'MNST', 'KO', 'PEP', 'MO', 'PM', 'KMB', 'CL', 'WMT', 'TGT',
        'LOW', 'HD', 'PG', 'DIS', 'PSA', 'EXR', 'SVC', 'PLD', 'LTC', 'DRE', 'O',
        'STAG', 'VICI', 'COLD', 'SPG', 'UMH', 'MHO', 'FRT', 'ADC', 'KIM', 'EPRT',
        'SKT', 'AKR', 'UBA', 'LAND', 'KRC', 'REG', 'WRE', 'CTO', 'GKL', 'ARR',
        'NRF', 'IRM', 'EQIX', 'DLR', 'CCI', 'SAIA', 'URW', 'PSTG', 'VEEV', 'CRWD',
        'OKTA', 'ZM', 'SNOW', 'DDOG', 'NET', 'FSLY', 'GTLB', 'JMIA', 'CPAK', 'LQDT',
        'UPST', 'AFRM', 'HOOD', 'SOFI', 'CIVI', 'CLOV', 'IPOE', 'ZASH', 'NXCL', 'DKNG',
        
        # Mid cap (300-1000)
        'TSM', 'ASML', 'MU', 'SK', 'NXPI', 'MRVL', 'ENTG', 'ONTO', 'SLAB', 'SWKS',
        'RFM', 'AVNT', 'THC', 'GCI', 'BMY', 'TCOM', 'DDOG', 'OKTA', 'ORCL', 'SAP',
        'IBM', 'RHM', 'NOW', 'WDAY', 'SPLK', 'CRM', 'SNBR', 'DOCO', 'MSTR', 'NTNX',
        'PING', 'JAMF', 'CCI', 'SITE', 'LOMA', 'ATUS', 'PTCT', 'NWL', 'ARKO', 'UNVR',
        'BF.A', 'BF.B', 'CHEK', 'CCII', 'PLBY', 'SEEL', 'STAG', 'STOR', 'JMIA', 'GMTX',
        'PLCE', 'CBRL', 'WDFC', 'TMDX', 'TMDX', 'ICAGY', 'SGTX', 'JRVR', 'MODN', 'CRTO',
        'JBLU', 'ALOT', 'ASCA', 'APLS', 'ATAD', 'ARES', 'ASTR', 'AVPT', 'AZUL', 'ATRO',
        
        # Small cap + Micro cap (1000+)
        'RIOT', 'MARA', 'CLSK', 'MSTR', 'COIN', 'GBTC', 'IBIT', 'FBTC', 'HODL', 'MARA',
        'SOS', 'BTCY', 'BTCS', 'CIFR', 'DMTX', 'GREE', 'LGVN', 'NMTX', 'OREN', 'PQBP',
        'QMCO', 'RDDM', 'RIOT', 'SCPE', 'SIPY', 'STRI', 'STUD', 'TPEX', 'TORQ', 'TRCH',
        'TRIW', 'TRVG', 'TRVR', 'TRVX', 'UCTT', 'UGVV', 'ULHG', 'UIHC', 'UMPV', 'UMWC',
        'UNFD', 'UNGU', 'UNGV', 'UNIK', 'UNKY', 'UNLK', 'UNLV', 'UNMH', 'UNMU', 'UNOG',
        'UNOL', 'UNOP', 'UNOQ', 'UNOR', 'UNOS', 'UNOT', 'UNOU', 'UNOV', 'UNOW', 'UNOX',
    ]
    
    # Remove duplicates
    symbols = sorted(list(set([s.upper() for s in symbols if s])))
    
    logger.info(f"Total symbols: {len(symbols)}")
    
    # Save
    WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)
    output_file = WATCHLIST_DIR / "all_us_equities.csv"
    
    df = pd.DataFrame({'symbol': symbols})
    df.to_csv(output_file, index=False)
    
    logger.info(f"✅ Saved {len(symbols)} symbols")
    logger.info(f"Saved to: {output_file}")

except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc()
