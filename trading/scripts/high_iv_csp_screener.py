#!/usr/bin/env python3
"""
High-IV CSP Screener
Real-time monitoring for cash-secured put opportunities during volatility spikes.
Finds quality stocks with elevated IV and attractive put premiums.
Feeds candidates to options executor.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "high_iv_csp.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Quality names worth selling puts on
QUALITY_NAMES = [
    # Dividend aristocrats (defensive, resilient)
    'PG', 'JNJ', 'KO', 'PEP', 'MCD', 'COST',
    # Quality tech (strong fundamentals)
    'MSFT', 'AAPL', 'NVDA', 'ASML', 'QCOM',
    # Quality financials (vol resilient)
    'JPM', 'BAC', 'WFC', 'GS',
    # Quality infrastructure
    'CAT', 'ABB', 'SPN',
]

# CSP Criteria
CSP_CRITERIA = {
    "min_premium_pct": 1.5,      # 1.5% minimum for 30-45 DTE
    "put_delta": (-0.25, -0.35), # 25-35 delta (OTM, not aggressive)
    "dte_range": (30, 45),        # 30-45 days to expiration
    "min_stock_price": 20,        # Avoid penny stocks
    "iv_percentile_min": 60,      # Only when IV is elevated (vol spike)
}

class HighIVCSPScreener:
    def __init__(self):
        self.candidates = []
        self.quality_data = {}
    
    def fetch_stock_data(self, symbol):
        """Fetch current price and recent history."""
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1y")
            info = stock.info
            
            if hist.empty:
                return None
            
            return {
                "symbol": symbol,
                "price": float(hist["Close"].iloc[-1]),
                "52w_high": float(hist["Close"].max()),
                "52w_low": float(hist["Close"].min()),
                "atr": float(hist["High"].rolling(14).mean().iloc[-1] - 
                           hist["Low"].rolling(14).mean().iloc[-1]),
                "volume_avg": float(hist["Volume"].tail(20).mean()),
                "pe_ratio": info.get("trailingPE", None),
                "dividend_yield": info.get("dividendYield", 0),
            }
        except Exception as e:
            logger.warning(f"Error fetching {symbol}: {e}")
            return None
    
    def calculate_put_strike(self, stock_price):
        """Calculate optimal put strike (5-10% OTM)."""
        # Standard strikes are in $1 increments
        otm_pct = 0.075  # 7.5% OTM as target
        target_strike = stock_price * (1 - otm_pct)
        
        # Round to nearest $1
        strike = round(target_strike)
        return max(strike, 1)  # Minimum $1
    
    def estimate_premium(self, stock_data, strike, dte=40):
        """
        Estimate put premium using Black-Scholes approximation.
        In production, use actual option chain data from IB.
        """
        stock_price = stock_data["price"]
        
        # Simplified: IV estimate based on price volatility
        annual_return = stock_data.get("dividend_yield", 0)
        
        # ATR-based volatility proxy
        if stock_data.get("atr") and stock_price > 0:
            iv = (stock_data["atr"] / stock_price) * np.sqrt(252) * 100
        else:
            iv = 20  # Default 20% IV
        
        # Simple approximation for OTM put value
        # Premium ≈ (stock_price - strike) / stock_price * IV * sqrt(DTE/365)
        moneyness = (stock_price - strike) / stock_price
        premium_pct = moneyness * (iv / 100) * np.sqrt(dte / 365)
        
        return abs(premium_pct) * 100  # Return as percentage
    
    def screen(self):
        """Screen quality names for CSP opportunities."""
        logger.info(f"Screening {len(QUALITY_NAMES)} quality names for CSP...")
        
        for symbol in QUALITY_NAMES:
            try:
                stock_data = self.fetch_stock_data(symbol)
                if not stock_data:
                    continue
                
                # Skip if price too low
                if stock_data["price"] < CSP_CRITERIA["min_stock_price"]:
                    continue
                
                # Calculate optimal put strike
                strike = self.calculate_put_strike(stock_data["price"])
                
                # Estimate premium
                premium_pct = self.estimate_premium(stock_data, strike, dte=40)
                
                # Check if meets premium threshold
                if premium_pct >= CSP_CRITERIA["min_premium_pct"]:
                    candidate = {
                        "symbol": symbol,
                        "price": round(stock_data["price"], 2),
                        "strike": strike,
                        "dte": 40,
                        "premium_pct": round(premium_pct, 2),
                        "max_loss": strike * 100,  # Per contract
                        "return_on_risk": round(premium_pct / ((strike - stock_data["price"]) / strike) * 100, 1) if strike > stock_data["price"] else 0,
                        "timestamp": datetime.now().isoformat(),
                    }
                    self.candidates.append(candidate)
                    logger.info(f"✓ {symbol}: ${stock_data['price']} → Put ${strike} @ {premium_pct:.2f}%")
                
            except Exception as e:
                logger.warning(f"Error screening {symbol}: {e}")
                continue
        
        logger.info(f"Found {len(self.candidates)} CSP candidates")
        return self.candidates
    
    def save_candidates(self):
        """Save candidates for executor to pick up."""
        output_file = Path.home() / ".openclaw" / "workspace" / "trading" / "high_iv_candidates.json"
        
        try:
            data = {
                "generated_at": datetime.now().isoformat(),
                "candidates": sorted(self.candidates, key=lambda x: x["premium_pct"], reverse=True),
                "criteria": CSP_CRITERIA,
                "summary": {
                    "total": len(self.candidates),
                    "avg_premium": round(np.mean([c["premium_pct"] for c in self.candidates]), 2) if self.candidates else 0,
                }
            }
            
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Candidates saved to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save candidates: {e}")
            return False
    
    def run(self):
        """Execute full screening pipeline."""
        logger.info("=== HIGH-IV CSP SCREENER STARTED ===")
        self.screen()
        self.save_candidates()
        logger.info("=== HIGH-IV CSP SCREENER COMPLETE ===")

def main():
    screener = HighIVCSPScreener()
    screener.run()

if __name__ == "__main__":
    main()
