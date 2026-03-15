#!/usr/bin/env python3
"""
Extract 800 from complete universe:
- ALL S&P 500
- ALL Nasdaq-listed
- ALL Russell 2000
Take top 800 from combined pool
"""

import pandas as pd
from pathlib import Path
from paths import WATCHLISTS_DIR

WATCHLIST_DIR = WATCHLISTS_DIR

# Load full symbol list
df = pd.read_csv(WATCHLIST_DIR / "pinchy_symbols_ALL.csv")

print("=" * 60)
print("EXTRACTING TOP 800 FROM COMPLETE UNIVERSE")
print("=" * 60)
print("")

# S&P 500
sp500 = df[df['liquidity_tier'] == 'Tier 1 - S&P 500']
print(f"S&P 500: {len(sp500)}")

# Nasdaq - search for 'Nasdaq' in index_membership
nasdaq = df[df['index_membership'].str.contains('Nasdaq', na=False, case=False)]
print(f"Nasdaq (from index_membership): {len(nasdaq)}")

# Russell 2000 - search for 'Russell' in index_membership
russell = df[df['index_membership'].str.contains('Russell', na=False, case=False)]
print(f"Russell 2000 (from index_membership): {len(russell)}")

# Combine all three pools
combined = pd.concat([sp500, nasdaq, russell]).drop_duplicates(subset=['symbol'])
print(f"\nCombined (with dedupe): {len(combined)}")
print("")

# If we have more than 800, take top 800
if len(combined) > 800:
    print(f"More than 800 available. Selecting top 800...")
    top_800 = combined.head(800)
    print(f"Selected: {len(top_800)}")
else:
    print(f"Less than 800 available. Using all {len(combined)}")
    top_800 = combined

# Verify composition
sp500_in_800 = len(top_800[top_800['liquidity_tier'] == 'Tier 1 - S&P 500'])
nasdaq_in_800 = len(top_800[top_800['index_membership'].str.contains('Nasdaq', na=False, case=False)])
russell_in_800 = len(top_800[top_800['index_membership'].str.contains('Russell', na=False, case=False)])

print("")
print("=" * 60)
print("FINAL SELECTION - TOP 800")
print("=" * 60)
print(f"S&P 500 in top 800:      {sp500_in_800}")
print(f"Nasdaq in top 800:       {nasdaq_in_800}")
print(f"Russell in top 800:      {russell_in_800}")
print(f"{'─' * 40}")
print(f"TOTAL:                   {len(top_800)}")
print("")

# Save
output_file = WATCHLIST_DIR / "top_800_complete_sp500_nasdaq_russell.csv"
top_800[['symbol']].to_csv(output_file, index=False)

print(f"✅ Saved {len(top_800)} symbols to:")
print(f"   {output_file}")
print("")

# Show samples
print("Sample S&P 500:")
for sym in top_800[top_800['liquidity_tier'] == 'Tier 1 - S&P 500']['symbol'].head(10):
    print(f"  • {sym}")

print("\nSample Nasdaq:")
nasdaq_sample = top_800[top_800['index_membership'].str.contains('Nasdaq', na=False, case=False)]
for sym in nasdaq_sample['symbol'].head(10):
    print(f"  • {sym}")

print("\nSample Russell:")
russell_sample = top_800[top_800['index_membership'].str.contains('Russell', na=False, case=False)]
for sym in russell_sample['symbol'].head(10):
    print(f"  • {sym}")

print(f"\nTotal ready for production: {len(top_800)} symbols")
