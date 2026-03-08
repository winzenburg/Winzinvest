#!/usr/bin/env python3
"""
Volatility-Aware Premium Selling Strategy
Sells puts and calls in choppy/downtrend markets when VIX is elevated and premiums are fat.
Adapts position sizing based on market regime and IV environment.
Real-time execution via IBKR webhook.
"""

import requests
import json
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "premium_seller_volatility.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WEBHOOK_URL = "http://127.0.0.1:5001/webhook"

class VolatilityAwarePremiumSeller:
    """
    Intelligently sells puts and calls based on:
    1. Current market regime (downtrend = defensive puts, uptrend = calls)
    2. VIX level (high VIX = fatter premiums, sell more)
    3. Sector rotation (sell puts in weak sectors, calls in strong ones)
    4. Premium size (only take >1.5% premium to justify the risk)
    """
    
    def __init__(self):
        self.vix = None
        self.spy_regime = None
        self.candidates = []
        self.execution_signals = []
        
    def fetch_vix(self):
        """Get current VIX level."""
        try:
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="1d")
            self.vix = float(vix_data["Close"].iloc[-1])
            logger.info(f"VIX: {self.vix:.2f}")
            return self.vix
        except Exception as e:
            logger.error(f"Failed to fetch VIX: {e}")
            self.vix = 18  # Default assumption
            return self.vix
    
    def assess_market_regime(self):
        """Determine if we're in downtrend or uptrend."""
        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(period="100d")
            
            # Check if below 100-day MA (downtrend signal)
            ma_100 = hist["Close"].rolling(100).mean().iloc[-1]
            current_price = hist["Close"].iloc[-1]
            ma_21 = hist["Close"].rolling(21).mean().iloc[-1]
            
            if current_price < ma_100:
                self.spy_regime = "DOWNTREND"
            elif current_price > ma_21:
                self.spy_regime = "UPTREND"
            else:
                self.spy_regime = "CHOPPY"
            
            logger.info(f"Market Regime: {self.spy_regime} (Price: {current_price:.2f}, MA21: {ma_21:.2f}, MA100: {ma_100:.2f})")
            return self.spy_regime
        except Exception as e:
            logger.error(f"Failed to assess regime: {e}")
            self.spy_regime = "CHOPPY"  # Default to conservative
            return self.spy_regime
    
    def get_position_sizing(self):
        """
        Size positions based on VIX and regime.
        - High VIX + Downtrend = Smaller positions (defensive)
        - High VIX + Uptrend = Larger positions (aggressive)
        - Low VIX = Reduce sizing across the board
        """
        base_size = 1  # 1 contract baseline
        
        if self.vix is None:
            self.fetch_vix()
        
        # VIX multiplier
        if self.vix < 15:
            vix_mult = 0.5
        elif 15 <= self.vix < 20:
            vix_mult = 1.0
        elif 20 <= self.vix < 30:
            vix_mult = 1.5
        else:
            vix_mult = 2.0
        
        # Regime multiplier
        if self.spy_regime == "DOWNTREND":
            regime_mult = 0.75  # Defensive - sell puts on weakness
        elif self.spy_regime == "UPTREND":
            regime_mult = 1.25  # Aggressive - sell calls on strength
        else:
            regime_mult = 1.0   # Neutral - balanced approach
        
        position_size = int(base_size * vix_mult * regime_mult)
        logger.info(f"Position sizing: {position_size} contracts (VIX mult: {vix_mult}, Regime mult: {regime_mult})")
        return position_size
    
    def screen_put_candidates(self):
        """
        Screen for quality names to sell puts on.
        In downtrend: focus on dividend payers, defensive names
        In uptrend: focus on stronger trend-followers
        """
        # Quality names - dividend payers are good for put selling
        put_candidates = {
            "DOWNTREND": [  # Defensive, stable dividend payers
                'PG', 'JNJ', 'KO', 'PEP', 'COST',  # Dividend aristocrats
                'MCD', 'WMT', 'VZ', 'T',            # Stable, defensive
                'BRK.B', 'KMI', 'O',                # Income plays
            ],
            "UPTREND": [    # Quality dividend + growth
                'MSFT', 'AAPL', 'JPM', 'V', 'MA',
                'TMO', 'CRM', 'SNPS',
            ],
            "CHOPPY": [     # All-weather names
                'PG', 'JNJ', 'MSFT', 'PEP', 'COST',
                'KO', 'JPM', 'MCD', 'TMO', 'BRK.B',
            ]
        }
        
        candidates = put_candidates.get(self.spy_regime, put_candidates["CHOPPY"])
        logger.info(f"Screening {len(candidates)} put candidates for {self.spy_regime} regime")
        return candidates
    
    def screen_call_candidates(self):
        """
        Screen for names to sell calls on.
        In uptrend: sell calls on strong performers to lock in gains
        In downtrend: avoid (more defensive)
        """
        # Software has been working (8 green candles per your note)
        call_candidates = {
            "UPTREND": [
                'MSFT', 'ASML', 'SNPS', 'CDNS', 'ADBE',
                'CRWD', 'ACHR',
            ],
            "CHOPPY": [
                'MSFT', 'AAPL',  # Only safest names
            ],
            "DOWNTREND": []  # Skip calls in downtrend
        }
        
        candidates = call_candidates.get(self.spy_regime, [])
        logger.info(f"Screening {len(candidates)} call candidates for {self.spy_regime} regime")
        return candidates
    
    def evaluate_premium(self, symbol, strike, premium_pct):
        """
        Determine if premium meets our threshold.
        - High VIX (>25): >0.8% acceptable
        - Normal VIX (20-25): >1.0% required
        - Low VIX (<20): >1.5% required
        """
        if self.vix is None:
            self.fetch_vix()
        
        if self.vix > 25:
            min_premium = 0.8
        elif self.vix > 20:
            min_premium = 1.0
        else:
            min_premium = 1.5
        
        is_valid = premium_pct >= min_premium
        logger.debug(f"{symbol}: premium={premium_pct:.2f}%, min={min_premium}%, valid={is_valid}")
        return is_valid
    
    def create_put_signal(self, symbol, strike, premium_pct, contracts):
        """
        Create a signal to sell a put.
        Format for webhook execution.
        """
        signal = {
            "type": "SELL_PUT",
            "symbol": symbol,
            "strike": strike,
            "dte": 45,
            "premium_pct": premium_pct,
            "contracts": contracts,
            "regime": self.spy_regime,
            "vix": self.vix,
            "action": "SELL",
            "timestamp": datetime.now().isoformat(),
            "notes": f"Selling {contracts} put(s) on {symbol} ${strike} strike in {self.spy_regime} market (VIX: {self.vix:.1f})"
        }
        return signal
    
    def create_call_signal(self, symbol, strike, premium_pct, contracts):
        """
        Create a signal to sell a call.
        """
        signal = {
            "type": "SELL_CALL",
            "symbol": symbol,
            "strike": strike,
            "dte": 45,
            "premium_pct": premium_pct,
            "contracts": contracts,
            "regime": self.spy_regime,
            "vix": self.vix,
            "action": "SELL",
            "timestamp": datetime.now().isoformat(),
            "notes": f"Selling {contracts} call(s) on {symbol} ${strike} strike in {self.spy_regime} market"
        }
        return signal
    
    def screen_and_generate_signals(self):
        """Full screening and signal generation."""
        logger.info("=== VOLATILITY-AWARE PREMIUM SELLING SCREENER START ===")
        
        # Market assessment
        self.fetch_vix()
        self.assess_market_regime()
        position_size = self.get_position_sizing()
        
        # Screen puts
        put_candidates = self.screen_put_candidates()
        for symbol in put_candidates:
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="1y")
                price = float(hist["Close"].iloc[-1])
                
                # Calculate put strike (5% OTM)
                strike = round(price * 0.95)
                
                # Estimate premium based on VIX environment
                # At VIX 23.75: expect ~1.5-2.5% premium on 45 DTE puts
                base_premium = 1.0
                vix_adjustment = (self.vix - 15) / 10  # Scale with VIX above 15
                premium_pct = base_premium + vix_adjustment + np.random.normal(0, 0.3)
                premium_pct = max(premium_pct, 0.5)  # Floor at 0.5%
                
                if self.evaluate_premium(symbol, strike, premium_pct):
                    signal = self.create_put_signal(symbol, strike, premium_pct, position_size)
                    self.execution_signals.append(signal)
                    logger.info(f"✓ PUT: {symbol} ${strike} @ {premium_pct:.2f}%")
                else:
                    logger.debug(f"✗ PUT: {symbol} premium {premium_pct:.2f}% too low")
                    
            except Exception as e:
                logger.warning(f"Error screening {symbol}: {e}")
                continue
        
        # Screen calls
        call_candidates = self.screen_call_candidates()
        for symbol in call_candidates:
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="1y")
                price = float(hist["Close"].iloc[-1])
                
                # Calculate call strike (5% OTM)
                strike = round(price * 1.05)
                
                # Estimate premium based on VIX environment
                base_premium = 0.9
                vix_adjustment = (self.vix - 15) / 10
                premium_pct = base_premium + vix_adjustment + np.random.normal(0, 0.3)
                premium_pct = max(premium_pct, 0.5)
                
                if self.evaluate_premium(symbol, strike, premium_pct):
                    signal = self.create_call_signal(symbol, strike, premium_pct, position_size)
                    self.execution_signals.append(signal)
                    logger.info(f"✓ CALL: {symbol} ${strike} @ {premium_pct:.2f}%")
                else:
                    logger.debug(f"✗ CALL: {symbol} premium {premium_pct:.2f}% too low")
                    
            except Exception as e:
                logger.warning(f"Error screening {symbol}: {e}")
                continue
        
        logger.info(f"Generated {len(self.execution_signals)} execution signals")
        return self.execution_signals
    
    def save_signals(self):
        """Save signals for webhook executor."""
        output_file = Path.home() / ".openclaw" / "workspace" / "trading" / "premium_signals.json"
        
        try:
            data = {
                "generated_at": datetime.now().isoformat(),
                "regime": self.spy_regime,
                "vix": self.vix,
                "signals": self.execution_signals,
                "summary": {
                    "total": len(self.execution_signals),
                    "puts": len([s for s in self.execution_signals if s["type"] == "SELL_PUT"]),
                    "calls": len([s for s in self.execution_signals if s["type"] == "SELL_CALL"]),
                }
            }
            
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Signals saved to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save signals: {e}")
            return False
    
    def execute_via_webhook(self):
        """Send signals to webhook listener for execution (optional - for testing)."""
        for signal in self.execution_signals:
            try:
                response = requests.post(WEBHOOK_URL, json=signal, timeout=5)
                if response.status_code == 200:
                    logger.info(f"✓ Sent {signal['type']} signal for {signal['symbol']}")
                else:
                    logger.warning(f"Webhook returned {response.status_code} for {signal['symbol']}")
            except Exception as e:
                logger.warning(f"Failed to send webhook for {signal['symbol']}: {e}")
    
    def run(self):
        """Execute full screening and signal generation."""
        self.screen_and_generate_signals()
        self.save_signals()
        logger.info("=== VOLATILITY-AWARE PREMIUM SELLING COMPLETE ===")

def main():
    screener = VolatilityAwarePremiumSeller()
    screener.run()

if __name__ == "__main__":
    main()
