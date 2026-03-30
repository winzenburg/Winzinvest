#!/usr/bin/env python3
"""
Generate System Benchmarks

Calculates aggregate statistics across ALL users for comparative context.
Powers "Your win rate: 68% vs system avg: 62%" displays.

Writes to logs/system_benchmarks.json.
Runs weekly (Sundays) alongside user segmentation.

Privacy: Only aggregate stats, no individual user data exposed.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

TRADE_DB = TRADING_DIR / "logs" / "trades.db"
OUTPUT_FILE = TRADING_DIR / "logs" / "system_benchmarks.json"


def calculate_benchmarks() -> Dict[str, Any]:
    """Calculate aggregate performance benchmarks across all users."""
    
    try:
        import sqlite3
        
        if not TRADE_DB.exists():
            logger.warning("Trade DB not found")
            return {}
        
        conn = sqlite3.connect(str(TRADE_DB))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Closed trades (last 90 days)
        cutoff = (datetime.now() - timedelta(days=90)).isoformat()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                AVG(CASE WHEN exit_price IS NOT NULL THEN realized_pnl ELSE NULL END) as avg_pnl,
                AVG(CASE WHEN exit_price IS NOT NULL AND realized_pnl_pct IS NOT NULL THEN realized_pnl_pct ELSE NULL END) as avg_return_pct,
                AVG(CASE WHEN r_multiple IS NOT NULL THEN r_multiple ELSE NULL END) as avg_r_multiple,
                MAX(realized_pnl) as best_trade,
                MIN(realized_pnl) as worst_trade
            FROM trades
            WHERE exit_price IS NOT NULL
            AND timestamp >= ?
        """, (cutoff,))
        
        row = cursor.fetchone()
        
        total_trades = row["total_trades"] or 0
        wins = row["wins"] or 0
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Strategy breakdown
        cursor.execute("""
            SELECT 
                strategy,
                COUNT(*) as count,
                AVG(realized_pnl) as avg_pnl,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            FROM trades
            WHERE exit_price IS NOT NULL
            AND timestamp >= ?
            GROUP BY strategy
            HAVING count >= 5
        """, (cutoff,))
        
        strategies = {}
        for s_row in cursor.fetchall():
            strategies[s_row["strategy"]] = {
                "count": s_row["count"],
                "avg_pnl": round(s_row["avg_pnl"] or 0, 2),
                "win_rate": round((s_row["win_rate"] or 0) * 100, 1),
            }
        
        conn.close()
        
        benchmarks = {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "avg_pnl": round(row["avg_pnl"] or 0, 2),
            "avg_return_pct": round(row["avg_return_pct"] or 0, 2),
            "avg_r_multiple": round(row["avg_r_multiple"] or 0, 2),
            "best_trade": round(row["best_trade"] or 0, 2),
            "worst_trade": round(row["worst_trade"] or 0, 2),
            "strategies": strategies,
        }
        
        return benchmarks
    
    except Exception as e:
        logger.error("Failed to calculate benchmarks: %s", e, exc_info=True)
        return {}


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    logger.info("Generating system benchmarks...")
    
    try:
        benchmarks = calculate_benchmarks()
        
        output = {
            "generated_at": datetime.now().isoformat(),
            "period_days": 90,
            "benchmarks": benchmarks,
        }
        
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(output, indent=2))
        
        logger.info("✓ System benchmarks written to %s", OUTPUT_FILE)
        logger.info("  Total trades: %d, Win rate: %.1f%%",
                   benchmarks.get("total_trades", 0),
                   benchmarks.get("win_rate", 0))
    
    except Exception as e:
        logger.error("Failed to generate benchmarks: %s", e, exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
