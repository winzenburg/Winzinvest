#!/usr/bin/env python3
"""
Extract 800 from complete universe:
- ALL S&P 500 (449)
- ALL Nasdaq-listed (90) - INCLUDING overlap with S&P
- Top Russell/small-cap (261)
Total: 800 unique symbols
"""

import pandas as pd
from pathlib import Path
from paths import WATCHLISTS_DIR

WATCHLIST_DIR = WATCHLISTS_DIR

# Load full symbol list
df = pd.read_csv(WATCHLIST_DIR / "pinchy_symbols_ALL.csv")

print("=" * 60)
print("EXTRACTING 800 - CORRECT COMPOSITION")
print("=" * 60)
print("")

# S&P 500
sp500 = df[df['liquidity_tier'] == 'Tier 1 - S&P 500']
print(f"S&P 500: {len(sp500)}")

# Nasdaq - ALL nasdaq-listed stocks
nasdaq = df[df['index_membership'].str.contains('Nasdaq', na=False, case=False)]
print(f"Nasdaq (all): {len(nasdaq)}")

# Russell - Tier 3
tier3 = df[df['liquidity_tier'] == 'Tier 3 - Listed']
print(f"Tier 3 (Russell/small-cap): {len(tier3)}")

# Combine S&P 500 + Nasdaq (some overlap is OK, we'll deduplicate)
sp500_nasdaq = pd.concat([sp500, nasdaq]).drop_duplicates(subset=['symbol'])
print(f"\nS&P 500 + Nasdaq (deduplicated): {len(sp500_nasdaq)}")

# Calculate how many Russell we need
russell_needed = 800 - len(sp500_nasdaq)
print(f"Russell/small-cap needed: {russell_needed}")

# Get top Russell stocks
russell_selection = tier3.head(russell_needed)

# Combine all
top_800 = pd.concat([sp500_nasdaq, russell_selection]).drop_duplicates(subset=['symbol'])

print("")
print("=" * 60)
print("FINAL COMPOSITION - 800 SYMBOLS")
print("=" * 60)

sp500_count = len(top_800[top_800['liquidity_tier'] == 'Tier 1 - S&P 500'])
nasdaq_count = len(top_800[top_800['index_membership'].str.contains('Nasdaq', na=False, case=False)])
russell_count = len(top_800[top_800['liquidity_tier'] == 'Tier 3 - Listed'])

print(f"S&P 500:          {sp500_count}")
print(f"Nasdaq (all):     {nasdaq_count}")
print(f"Russell/small-cap: {russell_count}")
print(f"{'─' * 40}")
print(f"TOTAL:            {len(top_800)}")
print("")

# Save
output_file = WATCHLIST_DIR / "top_800_final_correct.csv"
top_800[['symbol']].to_csv(output_file, index=False)

print(f"✅ Saved {len(top_800)} symbols to:")
print(f"   {output_file}")
print("")

# Show samples
print("S&P 500 (first 15):")
for sym in sp500['symbol'].head(15):
    print(f"  • {sym}")

print(f"\nNasdaq exclusive (all {len(nasdaq_count)}):")
nasdaq_only = nasdaq[~nasdaq['symbol'].isin(sp500['symbol'])]
for sym in nasdaq_only['symbol']:
    print(f"  • {sym}")

print(f"\nRussell/small-cap (first 15):")
for sym in russell_selection['symbol'].head(15):
    print(f"  • {sym}")

print(f"\n✅ NOW includes ALL {nasdaq_count} Nasdaq stocks")
