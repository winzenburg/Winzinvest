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

import os
import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yfinance as yf

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
    print("WARNING: fredapi not available. Install with: pip install fredapi")

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
    }
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
                print(f"WARNING: Could not initialize FRED API: {e}")
        
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
            print(f"Error fetching {series_id}: {e}")
            return None
    
    def check_vix_structure(self) -> Dict:
        """
        Check VIX term structure for backwardation.
        Trigger: VX1/VX2 >= 1.03 OR VX1 > VX2
        Weight: +3 (Tier 1, Priority #1)
        """
        try:
            vix = yf.Ticker("^VIX")
            vix3m = yf.Ticker("^VIX3M")
            
            # Get most recent close
            vx1 = vix.history(period="5d")['Close'].iloc[-1]
            vx2 = vix3m.history(period="5d")['Close'].iloc[-1]
            
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
        except Exception as e:
            print(f"Error checking VIX structure: {e}")
        
        try:
            return {"triggered": False, "indicator": "VIX_STRUCTURE",
                    "current": f"VIX {vx1:.1f} / VIX3M {vx2:.1f} ratio={vx1/vx2:.3f}"}
        except Exception:
            return {"triggered": False, "indicator": "VIX_STRUCTURE"}
    
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
    
    def calculate_regime(self) -> Dict:
        """Run all checks and calculate regime state."""
        
        # Run all checks
        checks = [
            self.check_vix_structure(),
            self.check_hy_oas(),
            self.check_real_yields(),
            self.check_nfci(),
            self.check_ism()
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
