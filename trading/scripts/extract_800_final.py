#!/usr/bin/env python3
"""
Extract 800 from complete universe:
- ALL S&P 500 (449)
- ALL Nasdaq (90)
- Top of Tier 3/Russell (261)
Total: 800
"""

import pandas as pd
from pathlib import Path
from paths import WATCHLISTS_DIR

WATCHLIST_DIR = WATCHLISTS_DIR

# Load full symbol list
df = pd.read_csv(WATCHLIST_DIR / "pinchy_symbols_ALL.csv")

print("=" * 60)
print("EXTRACTING 800 FROM COMPLETE UNIVERSE")
print("S&P 500 + Nasdaq + Russell 2000/Small-cap")
print("=" * 60)
print("")

# S&P 500
sp500 = df[df['liquidity_tier'] == 'Tier 1 - S&P 500']
print(f"S&P 500: {len(sp500)}")

# Nasdaq - all with Nasdaq in index_membership
nasdaq = df[df['index_membership'].str.contains('Nasdaq', na=False, case=False)]
print(f"Nasdaq (all): {len(nasdaq)}")

# Remove overlap (S&P 500 stocks also listed on Nasdaq)
sp500_symbols = set(sp500['symbol'])
nasdaq_only = nasdaq[~nasdaq['symbol'].isin(sp500_symbols)]
print(f"Nasdaq (excluding S&P 500): {len(nasdaq_only)}")

# Tier 3 - Russell 2000 and small-cap stocks
tier3 = df[df['liquidity_tier'] == 'Tier 3 - Listed']
print(f"Tier 3 (Russell/small-cap): {len(tier3)}")

# Calculate how many we need from each pool for 800 total
sp500_count = len(sp500)
nasdaq_count = len(nasdaq_only)
russell_needed = 800 - sp500_count - nasdaq_count

print("")
print("=" * 60)
print("COMPOSITION FOR 800")
print("=" * 60)
print(f"S&P 500:                 {sp500_count}")
print(f"Nasdaq (excluding S&P):  {nasdaq_count}")
print(f"Russell/Tier 3:          {russell_needed}")
print(f"{'─' * 40}")
print(f"TOTAL:                   {sp500_count + nasdaq_count + russell_needed}")

# Select top Russell stocks (ordered by position in dataframe = likely liquidity)
russell_selection = tier3.head(russell_needed)

# Combine
top_800 = pd.concat([sp500, nasdaq_only, russell_selection]).drop_duplicates(subset=['symbol'])

print("")
print(f"Final count: {len(top_800)}")

# Save
output_file = WATCHLIST_DIR / "top_800_final.csv"
top_800[['symbol']].to_csv(output_file, index=False)

print("")
print(f"✅ Saved {len(top_800)} symbols to:")
print(f"   {output_file}")
print("")

# Show breakdown
print("Breakdown:")
print(f"\nS&P 500 (first 15):")
for sym in sp500['symbol'].head(15):
    print(f"  • {sym}")

print(f"\nNasdaq exclusive (first 15):")
for sym in nasdaq_only['symbol'].head(15):
    print(f"  • {sym}")

print(f"\nRussell/Small-cap (first 15):")
for sym in russell_selection['symbol'].head(15):
    print(f"  • {sym}")

print(f"\nRussell/Small-cap (last 5):")
for sym in russell_selection['symbol'].tail(5):
    print(f"  • {sym}")

print(f"\n✅ System ready for 800-symbol production deployment")
