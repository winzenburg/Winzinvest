#!/usr/bin/env python3
"""
Regime Monitoring System for AMS Trading Engine
Tracks macro conditions and adjusts trading parameters dynamically.

Scoring System:
- VIX backwardation: +3
- HY OAS >400bps: +3
- Real yield breakout: +2
- NFCI >0: +1
- ISM <50: +1

Regime Bands:
- 0-1: Risk-On
- 2-3: Neutral
- 4-5: Tightening
- 6+: Defensive
"""

import logging
import os
import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yfinance as yf

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load .env so FRED_API_KEY is available when run via scheduler
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False
    logger.warning("fredapi not available. Install with: pip install fredapi")

# Configuration
REGIME_STATE_FILE = Path(__file__).parent.parent / "logs" / "regime_state.json"
REGIME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# FRED Series IDs
FRED_SERIES = {
    "DFII10": "10Y TIPS Real Yield",
    "BAMLH0A0HYM2": "ICE BofA US High Yield OAS",
    "NFCI": "Chicago Fed NFCI",
    "MANEMP": "ISM Manufacturing PMI"
}

# Priority order (lower number = higher priority)
ALERT_CONFIG = [
    {
        "indicator": "VIX_STRUCTURE",
        "priority": 1,
        "weight": 3,
        "tier": 1,
        "name": "VIX Backwardation"
    },
    {
        "indicator": "HY_OAS",
        "priority": 2,
        "weight": 3,
        "tier": 1,
        "name": "HY OAS Spike"
    },
    {
        "indicator": "REAL_YIELDS",
        "priority": 3,
        "weight": 2,
        "tier": 2,
        "name": "Real Yield Breakout"
    },
    {
        "indicator": "NFCI",
        "priority": 4,
        "weight": 1,
        "tier": 3,
        "name": "NFCI Tightening"
    },
    {
        "indicator": "ISM_MFG",
        "priority": 5,
        "weight": 1,
        "tier": 4,
        "name": "ISM Deterioration"
    },
    {
        "indicator": "COMMODITY_SURGE",
        "priority": 6,
        "weight": 2,
        "tier": 2,
        "name": "Oil Price Surge (30d +20%)"
    },
    {
        "indicator": "COMMODITY_CRISIS",
        "priority": 7,
        "weight": 3,
        "tier": 1,
        "name": "Oil Price Crisis (30d +40%)"
    },
    {
        "indicator": "NEWS_BEARISH",
        "priority": 9,
        "weight": 1,
        "tier": 3,
        "name": "Bearish News Sentiment"
    },
    {
        "indicator": "NEWS_VERY_BEARISH",
        "priority": 10,
        "weight": 2,
        "tier": 2,
        "name": "Very Bearish News Sentiment"
    },
    # Copper / metals chain
    {
        "indicator": "COPPER_SURGE",
        "priority": 13,
        "weight": 1,
        "tier": 3,
        "name": "Copper Surge (30d +20%) — construction/industrial boom"
    },
    {
        "indicator": "COPPER_COLLAPSE",
        "priority": 14,
        "weight": 1,
        "tier": 3,
        "name": "Copper Collapse (30d -20%) — industrial demand warning"
    },
    # Corn / grain chain
    {
        "indicator": "CORN_SURGE",
        "priority": 15,
        "weight": 1,
        "tier": 3,
        "name": "Corn Surge (30d +20%) — feed cost inflation signal"
    },
    {
        "indicator": "CORN_CRISIS",
        "priority": 16,
        "weight": 2,
        "tier": 2,
        "name": "Corn Crisis (30d +35%) — livestock margin squeeze"
    },
    # Soybean chain
    {
        "indicator": "SOYBEAN_SURGE",
        "priority": 17,
        "weight": 1,
        "tier": 3,
        "name": "Soybean Surge (30d +20%) — feed/crush margin pressure"
    },
    {
        "indicator": "SOYBEAN_CRISIS",
        "priority": 18,
        "weight": 2,
        "tier": 2,
        "name": "Soybean Crisis (30d +35%) — BG/ADM margin squeeze"
    },
    # USD chain
    {
        "indicator": "USD_SURGE",
        "priority": 19,
        "weight": 1,
        "tier": 3,
        "name": "USD Surge (30d +5%) — commodity price suppression"
    },
    {
        "indicator": "USD_WEAK",
        "priority": 20,
        "weight": 1,
        "tier": 3,
        "name": "USD Weakness (30d -5%) — commodity price inflation"
    },
    # Compound chain signal
    {
        "indicator": "LIVESTOCK_CHAIN",
        "priority": 21,
        "weight": 2,
        "tier": 2,
        "name": "Livestock chain alert — corn+soy elevated, food margins at risk"
    },
]


