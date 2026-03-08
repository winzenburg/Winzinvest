#!/usr/bin/env python3
"""
Helper to get current regime parameters for webhook listener.
Returns AMS parameter adjustments based on macro regime.
"""

import json
from pathlib import Path
from typing import Dict

REGIME_STATE_FILE = Path(__file__).parent.parent / "logs" / "regime_state.json"


def get_regime_params() -> Dict:
    """
    Load current regime score and return AMS parameters.
    
    Returns dict with:
    - score: Current regime score (0-10)
    - regime: Regime band (RISK_ON, NEUTRAL, TIGHTENING, DEFENSIVE)
    - zEnter: Z-score entry threshold
    - sizeMultiplier: Position size multiplier (0.0-1.0)
    - atrMultiplier: ATR stop distance multiplier
    - cooldown: Bars to wait before re-entry
    """
    
    # Default to Risk-On if no regime data exists
    default = {
        "score": 0,
        "regime": "RISK_ON",
        "emoji": "🟢",
        "zEnter": 2.0,
        "sizeMultiplier": 1.0,
        "atrMultiplier": 1.0,
        "cooldown": 3
    }
    
    if not REGIME_STATE_FILE.exists():
        return default
    
    try:
        with open(REGIME_STATE_FILE) as f:
            state = json.load(f)
        
        # Extract parameters
        return {
            "score": state.get("currentScore", 0),
            "regime": state.get("regime", "RISK_ON"),
            "emoji": "🟢" if state.get("regime") == "RISK_ON" else
                     "⚠️" if state.get("regime") == "NEUTRAL" else
                     "🟠" if state.get("regime") == "TIGHTENING" else "🔴",
            **state.get("parameters", {
                "zEnter": 2.0,
                "sizeMultiplier": 1.0,
                "atrMultiplier": 1.0,
                "cooldown": 3
            })
        }
    except Exception as e:
        print(f"Error loading regime state: {e}")
        return default


def format_regime_context() -> str:
    """Format regime info for inclusion in trade messages."""
    params = get_regime_params()
    
    return (
        f"{params['emoji']} Regime: {params['regime']} (score {params['score']}/10)\n"
        f"Size: {params['sizeMultiplier']*100:.0f}% | "
        f"Z-threshold: {params['zEnter']} | "
        f"ATR: {params['atrMultiplier']:.1f}x"
    )


if __name__ == "__main__":
    # Test
    params = get_regime_params()
    print(json.dumps(params, indent=2))
    print("\n" + format_regime_context())
