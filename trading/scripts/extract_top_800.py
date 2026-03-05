#!/usr/bin/env python3
"""
Extract top 800 most liquid stocks
From: S&P 500, Nasdaq, Russell 2000
"""

import pandas as pd
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
WATCHLIST_DIR = WORKSPACE / "trading" / "watchlists"

# Load full symbol list
df = pd.read_csv(WATCHLIST_DIR / "pinchy_symbols_ALL.csv")

print("=" * 60)
print("EXTRACTING TOP 800 MOST LIQUID STOCKS")
print("=" * 60)
print("")

# Tier 1 (S&P 500) - highest quality
sp500 = df[df['liquidity_tier'] == 'Tier 1 - S&P 500']
print(f"S&P 500: {len(sp500)} symbols")
print(f"  Sample: {sp500['symbol'].head(10).tolist()}")

# Tier 2 (Major Index - likely Nasdaq 100)
tier2 = df[df['liquidity_tier'] == 'Tier 2 - Major Index']
print(f"\nTier 2 (Major Index): {len(tier2)} symbols")
if len(tier2) > 0:
    print(f"  Sample: {tier2['symbol'].head(10).tolist()}")

# Tier 3 - check for Russell 2000
tier3 = df[df['liquidity_tier'] == 'Tier 3 - Listed']
print(f"\nTier 3 (Listed): {len(tier3)} symbols")

# Check index_membership for Russell
tier3_russell = tier3[tier3['index_membership'].str.contains('Russell', na=False)]
print(f"  Russell 2000 in Tier 3: {len(tier3_russell)} symbols")

# Combine: Tier 1 + Tier 2 + Russell from Tier 3
top_800 = pd.concat([sp500, tier2, tier3_russell]).head(800)

print("")
print("=" * 60)
print("FINAL SELECTION")
print("=" * 60)
print(f"S&P 500: {len(sp500)}")
print(f"Nasdaq/Major: {len(tier2)}")
print(f"Russell 2000: {len(tier3_russell)}")
print(f"TOTAL: {len(top_800)}")
print("")

# Save
output_file = WATCHLIST_DIR / "top_800_sp500_nasdaq_russell.csv"
top_800[['symbol']].to_csv(output_file, index=False)

print(f"✅ Saved {len(top_800)} symbols to:")
print(f"   {output_file}")
print("")
print("First 30 symbols:")
for i, sym in enumerate(top_800['symbol'].head(30), 1):
    print(f"  {i:2d}. {sym}")

print(f"\nLast 10 symbols:")
for i, sym in enumerate(top_800['symbol'].tail(10), len(top_800)-9):
    print(f"  {i:3d}. {sym}")
