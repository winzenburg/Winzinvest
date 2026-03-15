#!/usr/bin/env python3
"""
Create balanced universe: 800 stocks + 75 high-quality ETFs
Includes: Sector, Market Cap, Emerging Markets, Commodities, Fixed Income
"""

import pandas as pd
from pathlib import Path
from paths import WATCHLISTS_DIR

WATCHLIST_DIR = WATCHLISTS_DIR

# Load current 800 stocks
stocks_800 = pd.read_csv(WATCHLIST_DIR / "top_800_final_correct.csv")

print("=" * 60)
print("CREATING BALANCED UNIVERSE: 800 STOCKS + 75 ETFs")
print("=" * 60)
print("")

# High-quality ETFs organized by category
etfs = {
    "Broad Market": [
        "SPY",    # S&P 500
        "IVV",    # iShares Core S&P 500
        "VOO",    # Vanguard S&P 500
        "QQQ",    # Nasdaq-100
        "INVESCO", # QQQ alternative
        "IWM",    # Russell 2000
        "VB",     # Vanguard Small-Cap
        "SCHA",   # Schwab U.S. Small-Cap
    ],
    
    "Sector - Tech/Growth": [
        "XLK",    # Tech
        "VGT",    # Vanguard Info Tech
        "XLC",    # Communication Services
        "VGF",    # Vanguard Financial
        "VHO",    # Vanguard Health Care
    ],
    
    "Sector - Defensive": [
        "XLV",    # Healthcare
        "VHT",    # Vanguard Healthcare
        "XLP",    # Consumer Staples
        "VDC",    # Vanguard Consumer Staples
        "XLU",    # Utilities
        "VPU",    # Vanguard Utilities
    ],
    
    "Sector - Cyclical": [
        "XLF",    # Financials
        "VFV",    # Vanguard Financials
        "XLE",    # Energy
        "VDE",    # Vanguard Energy
        "XLI",    # Industrials
        "VIS",    # Vanguard Industrials
        "XLY",    # Consumer Discretionary
        "VCR",    # Vanguard Consumer Disc
        "XLRE",   # Real Estate
        "VNQ",    # Vanguard Real Estate
    ],
    
    "Emerging Markets": [
        "EEM",    # iShares MSCI Emerging Markets
        "VWO",    # Vanguard FTSE Emerging Markets
        "IEMG",   # iShares Core MSCI Emerging
        "MCHI",   # iShares MSCI China
        "FXI",    # iShares China Large-Cap
        "ASHR",   # Alhambra China
        "EWZS",   # iShares MSCI Brazil Small-Cap
        "EWZ",    # iShares MSCI Brazil
        "ERUS",   # iShares MSCI Russia
        "INDA",   # iShares MSCI India
        "EIDO",   # iShares MSCI Indonesia
        "ECNS",   # iShares MSCI China Small-Cap
        "IEMG",   # Core MSCI Emerging Markets
    ],
    
    "International Developed": [
        "EFA",    # iShares MSCI EAFE
        "VEA",    # Vanguard FTSE Developed
        "EWJ",    # iShares MSCI Japan
        "EWG",    # iShares MSCI Germany
        "EWU",    # iShares MSCI UK
        "EWD",    # iShares MSCI Sweden
        "EWH",    # iShares MSCI Hong Kong
        "EWS",    # iShares MSCI Singapore
        "EWA",    # iShares MSCI Australia
    ],
    
    "Commodities & Resources": [
        "GLD",    # Gold
        "IAU",    # iShares Gold
        "SLV",    # Silver
        "USO",    # Oil
        "DBC",    # Commodities
        "GSG",    # iShares Commodities
        "GDX",    # Gold Miners
        "GDXJ",   # Junior Gold Miners
    ],
    
    "Fixed Income & Bonds": [
        "BND",    # Vanguard Total Bond
        "AGG",    # iShares Core Agg Bond
        "LQD",    # Investment Grade Corp Bond
        "HYG",    # High Yield Corp Bond
        "TLT",    # 20+ Year Treasury
        "IEF",    # 7-10 Year Treasury
        "SHV",    # Short-Term Treasury
    ],
    
    "Alternative & Specialty": [
        "VNQ",    # Real Estate (REIT)
        "SCHP",   # TIPS (Inflation Protection)
        "VCIT",   # Intermediate Corp Bond
        "VCLT",   # Long-Term Corp Bond
        "VGIT",   # Intermediate Govt Bond
    ],
}

# Flatten and deduplicate
all_etf_symbols = []
for category, symbols in etfs.items():
    all_etf_symbols.extend(symbols)

all_etf_symbols = sorted(list(set(all_etf_symbols)))

print(f"Total ETFs selected: {len(all_etf_symbols)}")
print("")

# Create DataFrame for ETFs
etf_data = pd.DataFrame({
    'symbol': all_etf_symbols,
    'company_name': [f'ETF: {sym}' for sym in all_etf_symbols],
    'liquidity_tier': 'ETF'
})

# Combine stocks + ETFs
combined = pd.concat([stocks_800.assign(liquidity_tier='Stock'), etf_data])

print("COMPOSITION:")
print(f"  Stocks: {len(stocks_800)}")
print(f"  ETFs: {len(etf_data)}")
print(f"  TOTAL: {len(combined)}")
print("")

# Save
output_file = WATCHLIST_DIR / "balanced_800_stocks_plus_etfs.csv"
combined[['symbol']].to_csv(output_file, index=False)

print(f"✅ Saved {len(combined)} symbols to:")
print(f"   {output_file}")
print("")

print("ETF Breakdown:")
print("")
for category, symbols in etfs.items():
    unique_syms = len(set(symbols))
    print(f"{category}: {unique_syms}")
    for sym in set(symbols):
        print(f"  • {sym}")
    print("")

print(f"✅ Ready for production deployment")
