#!/usr/bin/env python3
"""
NX Dynamic Watchlist Generator v2
Enhanced version of existing watchlist with NX scoring.
Works with your current watchlist structure.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
import time

# Setup logging
LOG_FILE = Path.home() / ".openclaw" / "workspace" / "trading" / "logs" / "nx_watchlist_v2.log"
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
}

class NXEnhancer:
    """Enhance existing watchlist with NX scores."""
    
    def __init__(self):
        self.long_candidates = []
        self.short_candidates = []
        self.spy_data = None
    
    def fetch_spy(self):
        """Fetch SPY for relative strength calculations."""
        try:
            logger.info("Fetching SPY data...")
            self.spy_data = yf.download("SPY", period="1y", progress=False)
            logger.info("SPY data fetched")
            return True
        except Exception as e:
            logger.error(f"Failed to fetch SPY: {e}")
            return False
    
    def fetch_symbol_data(self, symbol, max_retries=3):
        """Fetch data for a single symbol with retry logic."""
        for attempt in range(max_retries):
            try:
                data = yf.download(symbol, period="1y", progress=False)
                if data is not None and len(data) > 0:
                    return data
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt+1} for {symbol}: {e}")
                    time.sleep(1)
                else:
                    logger.error(f"Failed to fetch {symbol}: {e}")
        return None
    
    def calculate_nx_score(self, symbol, price_data):
        """Calculate NX metrics for a symbol."""
        try:
            close = price_data['Close'].values
            volume = price_data['Volume'].values
            high = price_data['High'].values
            low = price_data['Low'].values
            
            # CompScore (momentum)
            roc_21 = self._roc(close, 21)
            roc_63 = self._roc(close, 63)
            roc_126 = self._roc(close, 126)
            momentum = (roc_21 + roc_63 + roc_126) / 3
            
            atr_pct = self._atr_percent(high, low, close, 14)
            comp_score = self._normalize(momentum, atr_pct)
            
            # RS vs SPY
            rs_pct = self._relative_strength(close, self.spy_data['Close'].values, 252)
            
            # RVol
            rvol = self._rvol(volume, 50)
            
            # Structure quality
            struct_q = self._structure(close, 20)
            
            # HTF Bias
            htf_bias = self._htf_bias(close)
            
            # RSI
            rsi = self._rsi(close, 14)
            
            # Regime
            regime = 2 if rvol > 1.5 and atr_pct > 2.0 else (0 if rvol < 1.0 and atr_pct < 1.5 else 1)
            
            # Ready flags
            long_ready = int(45 <= rsi <= 75)
            short_ready = int(25 <= rsi <= 55)
            
            # Tier
            tier = 3 if comp_score >= 0.35 else (2 if comp_score >= 0.20 else 1)
            
            return {
                "symbol": symbol,
                "price": round(close[-1], 2),
                "comp_score": round(comp_score, 3),
                "rs_pct": round(rs_pct, 3),
                "rvol": round(rvol, 2),
                "struct_q": round(struct_q, 3),
                "htf_bias": round(htf_bias, 3),
                "rsi": round(rsi, 1),
                "regime": regime,
                "long_ready": long_ready,
                "short_ready": short_ready,
                "tier": tier,
            }
        except Exception as e:
            logger.error(f"Error scoring {symbol}: {e}")
            return None
    
    def apply_filters(self, scores):
        """Apply NX filters to qualified candidates."""
        for score in scores:
            if not score:
                continue
            
            # Base filters
            if score["tier"] < 2 or score["rvol"] < NX_CRITERIA["rvol_min"] or score["struct_q"] < NX_CRITERIA["struct_q_min"]:
                continue
            
            # Long
            if (score["rs_pct"] >= NX_CRITERIA["rs_long_min"] and
                score["htf_bias"] >= NX_CRITERIA["htf_bias_long_min"] and
                score["long_ready"]):
                self.long_candidates.append(score)
            
            # Short
            if (score["rs_pct"] <= NX_CRITERIA["rs_short_max"] and
                score["htf_bias"] <= NX_CRITERIA["htf_bias_short_max"] and
                score["short_ready"]):
                self.short_candidates.append(score)
    
    def save_watchlist(self):
        """Save enhanced watchlist."""
        watchlist = {
            "generated_at": datetime.now().isoformat(),
            "long_candidates": sorted(self.long_candidates, key=lambda x: x["comp_score"], reverse=True),
            "short_candidates": sorted(self.short_candidates, key=lambda x: x["comp_score"], reverse=True),
            "nx_criteria": NX_CRITERIA,
            "summary": {
                "long_count": len(self.long_candidates),
                "short_count": len(self.short_candidates),
            }
        }
        
        try:
            with open(WATCHLIST_FILE, "w") as f:
                json.dump(watchlist, f, indent=2)
            logger.info(f"Watchlist saved: {len(self.long_candidates)} longs, {len(self.short_candidates)} shorts")
            return True
        except Exception as e:
            logger.error(f"Failed to save watchlist: {e}")
            return False
    
    # Helper methods
    def _roc(self, close, period):
        return ((close[-1] - close[-period-1]) / close[-period-1] * 100) if len(close) > period else 0
    
    def _atr_percent(self, h, l, c, p):
        tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
        return (np.mean(tr[-p:]) / c[-1] * 100) if len(tr) >= p else 0
    
    def _normalize(self, mom, atr_p):
        if atr_p > 0:
            n = (mom / (atr_p / 2.0)) * 100
        else:
            n = mom
        return min(max((n + 100) / 200, 0), 1)
    
    def _relative_strength(self, sym_c, spy_c, lb):
        if len(sym_c) < lb or len(spy_c) < lb:
            return 0.5
        sym_ret = np.prod((sym_c[-lb:] / np.roll(sym_c[-lb:], 1))[1:])
        spy_ret = np.prod((spy_c[-lb:] / np.roll(spy_c[-lb:], 1))[1:])
        rs = sym_ret / spy_ret if spy_ret > 0 else 1
        return min(max((rs - 1.0) * 0.5 + 0.5, 0), 1)
    
    def _rvol(self, vol, p):
        if len(vol) < p * 2:
            return 1.0
        return np.mean(vol[-p:]) / np.mean(vol[-p*2:-p]) if np.mean(vol[-p*2:-p]) > 0 else 1.0
    
    def _structure(self, c, p):
        if len(c) < p:
            return 0.5
        ret = np.diff(c[-p:])
        return np.sum(ret > 0) / len(ret)
    
    def _htf_bias(self, c):
        if len(c) < 126:
            return 0.5
        w_roc = (c[-1] - c[-35]) / c[-35] if len(c) > 35 else 0
        m_roc = (c[-1] - c[-126]) / c[-126] if len(c) > 126 else 0
        bias = (w_roc * 0.3 + m_roc * 0.2) / 0.5
        return (np.tanh(bias) + 1) / 2
    
    def _rsi(self, c, p):
        if len(c) < p:
            return 50
        d = np.diff(c[-p-1:])
        g = np.where(d > 0, d, 0)
        l = np.where(d < 0, -d, 0)
        rs = np.mean(g) / np.mean(l) if np.mean(l) > 0 else 100
        return 100 - (100 / (1 + rs))
    
    def run(self, symbols):
        """Run enhancement pipeline."""
        logger.info(f"Starting NX enhancement for {len(symbols)} symbols...")
        
        if not self.fetch_spy():
            logger.error("Failed to fetch SPY, aborting")
            return False
        
        scores = []
        for i, symbol in enumerate(symbols):
            logger.info(f"[{i+1}/{len(symbols)}] Scoring {symbol}...")
            data = self.fetch_symbol_data(symbol)
            if data is not None and len(data) > 100:
                score = self.calculate_nx_score(symbol, data)
                if score:
                    scores.append(score)
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"Scored {len(scores)} symbols, applying filters...")
        self.apply_filters(scores)
        success = self.save_watchlist()
        
        logger.info("NX enhancement complete")
        return success

def main():
    # Your baseline watchlist
    symbols = [
        'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN', 'BERKB',
        'AMD', 'INTC', 'QCOM', 'AVGO', 'TXN', 'SMCI', 'PLTR', 'AFRM', 'UPST', 'COIN',
        'SPY', 'QQQ', 'IWM', 'XLK', 'XLE', 'XLF', 'XLI', 'XLV', 'XLY', 'XLP',
    ]
    
    enhancer = NXEnhancer()
    enhancer.run(symbols)

if __name__ == "__main__":
    main()
