#!/usr/bin/env python3
"""
NX Dynamic Watchlist Generator
Screens the full market using AMS Pro Screener NX criteria.
Auto-generates watchlist.json with qualified candidates.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Setup logging
LOG_FILE = Path.home() / ".openclaw" / "workspace" / "trading" / "logs" / "nx_watchlist.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
WATCHLIST_FILE = Path.home() / ".openclaw" / "workspace" / "trading" / "watchlist.json"
NX_CRITERIA = {
    "tier_2_min": 0.20,
    "tier_3_min": 0.35,
    "rs_long_min": 0.60,
    "rs_short_max": 0.40,
    "rvol_min": 1.20,
    "struct_q_min": 0.50,
    "htf_bias_long_min": 0.50,
    "htf_bias_short_max": 0.50,
    "min_price": 5.0,
    "min_volume_usd": 25_000_000,
}

class NXWatchlistGenerator:
    def __init__(self):
        self.universe = []
        self.screened = []
        self.long_candidates = []
        self.short_candidates = []
        self.spy = None
        
    def fetch_market_data(self):
        """Fetch price and volume data for screening."""
        logger.info("Fetching market data...")
        
        # Core universe: S&P 500, Nasdaq 100, Russell 2000, major ETFs
        symbols = self._get_universe_symbols()
        
        try:
            # Fetch last 252 days (1 year for RS calculation)
            data = yf.download(
                symbols,
                start=datetime.now() - timedelta(days=252),
                end=datetime.now(),
                progress=False
            )
            
            # Fetch SPY separately for relative strength
            self.spy = yf.download(
                "SPY",
                start=datetime.now() - timedelta(days=252),
                end=datetime.now(),
                progress=False
            )
            
            logger.info(f"Downloaded data for {len(symbols)} symbols")
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            return None
    
    def _get_universe_symbols(self):
        """Get list of symbols to screen."""
        # S&P 500 (simplified list - in production use full list)
        sp500 = [
            'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'TSLA', 'BERKB', 'JPMORGN', 'V',
            'JNJ', 'WMT', 'PG', 'MA', 'ASML', 'COST', 'MCD', 'SPG', 'CAT', 'AXP',
            'NFLX', 'ADBE', 'CSCO', 'BKNG', 'XOM', 'CVX', 'COP', 'ISRG', 'PEP', 'KO',
            'AMD', 'INTC', 'QCOM', 'AVGO', 'TXN', 'SMCI', 'PLTR', 'AFRM', 'UPST', 'COIN',
            'GS', 'BAC', 'WFC', 'MS', 'BLK', 'HOOD', 'SOFI', 'MARA', 'RIOT', 'MSTR',
        ]
        
        # Nasdaq 100 (subset)
        nasdaq = ['QQQ']
        
        # Russell 2000 (sample)
        russell = [
            'IWM', 'FXI', 'EEM', 'GLD', 'TLT', 'SLV', 'DBC', 'BCI', 'PFE', 'ABT',
            'MRK', 'LLY', 'UNH', 'CRM', 'SNOW', 'CRWD', 'DDOG', 'NET', 'OKTA', 'TWLO',
        ]
        
        # Major ETFs
        etfs = ['SPY', 'QQQ', 'IWM', 'XLK', 'XLE', 'XLF', 'XLI', 'XLV', 'XLY', 'XLP']
        
        return list(set(sp500 + nasdaq + russell + etfs))
    
    def calculate_nx_scores(self, data):
        """Calculate NX screener metrics for each symbol."""
        logger.info("Calculating NX scores...")
        
        candidates = []
        
        # Handle both single and multiindex columns
        if isinstance(data.columns, pd.MultiIndex):
            symbols = data.columns.get_level_values(0).unique()
        else:
            symbols = [col.split('_')[0] for col in data.columns if '_' in col]
            symbols = list(set(symbols))
        
        for symbol in symbols:
            try:
                symbol_data = data[symbol]
                
                # Skip if insufficient data
                if len(symbol_data) < 126:
                    continue
                
                # Basic metrics
                close = symbol_data['Close'].values
                volume = symbol_data['Volume'].values
                high = symbol_data['High'].values
                low = symbol_data['Low'].values
                
                # Skip if below minimum price or volume
                current_price = close[-1]
                avg_volume_usd = (volume[-20:].mean() * close[-20:].mean())
                
                if current_price < NX_CRITERIA["min_price"]:
                    continue
                if avg_volume_usd < NX_CRITERIA["min_volume_usd"]:
                    continue
                
                # CompScore (momentum quality)
                roc_21 = self._calculate_roc(close, 21)
                roc_63 = self._calculate_roc(close, 63)
                roc_126 = self._calculate_roc(close, 126)
                
                # Normalize by ATR
                atr = self._calculate_atr(high, low, close, 14)
                atr_pct = (atr / close[-1]) * 100
                
                momentum = (roc_21 + roc_63 + roc_126) / 3
                comp_score = self._normalize_momentum(momentum, atr_pct)
                
                # Relative Strength vs SPY
                rs_pct = self._calculate_rs_percentile(close, self.spy['Close'].values, 252)
                
                # Relative Volume
                rvol = self._calculate_rvol(volume, 50)
                
                # Structure Quality (pivot clarity)
                struct_q = self._calculate_structure_quality(close, 20)
                
                # HTF Bias (Weekly/Monthly trend)
                htf_bias = self._calculate_htf_bias(close)
                
                # RSI
                rsi = self._calculate_rsi(close, 14)
                
                # Regime (0=squeeze, 1=normal, 2=breakout)
                regime = self._determine_regime(rvol, atr_pct)
                
                # Ready flags
                long_ready = int(rsi >= 45 and rsi <= 75)
                short_ready = int(rsi >= 25 and rsi <= 55)
                
                # Tier determination
                if comp_score >= NX_CRITERIA["tier_3_min"]:
                    tier = 3
                elif comp_score >= NX_CRITERIA["tier_2_min"]:
                    tier = 2
                else:
                    tier = 1
                
                candidate = {
                    "symbol": symbol,
                    "tier": tier,
                    "comp_score": round(comp_score, 3),
                    "rs_pct": round(rs_pct, 3),
                    "rvol": round(rvol, 2),
                    "struct_q": round(struct_q, 3),
                    "htf_bias": round(htf_bias, 3),
                    "rsi": round(rsi, 1),
                    "regime": regime,
                    "long_ready": long_ready,
                    "short_ready": short_ready,
                    "price": round(current_price, 2),
                    "avg_volume_usd": round(avg_volume_usd / 1_000_000, 1),  # in millions
                }
                
                candidates.append(candidate)
                
            except Exception as e:
                logger.warning(f"Error processing {symbol}: {e}")
                continue
        
        self.screened = candidates
        logger.info(f"Screened {len(candidates)} candidates")
        return candidates
    
    def apply_nx_filters(self):
        """Apply NX green-light rules to identify candidates."""
        logger.info("Applying NX filters...")
        
        for candidate in self.screened:
            # Base criteria
            if candidate["tier"] < 2:
                continue
            if candidate["rvol"] < NX_CRITERIA["rvol_min"]:
                continue
            if candidate["struct_q"] < NX_CRITERIA["struct_q_min"]:
                continue
            
            # Long candidates
            if (candidate["rs_pct"] >= NX_CRITERIA["rs_long_min"] and
                candidate["htf_bias"] >= NX_CRITERIA["htf_bias_long_min"] and
                candidate["long_ready"]):
                self.long_candidates.append(candidate)
            
            # Short candidates
            if (candidate["rs_pct"] <= NX_CRITERIA["rs_short_max"] and
                candidate["htf_bias"] <= NX_CRITERIA["htf_bias_short_max"] and
                candidate["short_ready"]):
                self.short_candidates.append(candidate)
        
        logger.info(f"Long candidates: {len(self.long_candidates)}")
        logger.info(f"Short candidates: {len(self.short_candidates)}")
    
    def save_watchlist(self):
        """Save screened candidates to watchlist.json."""
        watchlist = {
            "generated_at": datetime.now().isoformat(),
            "long_candidates": sorted(self.long_candidates, key=lambda x: x["comp_score"], reverse=True),
            "short_candidates": sorted(self.short_candidates, key=lambda x: x["comp_score"], reverse=True),
            "nx_criteria": NX_CRITERIA,
            "summary": {
                "total_screened": len(self.screened),
                "long_count": len(self.long_candidates),
                "short_count": len(self.short_candidates),
            }
        }
        
        try:
            with open(WATCHLIST_FILE, "w") as f:
                json.dump(watchlist, f, indent=2)
            logger.info(f"Watchlist saved to {WATCHLIST_FILE}")
            return True
        except Exception as e:
            logger.error(f"Failed to save watchlist: {e}")
            return False
    
    # Helper methods
    def _calculate_roc(self, close, period):
        """Rate of Change."""
        if len(close) < period:
            return 0
        return ((close[-1] - close[-period-1]) / close[-period-1]) * 100
    
    def _calculate_atr(self, high, low, close, period):
        """Average True Range."""
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                abs(high[1:] - close[:-1]),
                abs(low[1:] - close[:-1])
            )
        )
        return np.mean(tr[-period:])
    
    def _normalize_momentum(self, momentum, atr_pct):
        """Normalize momentum by volatility."""
        baseline = 2.0
        if atr_pct > 0:
            normalized = (momentum / (atr_pct / baseline)) * 100
        else:
            normalized = momentum
        # Scale to 0-1
        return min(max((normalized + 100) / 200, 0), 1)
    
    def _calculate_rs_percentile(self, symbol_close, spy_close, lookback):
        """Relative strength vs SPY."""
        if len(symbol_close) < lookback or len(spy_close) < lookback:
            return 0.5
        
        symbol_returns = np.diff(symbol_close[-lookback:]) / symbol_close[-lookback:-1]
        spy_returns = np.diff(spy_close[-lookback:]) / spy_close[-lookback:-1]
        
        rs_ratio = np.prod(1 + symbol_returns) / np.prod(1 + spy_returns)
        return min(max(rs_ratio - 1.0, 0), 1.0) + 0.5  # Map to 0-1 range
    
    def _calculate_rvol(self, volume, lookback):
        """Relative Volume."""
        if len(volume) < lookback * 2:
            return 1.0
        current_vol = np.mean(volume[-lookback:])
        prior_vol = np.mean(volume[-lookback*2:-lookback])
        if prior_vol > 0:
            return current_vol / prior_vol
        return 1.0
    
    def _calculate_structure_quality(self, close, period):
        """Structure quality (pivot clarity)."""
        if len(close) < period:
            return 0.5
        # Simplified: measure trend consistency
        returns = np.diff(close[-period:])
        positive = np.sum(returns > 0)
        consistency = positive / len(returns)
        return consistency
    
    def _calculate_htf_bias(self, close):
        """Higher timeframe bias (Weekly/Monthly trend)."""
        if len(close) < 126:
            return 0.5
        # Simplified: 5-week and 4-week ROC
        weekly_roc = (close[-1] - close[-35]) / close[-35]
        monthly_roc = (close[-1] - close[-126]) / close[-126]
        bias = (weekly_roc * 0.3 + monthly_roc * 0.2) / 0.5
        # Tanh map to 0-1
        return (np.tanh(bias) + 1) / 2
    
    def _calculate_rsi(self, close, period):
        """Relative Strength Index."""
        if len(close) < period:
            return 50
        deltas = np.diff(close[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _determine_regime(self, rvol, atr_pct):
        """Determine market regime (0=squeeze, 1=normal, 2=breakout)."""
        if rvol < 1.0 and atr_pct < 1.5:
            return 0  # Squeeze
        elif rvol >= 1.5 and atr_pct >= 2.0:
            return 2  # Breakout
        else:
            return 1  # Normal
    
    def run(self):
        """Execute full screening pipeline."""
        logger.info("=== NX Watchlist Generation Started ===")
        
        data = self.fetch_market_data()
        if data is None:
            logger.error("Failed to fetch market data")
            return False
        
        self.calculate_nx_scores(data)
        self.apply_nx_filters()
        success = self.save_watchlist()
        
        logger.info("=== NX Watchlist Generation Complete ===")
        return success

def main():
    generator = NXWatchlistGenerator()
    generator.run()

if __name__ == "__main__":
    main()