class RegimeMonitor:
    """Monitor macro regime conditions and calculate risk score."""
    
    def __init__(self, fred_api_key: Optional[str] = None):
        self.fred_api_key = fred_api_key or os.getenv("FRED_API_KEY")
        self.fred = None
        
        if FRED_AVAILABLE and self.fred_api_key:
            try:
                self.fred = Fred(api_key=self.fred_api_key)
            except Exception as e:
                logger.warning("Could not initialize FRED API: %s", e)
        
        self.state_file = REGIME_STATE_FILE
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load previous regime state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {
            "currentScore": 0,
            "previousScore": 0,
            "regime": "RISK_ON",
            "previousRegime": "RISK_ON",
            "lastUpdate": None,
            "activeAlerts": [],
            "history": []
        }
    
    def _save_state(self, state: Dict):
        """Save current regime state atomically to prevent partial reads."""
        path = Path(self.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(state, fh, indent=2)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    
    def _get_fred_data(self, series_id: str, days_back: int = 30) -> Optional[List]:
        """Fetch FRED data series using a trailing date window."""
        if not self.fred:
            return None
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            data = self.fred.get_series(series_id, start_date, end_date)
            return data
        except Exception as e:
            logger.warning("Error fetching %s: %s", series_id, e)
            return None
    
    def check_vix_structure(self) -> Dict:
        """
        Check VIX term structure for backwardation.
        Trigger: VX1/VX2 >= 1.03 OR VX1 > VX2
        Weight: +3 (Tier 1, Priority #1)
        """
        vx1: Optional[float] = None
        vx2: Optional[float] = None
        try:
            vix = yf.Ticker("^VIX")
            vix3m = yf.Ticker("^VIX3M")
            
            vx1 = float(vix.history(period="5d")['Close'].iloc[-1])
            vx2 = float(vix3m.history(period="5d")['Close'].iloc[-1])
            
            ratio = vx1 / vx2
            
            if ratio >= 1.03 or vx1 > vx2:
                return {
                    "triggered": True,
                    "indicator": "VIX_STRUCTURE",
                    "priority": 1,
                    "weight": 3,
                    "tier": 1,
                    "name": "VIX Backwardation",
                    "value": f"VX1/VX2 = {ratio:.3f}",
                    "detail": f"VIX: {vx1:.1f}, VIX3M: {vx2:.1f}"
                }
            return {
                "triggered": False,
                "indicator": "VIX_STRUCTURE",
                "priority": 1,
                "weight": 3,
                "tier": 1,
                "name": "VIX Backwardation",
                "value": f"VIX {vx1:.1f} / VIX3M {vx2:.1f} ratio={ratio:.3f}",
                "detail": f"Contango — no backwardation signal"
            }
        except Exception as e:
            logger.warning("Error checking VIX structure: %s", e)
            return {"triggered": False, "indicator": "VIX_STRUCTURE",
                    "priority": 1, "weight": 3, "tier": 1,
                    "name": "VIX Backwardation", "value": "N/A",
                    "detail": f"Data unavailable: {e}"}
    
    def check_hy_oas(self) -> Dict:
        """
        Check High Yield OAS spreads.
        Trigger: Daily >=25bps OR 10-day >=50bps OR Absolute >=400bps

        NOTE: FRED series BAMLH0A0HYM2 is in percent (e.g. 3.25 = 325 bps).
        All thresholds are stored in percent units to match.
        """
        data = self._get_fred_data("BAMLH0A0HYM2", days_back=30)
        if data is None or len(data) < 10:
            return {"triggered": False, "indicator": "HY_OAS"}

        current = data.iloc[-1]  # in % — e.g. 3.25 means 325 bps
        daily_change = current - data.iloc[-2] if len(data) >= 2 else 0
        ten_day_change = current - data.iloc[-11] if len(data) >= 11 else 0

        # Thresholds converted to % units: 25bps=0.25, 50bps=0.50, 400bps=4.00
        if daily_change >= 0.25 or ten_day_change >= 0.50 or current >= 4.00:
            return {
                "triggered": True,
                "indicator": "HY_OAS",
                "priority": 2,
                "weight": 3,
                "tier": 1,
                "name": "HY OAS Spike",
                "value": f"{current*100:.0f}bps",
                "detail": f"1d: {daily_change*100:+.0f}bps, 10d: {ten_day_change*100:+.0f}bps",
            }

        return {"triggered": False, "indicator": "HY_OAS", "current": f"{current*100:.0f}bps"}
    
    def check_real_yields(self) -> Dict:
        """
        Check 10Y TIPS real yields.
        Trigger: 5-day >=+35bps OR at/near 6mo high OR Cross >2.0%
        Weight: +2 (Tier 2, Priority #3)

        FRED series DFII10 is in percent (e.g. 2.18 = 2.18%).
        Use limit=130 to get ~6 months of daily data including most recent.
        """
        data = self._get_fred_data("DFII10", days_back=200)
        if data is None or len(data) < 5:
            return {"triggered": False, "indicator": "REAL_YIELDS"}

        current = data.iloc[-1]
        five_day_change = (current - data.iloc[-6]) if len(data) >= 6 else 0
        six_month_high = data.max()

        # Trigger if: 5-day spike, at 6mo high, or absolute level >= 2.0%
        if five_day_change >= 0.35 or current >= six_month_high * 0.99 or current >= 2.0:
            return {
                "triggered": True,
                "indicator": "REAL_YIELDS",
                "priority": 3,
                "weight": 2,
                "tier": 2,
                "name": "Real Yield Breakout",
                "value": f"{current:.2f}%",
                "detail": f"5d: {five_day_change:+.2f}%, 6mo high: {six_month_high:.2f}%",
            }

        return {"triggered": False, "indicator": "REAL_YIELDS",
                "current": f"{current:.2f}%  (6mo high {six_month_high:.2f}%)"}
    
    def check_nfci(self) -> Dict:
        """
        Check Chicago Fed NFCI.
        Trigger: Cross above 0 OR 4-week change >=+0.30

        NFCI is released weekly — 90 days = ~13 observations.
        Positive values = tighter-than-average financial conditions.
        """
        data = self._get_fred_data("NFCI", days_back=120)  # weekly series — 120 days = ~17 obs
        if data is None or len(data) < 4:
            return {"triggered": False, "indicator": "NFCI"}

        current = data.iloc[-1]
        # 4 weeks back = ~4 weekly observations
        four_week_change = (current - data.iloc[-5]) if len(data) >= 5 else 0

        if current > 0 or four_week_change >= 0.30:
            return {
                "triggered": True,
                "indicator": "NFCI",
                "priority": 4,
                "weight": 1,
                "tier": 3,
                "name": "NFCI Tightening",
                "value": f"{current:.2f}",
                "detail": f"4w change: {four_week_change:+.2f}",
            }

        return {"triggered": False, "indicator": "NFCI", "current": f"{current:.2f}"}
    
    def check_ism(self) -> Dict:
        """
        Check manufacturing activity via Industrial Production: Manufacturing (IPMAN).
        Trigger: YoY decline >= 3% OR 3-month decline >= 1.5%
        Weight: +1 (Tier 4, Priority #5)

        ISM PMI is proprietary and not on FRED. IPMAN (Fed Industrial Production)
        is the best available proxy — YoY contraction reliably maps to PMI < 50.
        """
        data = self._get_fred_data("IPMAN", days_back=480)
        if data is None or len(data) < 6:
            return {"triggered": False, "indicator": "ISM_MFG"}

        current = float(data.iloc[-1])
        three_month_ago = float(data.iloc[-4]) if len(data) >= 4 else current
        year_ago = float(data.iloc[-13]) if len(data) >= 13 else None

        three_month_chg_pct = (current - three_month_ago) / abs(three_month_ago) * 100
        yoy_chg_pct = (current - year_ago) / abs(year_ago) * 100 if year_ago else None

        triggered = three_month_chg_pct <= -1.5 or (yoy_chg_pct is not None and yoy_chg_pct <= -3.0)
        yoy_str = f"{yoy_chg_pct:+.1f}% YoY" if yoy_chg_pct is not None else ""
        if triggered:
            return {
                "triggered": True,
                "indicator": "ISM_MFG",
                "priority": 5,
                "weight": 1,
                "tier": 4,
                "name": "Manufacturing Contraction (IPMAN)",
                "value": f"IPMAN {current:.1f}",
                "detail": f"3mo: {three_month_chg_pct:+.1f}%  {yoy_str}",
            }

        return {"triggered": False, "indicator": "ISM_MFG",
                "current": f"IPMAN {current:.1f}  3mo {three_month_chg_pct:+.1f}%  {yoy_str}"}
    
    def get_regime_from_score(self, score: int) -> Dict:
        """Map score to regime band and AMS parameters."""
        if score <= 1:
            return {
                "band": "RISK_ON",
                "emoji": "🟢",
                "zEnter": 2.0,
                "sizeMultiplier": 1.0,
                "atrMultiplier": 1.0,
                "cooldown": 3
            }
        elif score <= 3:
            return {
                "band": "NEUTRAL",
                "emoji": "⚠️",
                "zEnter": 2.25,
                "sizeMultiplier": 0.75,
                "atrMultiplier": 0.9,
                "cooldown": 5
            }
        elif score <= 5:
            return {
                "band": "TIGHTENING",
                "emoji": "🟠",
                "zEnter": 2.5,
                "sizeMultiplier": 0.5,
                "atrMultiplier": 0.8,
                "cooldown": 8
            }
        else:
            return {
                "band": "DEFENSIVE",
                "emoji": "🔴",
                "zEnter": 3.0,
                "sizeMultiplier": 0.25,
                "atrMultiplier": 0.7,
                "cooldown": 13
            }
    
    @staticmethod
    def _commodity_30d_pct(symbol: str) -> Optional[float]:
        """Download 60 days of a futures symbol and return 30-day % change."""
        try:
            hist = yf.download(symbol, period="60d", progress=False, auto_adjust=True)
            if hist is None or len(hist) < 10:
                return None
            closes = hist["Close"].dropna()
            if len(closes) < 2:
                return None
            current = float(closes.iloc[-1])
            past_idx = max(0, len(closes) - 22)
            past = float(closes.iloc[past_idx])
            if past == 0:
                return None
            return ((current - past) / past) * 100
        except Exception:
            return None

    def check_commodity_triggers(self) -> Dict:
        """
        Check 30-day % change across six supply chain commodities.

        Oil (CL=F):       +40% CRISIS (+3), +20% SURGE (+2), -20% COLLAPSE (+1)
        Wheat (ZW=F):     +30% CRISIS (+1), +15% SURGE (info)
        Natural Gas (NG=F):+50% CRISIS (+1), +25% SURGE (info)
        Copper (HG=F):    +20% SURGE (+1), -20% COLLAPSE (+1)
        Corn (ZC=F):      +35% CRISIS (+2), +20% SURGE (+1)
        Soybeans (ZS=F):  +35% CRISIS (+2), +20% SURGE (+1)
        USD (DX-Y.NYB):   +5% SURGE (+1), -5% WEAK (+1)

        Compound signals:
          food_chain_alert     = oil SURGE/CRISIS + (wheat or natgas) elevated
          livestock_chain_alert = corn or soy SURGE/CRISIS
        """
        now_iso = datetime.now().isoformat()
        triggers: Dict = {
            "oil_30d_pct": 0.0,
            "oil_level": "NORMAL",
            "energy_multiplier": 1.0,
            "wheat_30d_pct": 0.0,
            "wheat_level": "NORMAL",
            "natgas_30d_pct": 0.0,
            "natgas_level": "NORMAL",
            "copper_30d_pct": 0.0,
            "copper_level": "NORMAL",
            "copper_multiplier": 1.0,
            "corn_30d_pct": 0.0,
            "corn_level": "NORMAL",
            "soybean_30d_pct": 0.0,
            "soybean_level": "NORMAL",
            "usd_30d_pct": 0.0,
            "usd_level": "NORMAL",
            "food_chain_alert": False,
            "livestock_chain_alert": False,
            "checked_at": now_iso,
        }
        result: Dict = {
            "triggered": False,
            "indicator": "COMMODITY_NONE",
            "priority": 6,
            "weight": 0,
            "tier": 3,
            "name": "Commodities Normal",
            "value": "N/A",
            "detail": "",
            "commodity_triggers": triggers,
        }

        try:
            oil_pct    = self._commodity_30d_pct("CL=F")
            wheat_pct  = self._commodity_30d_pct("ZW=F")
            natgas_pct = self._commodity_30d_pct("NG=F")
            copper_pct = self._commodity_30d_pct("HG=F")
            corn_pct   = self._commodity_30d_pct("ZC=F")
            soy_pct    = self._commodity_30d_pct("ZS=F")
            usd_pct    = self._commodity_30d_pct("DX-Y.NYB")

            details: List[str] = []

            # ----------------------------------------------------------------
            # Oil → petrochemicals / shipping / energy sector
            # ----------------------------------------------------------------
            oil_level = "NORMAL"
            energy_mult = 1.0
            if oil_pct is not None:
                triggers["oil_30d_pct"] = round(oil_pct, 2)
                if oil_pct >= 40:
                    oil_level = "CRISIS"
                    energy_mult = 1.35
                    result.update({
                        "triggered": True,
                        "indicator": "COMMODITY_CRISIS",
                        "priority": 7,
                        "weight": 3,
                        "tier": 1,
                        "name": "Oil Price Crisis (30d +40%)",
                    })
                elif oil_pct >= 20:
                    oil_level = "SURGE"
                    energy_mult = 1.15
                    result.update({
                        "triggered": True,
                        "indicator": "COMMODITY_SURGE",
                        "priority": 6,
                        "weight": 2,
                        "tier": 2,
                        "name": "Oil Price Surge (30d +20%)",
                    })
                elif oil_pct <= -20:
                    oil_level = "COLLAPSE"
                    energy_mult = 0.80
                    result.update({
                        "triggered": True,
                        "indicator": "COMMODITY_COLLAPSE",
                        "priority": 8,
                        "weight": 1,
                        "tier": 3,
                        "name": "Oil Price Collapse (30d -20%)",
                    })
                details.append(f"Oil {oil_pct:+.1f}%")
            triggers["oil_level"] = oil_level
            triggers["energy_multiplier"] = energy_mult

            # ----------------------------------------------------------------
            # Wheat → food cost inflation
            # ----------------------------------------------------------------
            wheat_level = "NORMAL"
            if wheat_pct is not None:
                triggers["wheat_30d_pct"] = round(wheat_pct, 2)
                if wheat_pct >= 30:
                    wheat_level = "CRISIS"
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "WHEAT_CRISIS",
                            "priority": 11,
                            "weight": 1,
                            "tier": 3,
                            "name": "Wheat Price Crisis (30d +30%)",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 1
                elif wheat_pct >= 15:
                    wheat_level = "SURGE"
                details.append(f"Wheat {wheat_pct:+.1f}%")
            triggers["wheat_level"] = wheat_level

            # ----------------------------------------------------------------
            # Natural Gas → electricity → fertilizer feedstock
            # ----------------------------------------------------------------
            natgas_level = "NORMAL"
            if natgas_pct is not None:
                triggers["natgas_30d_pct"] = round(natgas_pct, 2)
                if natgas_pct >= 50:
                    natgas_level = "CRISIS"
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "NATGAS_CRISIS",
                            "priority": 12,
                            "weight": 1,
                            "tier": 3,
                            "name": "Natural Gas Crisis (30d +50%)",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 1
                elif natgas_pct >= 25:
                    natgas_level = "SURGE"
                details.append(f"NatGas {natgas_pct:+.1f}%")
            triggers["natgas_level"] = natgas_level

            # ----------------------------------------------------------------
            # Copper → construction / industrial activity ("Dr. Copper")
            # Surge = industrial expansion (boost Materials, Industrials)
            # Collapse = demand warning (defensive signal)
            # ----------------------------------------------------------------
            copper_level = "NORMAL"
            copper_mult = 1.0
            if copper_pct is not None:
                triggers["copper_30d_pct"] = round(copper_pct, 2)
                if copper_pct >= 20:
                    copper_level = "SURGE"
                    copper_mult = 1.10
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "COPPER_SURGE",
                            "priority": 13,
                            "weight": 1,
                            "tier": 3,
                            "name": "Copper Surge (30d +20%) — construction/industrial boom",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 1
                elif copper_pct <= -20:
                    copper_level = "COLLAPSE"
                    copper_mult = 0.88
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "COPPER_COLLAPSE",
                            "priority": 14,
                            "weight": 1,
                            "tier": 3,
                            "name": "Copper Collapse (30d -20%) — industrial demand warning",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 1
                details.append(f"Copper {copper_pct:+.1f}%")
            triggers["copper_level"] = copper_level
            triggers["copper_multiplier"] = copper_mult

            # ----------------------------------------------------------------
            # Corn → ethanol blending / animal feed margins
            # ----------------------------------------------------------------
            corn_level = "NORMAL"
            if corn_pct is not None:
                triggers["corn_30d_pct"] = round(corn_pct, 2)
                if corn_pct >= 35:
                    corn_level = "CRISIS"
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "CORN_CRISIS",
                            "priority": 16,
                            "weight": 2,
                            "tier": 2,
                            "name": "Corn Crisis (30d +35%) — livestock margin squeeze",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 2
                elif corn_pct >= 20:
                    corn_level = "SURGE"
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "CORN_SURGE",
                            "priority": 15,
                            "weight": 1,
                            "tier": 3,
                            "name": "Corn Surge (30d +20%) — feed cost inflation signal",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 1
                details.append(f"Corn {corn_pct:+.1f}%")
            triggers["corn_level"] = corn_level

            # ----------------------------------------------------------------
            # Soybeans → crush spread / BG/ADM direct margin signal
            # ----------------------------------------------------------------
            soybean_level = "NORMAL"
            if soy_pct is not None:
                triggers["soybean_30d_pct"] = round(soy_pct, 2)
                if soy_pct >= 35:
                    soybean_level = "CRISIS"
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "SOYBEAN_CRISIS",
                            "priority": 18,
                            "weight": 2,
                            "tier": 2,
                            "name": "Soybean Crisis (30d +35%) — BG/ADM margin squeeze",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 2
                elif soy_pct >= 20:
                    soybean_level = "SURGE"
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "SOYBEAN_SURGE",
                            "priority": 17,
                            "weight": 1,
                            "tier": 3,
                            "name": "Soybean Surge (30d +20%) — feed/crush margin pressure",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 1
                details.append(f"Soy {soy_pct:+.1f}%")
            triggers["soybean_level"] = soybean_level

            # ----------------------------------------------------------------
            # USD Index → strong dollar suppresses commodity prices and EM
            # exporters; weak dollar inflates commodity prices globally.
            # ----------------------------------------------------------------
            usd_level = "NORMAL"
            usd_mult = 1.0  # applied to Materials/Energy (inverse of USD strength)
            if usd_pct is not None:
                triggers["usd_30d_pct"] = round(usd_pct, 2)
                if usd_pct >= 5:
                    usd_level = "SURGE"
                    usd_mult = 0.90  # strong dollar → cheaper commodities → penalise commodity sectors
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "USD_SURGE",
                            "priority": 19,
                            "weight": 1,
                            "tier": 3,
                            "name": "USD Surge (30d +5%) — commodity price suppression",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 1
                elif usd_pct <= -5:
                    usd_level = "WEAK"
                    usd_mult = 1.10  # weak dollar → expensive commodities → boost commodity sectors
                    if not result.get("triggered"):
                        result.update({
                            "triggered": True,
                            "indicator": "USD_WEAK",
                            "priority": 20,
                            "weight": 1,
                            "tier": 3,
                            "name": "USD Weakness (30d -5%) — commodity price inflation",
                        })
                    else:
                        result["weight"] = result.get("weight", 0) + 1
                details.append(f"USD {usd_pct:+.1f}%")
            triggers["usd_level"] = usd_level
            triggers["usd_multiplier"] = usd_mult

            # ----------------------------------------------------------------
            # Compound chain signals
            # ----------------------------------------------------------------
            oil_elevated   = oil_level in ("SURGE", "CRISIS")
            grain_elevated = wheat_level in ("SURGE", "CRISIS") or natgas_level in ("SURGE", "CRISIS")
            triggers["food_chain_alert"] = oil_elevated and grain_elevated

            livestock_elevated = corn_level in ("SURGE", "CRISIS") or soybean_level in ("SURGE", "CRISIS")
            triggers["livestock_chain_alert"] = livestock_elevated
            if livestock_elevated and not result.get("triggered"):
                result.update({
                    "triggered": True,
                    "indicator": "LIVESTOCK_CHAIN",
                    "priority": 21,
                    "weight": 2,
                    "tier": 2,
                    "name": "Livestock chain alert — corn+soy elevated, food margins at risk",
                })

            result["value"] = ", ".join(details) if details else "N/A"
            result["detail"] = (
                f"Oil={oil_level}, Wheat={wheat_level}, NatGas={natgas_level}, "
                f"Copper={copper_level}, Corn={corn_level}, Soy={soybean_level}, USD={usd_level}"
            )
            result["commodity_triggers"] = triggers

        except Exception as exc:
            logger.warning("Commodity trigger check failed: %s", exc)

        return result

    def check_news_sentiment(self) -> Dict:
        """
        Read news_sentiment.json and trigger if macro sentiment is strongly negative.

        Two sources are blended:
          1. Marketaux (hourly, 2-hour staleness window) — stored in macro_sentiment
          2. Bulltard Substack recap (daily, 24-hour staleness window) — stored in
             bulltard_bias_score / bulltard_updated_at

        If only one source is fresh, that source governs.  If both are fresh, the
        pre-blended macro_sentiment value is used (the puller already does the blend).

        Thresholds:
          score <= -0.7 -> NEWS_VERY_BEARISH, weight +2
          score <= -0.5 -> NEWS_BEARISH,      weight +1
        """
        result: Dict = {
            "triggered": False,
            "indicator": "NEWS_NEUTRAL",
            "priority": 9,
            "weight": 0,
            "tier": 4,
            "name": "News Sentiment Normal",
            "value": "N/A",
            "detail": "",
        }
        sentiment_file = Path(self.state_file).parent / "news_sentiment.json"
        if not sentiment_file.exists():
            result["detail"] = "No news sentiment data available"
            return result

        try:
            data = json.loads(sentiment_file.read_text(encoding="utf-8"))
            now  = datetime.now()

            # ── Marketaux signal (2-hour window) ──────────────────────────────
            marketaux_score: Optional[float] = None
            ts_str = data.get("timestamp", "")
            if ts_str:
                try:
                    age_h = (now - datetime.fromisoformat(ts_str)).total_seconds() / 3600
                    if age_h <= 2:
                        v = data.get("macro_sentiment")
                        if isinstance(v, (int, float)):
                            marketaux_score = float(v)
                except Exception:
                    pass

            # ── Bulltard signal (24-hour window) ─────────────────────────────
            bulltard_score: Optional[float] = None
            bulltard_label = ""
            bt_str = data.get("bulltard_updated_at", "")
            if bt_str:
                try:
                    age_h = (now - datetime.fromisoformat(bt_str)).total_seconds() / 3600
                    if age_h <= 24:
                        v = data.get("bulltard_bias_score")
                        if isinstance(v, (int, float)):
                            bulltard_score = float(v)
                            bulltard_label = str(data.get("bulltard_bias_label", ""))
                except Exception:
                    pass

            # ── Combine ───────────────────────────────────────────────────────
            if marketaux_score is not None and bulltard_score is not None:
                # Both fresh: 60% Marketaux, 40% Bulltard
                macro_sent = round(0.6 * marketaux_score + 0.4 * bulltard_score, 3)
                source_desc = f"Marketaux {marketaux_score:+.2f} + Bulltard {bulltard_score:+.2f} ({bulltard_label})"
            elif bulltard_score is not None:
                macro_sent = bulltard_score
                source_desc = f"Bulltard only: {bulltard_label} ({bulltard_score:+.2f})"
            elif marketaux_score is not None:
                macro_sent = marketaux_score
                articles = data.get("articles_analyzed", 0)
                source_desc = f"Marketaux only ({articles} articles)"
            else:
                result["detail"] = "All news data is stale — skipping"
                return result

            port_sent = data.get("portfolio_sentiment", 0.0)
            if not isinstance(port_sent, (int, float)):
                port_sent = 0.0

            result["value"]  = f"Macro: {macro_sent:+.3f}, Portfolio: {port_sent:+.3f}"
            result["detail"] = source_desc

            if macro_sent <= -0.7:
                result.update({
                    "triggered": True,
                    "indicator": "NEWS_VERY_BEARISH",
                    "priority": 10,
                    "weight": 2,
                    "tier": 2,
                    "name": "Very Bearish News Sentiment",
                })
            elif macro_sent <= -0.5:
                result.update({
                    "triggered": True,
                    "indicator": "NEWS_BEARISH",
                    "priority": 9,
                    "weight": 1,
                    "tier": 3,
                    "name": "Bearish News Sentiment",
                })

        except (OSError, ValueError, TypeError) as exc:
            logger.warning("News sentiment check failed: %s", exc)

        return result

    def calculate_regime(self) -> Dict:
        """Run all checks and calculate regime state."""
        
        # Run all checks
        checks = [
            self.check_vix_structure(),
            self.check_hy_oas(),
            self.check_real_yields(),
            self.check_nfci(),
            self.check_ism(),
            self.check_commodity_triggers(),
            self.check_news_sentiment()
        ]
        
        # Filter triggered alerts and sort by priority
        active_alerts = [c for c in checks if c.get("triggered")]
        active_alerts.sort(key=lambda x: x["priority"])
        
        # Calculate total score
        total_score = sum(a["weight"] for a in active_alerts)
        
        # Get regime parameters
        regime_params = self.get_regime_from_score(total_score)
        
        # Get inactive indicators
        inactive = [c for c in checks if not c.get("triggered")]

        # Extract commodity trigger data from check results
        commodity_triggers: Dict = {
            "oil_30d_pct": 0.0, "oil_level": "NORMAL", "energy_multiplier": 1.0,
            "wheat_30d_pct": 0.0, "wheat_level": "NORMAL",
            "natgas_30d_pct": 0.0, "natgas_level": "NORMAL",
            "copper_30d_pct": 0.0, "copper_level": "NORMAL", "copper_multiplier": 1.0,
            "corn_30d_pct": 0.0, "corn_level": "NORMAL",
            "soybean_30d_pct": 0.0, "soybean_level": "NORMAL",
            "usd_30d_pct": 0.0, "usd_level": "NORMAL", "usd_multiplier": 1.0,
            "food_chain_alert": False, "livestock_chain_alert": False,
            "checked_at": datetime.now().isoformat(),
        }
        for c in checks:
            if "commodity_triggers" in c:
                commodity_triggers = c["commodity_triggers"]
                break
        
        return {
            "score": total_score,
            "regime": regime_params["band"],
            "emoji": regime_params["emoji"],
            "parameters": {
                "zEnter": regime_params["zEnter"],
                "sizeMultiplier": regime_params["sizeMultiplier"],
                "atrMultiplier": regime_params["atrMultiplier"],
                "cooldown": regime_params["cooldown"]
            },
            "activeAlerts": active_alerts,
            "inactiveIndicators": inactive,
            "commodity_triggers": commodity_triggers,
            "timestamp": datetime.now().isoformat()
        }
    
    def check_and_alert(self) -> Dict:
        """Check regime and determine if alert needed."""
        current = self.calculate_regime()
        previous_regime = self.state.get("regime", "RISK_ON")
        
        # Determine if regime band changed
        regime_changed = current["regime"] != previous_regime
        
        # Update state
        new_state = {
            "currentScore": current["score"],
            "previousScore": self.state.get("currentScore", 0),
            "regime": current["regime"],
            "previousRegime": previous_regime,
            "lastUpdate": current["timestamp"],
            "activeAlerts": current["activeAlerts"],
            "parameters": current["parameters"],
            "commodity_triggers": current.get("commodity_triggers", {}),
            "history": self.state.get("history", [])[-20:]  # Keep last 20
        }
        
        # Add to history if regime changed
        if regime_changed:
            new_state["history"].append({
                "timestamp": current["timestamp"],
                "score": current["score"],
                "regime": current["regime"],
                "event": f"{previous_regime} → {current['regime']}"
            })
        
        self._save_state(new_state)
        
        return {
            **current,
            "alertNeeded": regime_changed,
            "previousRegime": previous_regime
        }


def format_regime_report(result: Dict, include_inactive: bool = True) -> str:
    """Format regime check result as readable report."""
    
    lines = []
    lines.append("=" * 60)
    lines.append("MACRO REGIME CHECK")
    lines.append("=" * 60)
    lines.append("")
    
    emoji = result.get("emoji", "")
    regime = result.get("regime", "UNKNOWN")
    score = result.get("score", 0)
    
    lines.append(f"Regime: {emoji} {regime} (Score {score}/10)")
    lines.append("")
    
    # Active alerts
    active = result.get("activeAlerts", [])
    if active:
        lines.append("Active Alerts (priority order):")
        for alert in active:
            priority = alert["priority"]
            name = alert["name"]
            value = alert["value"]
            detail = alert.get("detail", "")
            weight = alert["weight"]
            lines.append(f"├─ #{priority} {name}: {value} (+{weight})")
            if detail:
                lines.append(f"│  {detail}")
        lines.append("")
    else:
        lines.append("✅ No active alerts")
        lines.append("")
    
    # Inactive indicators (optional)
    if include_inactive:
        inactive = result.get("inactiveIndicators", [])
        if inactive:
            lines.append("Inactive:")
            for ind in inactive:
                indicator = ind.get("indicator", "UNKNOWN")
                current_val = ind.get("current", "N/A")
                lines.append(f"├─ ✅ {indicator}: {current_val}")
            lines.append("")
    
    # AMS parameters
    params = result.get("parameters", {})
    lines.append(f"📋 AMS Parameters ({regime}):")
    lines.append(f"• zEnter: {params.get('zEnter', 'N/A')}")
    lines.append(f"• Position size: {params.get('sizeMultiplier', 0)*100:.0f}%")
    lines.append(f"• ATR multiplier: {params.get('atrMultiplier', 1.0):.1f}x")
    lines.append(f"• Cooldown: {params.get('cooldown', 'N/A')} bars")
    lines.append("")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)


def main():
    """Run regime check."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Macro regime monitoring")
    parser.add_argument("--alert", action="store_true", help="Check if alert needed")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--brief", action="store_true", help="Brief output (no inactive)")
    args = parser.parse_args()
    
    monitor = RegimeMonitor()
    
    if args.alert:
        result = monitor.check_and_alert()
    else:
        result = monitor.calculate_regime()
        result["alertNeeded"] = False
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_regime_report(result, include_inactive=not args.brief))
        
        if result.get("alertNeeded"):
            prev = result.get("previousRegime", "UNKNOWN")
            curr = result.get("regime", "UNKNOWN")
            print(f"\n🚨 REGIME CHANGE: {prev} → {curr}")


if __name__ == "__main__":
    main()
