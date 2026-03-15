#!/usr/bin/env python3
"""
Extract 800 most liquid stocks
From: S&P 500, Nasdaq, Russell 2000
"""

import pandas as pd
from pathlib import Path
from paths import WATCHLISTS_DIR

WATCHLIST_DIR = WATCHLISTS_DIR

# Load full symbol list
df = pd.read_csv(WATCHLIST_DIR / "pinchy_symbols_ALL.csv")

print("=" * 60)
print("EXTRACTING 800 BROADER SYMBOL UNIVERSE")
print("=" * 60)
print("")

# Tier 1 (S&P 500)
sp500 = df[df['liquidity_tier'] == 'Tier 1 - S&P 500']
print(f"S&P 500: {len(sp500)}")

# Tier 2 (Nasdaq/Major Index)
tier2 = df[df['liquidity_tier'] == 'Tier 2 - Major Index']
print(f"Nasdaq Major: {len(tier2)}")

# Tier 3 - Russell 2000 (look for 'Russell' in index_membership)
tier3 = df[df['liquidity_tier'] == 'Tier 3 - Listed']
tier3_russell = tier3[tier3['index_membership'].str.contains('Russell', na=False, case=False)]
print(f"Russell 2000 (tagged): {len(tier3_russell)}")

# If Russell count is low, use top of Tier 3 as proxy (likely Russell/liquid small-cap)
russell_needed = 800 - len(sp500) - len(tier2)
if len(tier3_russell) < russell_needed:
    print(f"  Only {len(tier3_russell)} Russell-tagged. Using top {russell_needed} from Tier 3...")
    tier3_top = tier3.head(russell_needed)
    print(f"  Using {len(tier3_top)} top Tier 3 symbols")
else:
    tier3_top = tier3_russell.head(russell_needed)
    print(f"  Using {len(tier3_top)} Russell-tagged symbols")

# Combine to get exactly 800
top_800 = pd.concat([sp500, tier2, tier3_top])

print("")
print("=" * 60)
print("FINAL SELECTION - 800 SYMBOLS")
print("=" * 60)
print(f"S&P 500 (Tier 1):     {len(sp500):3d}")
print(f"Nasdaq/Major (T2):    {len(tier2):3d}")
print(f"Russell/Small-cap:    {len(tier3_top):3d}")
print(f"{'─' * 30}")
print(f"TOTAL:                {len(top_800):3d}")
print("")

# Save
output_file = WATCHLIST_DIR / "top_800_broader_sp500_nasdaq_russell.csv"
top_800[['symbol']].to_csv(output_file, index=False)

print(f"✅ Saved {len(top_800)} symbols to:")
print(f"   {output_file}")
print("")

# Show samples from each tier
print("Sample symbols:")
print(f"\nS&P 500 (first 10):")
for sym in sp500['symbol'].head(10):
    print(f"  • {sym}")

print(f"\nNasdaq/Major (all {len(tier2)}):")
for sym in tier2['symbol']:
    print(f"  • {sym}")

print(f"\nRussell/Small-cap (first 10):")
for sym in tier3_top['symbol'].head(10):
    print(f"  • {sym}")

print(f"\nRussell/Small-cap (last 10):")
for sym in tier3_top['symbol'].tail(10):
    print(f"  • {sym}")
