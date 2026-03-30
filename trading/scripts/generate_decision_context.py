#!/usr/bin/env python3
"""
Generate Decision Context — Educational Tooltips

Enriches every open position and recent decision with "Why?" context.
Writes to logs/decision_context.json for tooltip consumption.

Examples:
- "Why did we enter TSLA?" → "Conviction 0.78 (above 0.55 threshold), CHOPPY regime allows momentum plays, Technology sector at 22% (below 30% limit)"
- "Why did we block AAPL?" → "Conviction 0.52 (below 0.55 threshold)"
- "Why is the stop at $180?" → "2.0× ATR ($4.50) from entry $185.50"

Runs daily after narrative generation (post-close).
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"
TRADE_DB = TRADING_DIR / "logs" / "trades.db"
REGIME_CONTEXT = TRADING_DIR / "logs" / "regime_context.json"
ADAPTIVE_CONFIG = TRADING_DIR / "logs" / "adaptive_config.json"
OUTPUT_FILE = TRADING_DIR / "logs" / "decision_context.json"


def load_open_positions() -> List[Dict[str, Any]]:
    """Load open positions from trade DB."""
    try:
        import sqlite3
        
        if not TRADE_DB.exists():
            return []
        
        conn = sqlite3.connect(str(TRADE_DB))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trades 
            WHERE status = 'Filled' 
            AND exit_price IS NULL
            ORDER BY timestamp DESC
        """)
        
        positions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return positions
    
    except Exception as e:
        logger.warning("Could not load positions from DB: %s", e)
        return []


def load_recent_decisions(days: int = 7) -> List[Dict[str, Any]]:
    """Load recent execution decisions (last N days)."""
    if not EXECUTION_LOG.exists():
        return []
    
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    decisions: List[Dict[str, Any]] = []
    
    try:
        for line in EXECUTION_LOG.read_text().strip().splitlines():
            line = line.strip()
            if not line:
                continue
            
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                
                ts = obj.get("timestamp") or ""
                if ts >= cutoff:
                    decisions.append(obj)
            
            except (json.JSONDecodeError, ValueError):
                continue
    
    except Exception as e:
        logger.warning("Could not load executions: %s", e)
    
    return decisions


def get_conviction_thresholds() -> Dict[str, float]:
    """Load conviction thresholds from adaptive_config.json."""
    defaults = {"min_conviction_long": 0.55, "min_conviction_short": 0.45}
    
    if not ADAPTIVE_CONFIG.exists():
        return defaults
    
    try:
        data = json.loads(ADAPTIVE_CONFIG.read_text())
        return {
            "min_conviction_long": data.get("min_conviction_long", defaults["min_conviction_long"]),
            "min_conviction_short": data.get("min_conviction_short", defaults["min_conviction_short"]),
        }
    except Exception:
        return defaults


def explain_entry(record: Dict[str, Any]) -> str:
    """Generate explanation for why we entered this position."""
    parts = []
    
    # Conviction
    conviction = record.get("conviction_score")
    if conviction is not None:
        side = record.get("side", "").upper()
        thresholds = get_conviction_thresholds()
        threshold = thresholds["min_conviction_short"] if side == "SHORT" or side == "SELL" else thresholds["min_conviction_long"]
        parts.append(f"Conviction: {conviction:.2f} (threshold: {threshold:.2f})")
    
    # Strategy/Reason
    reason = record.get("reason") or record.get("entry_reason")
    if reason:
        parts.append(reason)
    
    # Regime at entry
    regime = record.get("regime")
    if regime:
        parts.append(f"Market regime: {regime}")
    
    # Strategy source
    strategy = record.get("strategy")
    if strategy:
        parts.append(f"Strategy: {strategy}")
    
    return " · ".join(parts) if parts else "Entry criteria met"


def explain_stop(record: Dict[str, Any]) -> str:
    """Explain why the stop is at its current level."""
    stop_price = record.get("stop_price")
    entry_price = record.get("entry_price")
    
    if not stop_price or not entry_price:
        return "Stop order placed for risk management"
    
    distance = abs(entry_price - stop_price)
    distance_pct = (distance / entry_price) * 100
    
    # Try to infer ATR multiple
    atr_mult = "unknown"
    stop_metadata = record.get("stop_metadata") or {}
    if "atr_mult" in stop_metadata:
        atr_mult = f"{stop_metadata['atr_mult']}×"
    
    return f"Stop at ${stop_price:.2f} ({distance_pct:.1f}% from entry) — ATR multiplier: {atr_mult}"


def explain_rejection(record: Dict[str, Any]) -> str:
    """Explain why signal was blocked."""
    reason = record.get("reason", "Risk gate triggered")
    
    # Enrich with specific details if available
    conviction = record.get("conviction_score")
    if conviction is not None and "conviction" in reason.lower():
        side = record.get("side", "").upper()
        thresholds = get_conviction_thresholds()
        threshold = thresholds["min_conviction_short"] if side == "SHORT" else thresholds["min_conviction_long"]
        return f"{reason}. Score: {conviction:.2f}, Required: {threshold:.2f}"
    
    return reason


def build_context_map() -> Dict[str, Any]:
    """Build complete context map for all positions and recent decisions."""
    positions = load_open_positions()
    recent_decisions = load_recent_decisions(days=7)
    
    context = {
        "generated_at": datetime.now().isoformat(),
        "positions": {},
        "decisions": {},
    }
    
    # Context for open positions
    for pos in positions:
        symbol = pos.get("symbol", "")
        if not symbol:
            continue
        
        context["positions"][symbol] = {
            "entry_explanation": explain_entry(pos),
            "stop_explanation": explain_stop(pos) if pos.get("stop_price") else None,
            "holding_days": pos.get("holding_days", 0),
            "strategy": pos.get("strategy", ""),
            "entry_date": pos.get("timestamp", ""),
        }
    
    # Context for recent decisions
    for decision in recent_decisions:
        key = f"{decision.get('symbol', '')}_{decision.get('timestamp', '')}"
        status = decision.get("status", "").upper()
        
        if status in ("FILLED", "FILL"):
            context["decisions"][key] = {
                "type": "entry",
                "symbol": decision.get("symbol"),
                "explanation": explain_entry(decision),
                "timestamp": decision.get("timestamp"),
            }
        
        elif status in ("REJECTED", "BLOCKED", "SKIPPED"):
            context["decisions"][key] = {
                "type": "blocked",
                "symbol": decision.get("symbol"),
                "explanation": explain_rejection(decision),
                "timestamp": decision.get("timestamp"),
            }
    
    return context


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    logger.info("Generating decision context for tooltips...")
    
    try:
        context = build_context_map()
        
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(context, indent=2))
        
        logger.info("✓ Decision context written to %s", OUTPUT_FILE)
        logger.info("  Positions: %d, Recent decisions: %d",
                   len(context["positions"]),
                   len(context["decisions"]))
    
    except Exception as e:
        logger.error("Failed to generate decision context: %s", e, exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
