#!/usr/bin/env python3
"""
Sort all 5,342 symbols by trading volume
Extract top 800 for daily screening
"""

import pandas as pd
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
WATCHLIST_DIR = WORKSPACE / "trading" / "watchlists"

# Load your full symbol list
df = pd.read_csv(WATCHLIST_DIR / "pinchy_symbols_ALL.csv")

print(f"Total symbols: {len(df)}")
print(f"Columns: {df.columns.tolist()}")
print("")
print("Sample:")
print(df.head())
print("")

# Check if there's a liquidity tier or volume column
print("Checking for volume/liquidity info...")
if 'liquidity_tier' in df.columns:
    print("\nLiquidity tiers found:")
    print(df['liquidity_tier'].value_counts())
    
    # Top 800 by tier (Tier 1 first, then Tier 2)
    tier1 = df[df['liquidity_tier'] == 'Tier 1 - S&P 500']
    tier2 = df[df['liquidity_tier'] == 'Tier 2 - Nasdaq 100']
    
    top_800 = pd.concat([tier1, tier2]).head(800)
    
    print(f"\nTier 1: {len(tier1)}")
    print(f"Tier 2: {len(tier2)}")
    print(f"Top 800 selected: {len(top_800)}")
    
    # Save
    output_file = WATCHLIST_DIR / "top_800_most_liquid.csv"
    top_800[['symbol']].to_csv(output_file, index=False)
    
    print(f"\n✅ Saved to: {output_file}")
    print(f"\nTop 20 symbols:")
    print(top_800['symbol'].head(20).tolist())

else:
    print("No liquidity tier column. Using first 800 (likely highest quality in your export)")
    top_800 = df.head(800)
    
    output_file = WATCHLIST_DIR / "top_800_most_liquid.csv"
    top_800[['symbol']].to_csv(output_file, index=False)
    
    print(f"✅ Saved top 800 to: {output_file}")
    print(f"\nFirst 20:")
    print(top_800['symbol'].head(20).tolist())
