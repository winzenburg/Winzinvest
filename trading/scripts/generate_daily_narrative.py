#!/usr/bin/env python3
"""
Generate Daily Narrative — "What Happened Today"

Parses execution logs and creates natural language summary of system activity.
Writes to logs/daily_narrative.json for dashboard consumption.

Runs after market close via scheduler (or manually for testing).
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"
REGIME_CONTEXT = TRADING_DIR / "logs" / "regime_context.json"
NARRATIVE_OUTPUT = TRADING_DIR / "logs" / "daily_narrative.json"


def load_executions_today() -> List[Dict[str, Any]]:
    """Load today's execution records from JSONL log."""
    if not EXECUTION_LOG.exists():
        return []
    
    today = datetime.now().date().isoformat()
    records: List[Dict[str, Any]] = []
    
    try:
        for line in EXECUTION_LOG.read_text().strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                
                # Check if record is from today
                ts = obj.get("timestamp") or obj.get("timestamp_iso") or ""
                if ts.startswith(today):
                    records.append(obj)
            
            except (json.JSONDecodeError, ValueError):
                continue
    
    except Exception as e:
        logger.warning("Could not load execution log: %s", e)
    
    return records


def categorize_executions(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group executions by status: entered, exited, blocked."""
    categorized: Dict[str, List[Dict[str, Any]]] = {
        "entered": [],
        "exited": [],
        "blocked": [],
        "rolled": [],
        "adjusted": [],
    }
    
    for rec in records:
        status = (rec.get("status") or "").upper()
        source = (rec.get("source_script") or "").lower()
        type_val = (rec.get("type") or "").upper()
        
        # Entries
        if status in ("FILLED", "FILL") and type_val in ("SHORT", "LONG", "BUY", "SELL"):
            categorized["entered"].append(rec)
        
        # Exits (stops, take-profits)
        elif "exit" in status.lower() or "stop" in status.lower() or "tp" in status.lower():
            categorized["exited"].append(rec)
        
        # Rejections
        elif status in ("REJECTED", "BLOCKED", "SKIPPED"):
            categorized["blocked"].append(rec)
        
        # Rolls (options management)
        elif "roll" in source or "roll" in status.lower():
            categorized["rolled"].append(rec)
        
        # Adjustments (stop updates, etc.)
        elif "adjust" in source or "update" in source:
            categorized["adjusted"].append(rec)
    
    return categorized


def get_current_regime() -> str:
    """Load current market regime from regime_context.json."""
    if not REGIME_CONTEXT.exists():
        return "MIXED"
    
    try:
        data = json.loads(REGIME_CONTEXT.read_text())
        return data.get("regime", "MIXED")
    except Exception:
        return "MIXED"


def build_summary_text(categorized: Dict[str, List[Dict]], regime: str) -> str:
    """Generate natural language summary."""
    entered = len(categorized["entered"])
    exited = len(categorized["exited"])
    blocked = len(categorized["blocked"])
    total = entered + blocked
    
    if total == 0:
        return f"No new signals today. Market regime: {regime}. System is monitoring existing positions."
    
    parts = []
    
    # Opening
    parts.append(f"The system screened {total} signal{'s' if total != 1 else ''} today")
    
    # Execution
    if entered > 0:
        parts.append(f"executed {entered}")
    
    # Blocks
    if blocked > 0:
        parts.append(f"blocked {blocked}")
    
    summary = ", ".join(parts) + "."
    
    # Regime context
    summary += f" Market regime: {regime}."
    
    # Exits
    if exited > 0:
        summary += f" Closed {exited} position{'s' if exited != 1 else ''}."
    
    return summary


def build_key_decisions(categorized: Dict[str, List[Dict]]) -> List[Dict[str, str]]:
    """Extract 3-5 most interesting decisions for detail view."""
    decisions: List[Dict[str, str]] = []
    
    # Entries (take up to 3)
    for rec in categorized["entered"][:3]:
        symbol = rec.get("symbol", "")
        reason = rec.get("reason", "")
        conviction = rec.get("conviction_score")
        
        reason_text = reason if reason else "Signal met entry criteria"
        if conviction:
            reason_text += f" (conviction: {conviction:.2f})"
        
        decisions.append({
            "action": "entered",
            "symbol": symbol,
            "reason": reason_text,
        })
    
    # Blocks (take up to 3)
    for rec in categorized["blocked"][:3]:
        symbol = rec.get("symbol", "")
        reason = rec.get("reason", "Risk gate triggered")
        
        decisions.append({
            "action": "blocked",
            "symbol": symbol,
            "reason": reason,
        })
    
    # Exits (take up to 2)
    for rec in categorized["exited"][:2]:
        symbol = rec.get("symbol", "")
        reason = rec.get("exit_reason") or rec.get("reason", "Stop or target hit")
        pnl = rec.get("realized_pnl")
        
        detail = ""
        if pnl is not None:
            detail = f"P&L: ${pnl:,.0f}" if pnl < 0 else f"P&L: +${pnl:,.0f}"
        
        decisions.append({
            "action": "exited",
            "symbol": symbol,
            "reason": reason,
            "detail": detail,
        })
    
    return decisions


def count_rejection_reasons(blocked: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group blocked signals by reason and count occurrences."""
    reason_counts: Dict[str, int] = {}
    
    for rec in blocked:
        reason = rec.get("reason", "Unknown")
        
        # Normalize similar reasons
        reason_lower = reason.lower()
        if "conviction" in reason_lower:
            key = "Low conviction"
        elif "sector" in reason_lower:
            key = "Sector concentration"
        elif "regime" in reason_lower:
            key = "Regime gate"
        elif "budget" in reason_lower or "daily" in reason_lower:
            key = "Daily trade budget"
        elif "loss" in reason_lower:
            key = "Daily loss limit"
        elif "timing" in reason_lower or "gap" in reason_lower:
            key = "Market timing"
        else:
            key = reason[:50]  # Truncate long reasons
        
        reason_counts[key] = reason_counts.get(key, 0) + 1
    
    total = sum(reason_counts.values())
    reasons = [
        {
            "reason": reason,
            "count": count,
            "pct": (count / total * 100) if total > 0 else 0,
        }
        for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    
    return reasons


def generate_narrative() -> Dict[str, Any]:
    """Generate today's narrative from execution logs."""
    records = load_executions_today()
    categorized = categorize_executions(records)
    regime = get_current_regime()
    
    entered = categorized["entered"]
    exited = categorized["exited"]
    blocked = categorized["blocked"]
    
    narrative = {
        "date": datetime.now().date().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "summary": build_summary_text(categorized, regime),
        "regime": regime,
        "decisions": build_key_decisions(categorized),
        "stats": {
            "screened": len(entered) + len(blocked),
            "executed": len(entered),
            "blocked": len(blocked),
        },
    }
    
    # Add rejection reasons if any blocks
    if blocked:
        narrative["rejectionReasons"] = count_rejection_reasons(blocked)
        narrative["recentRejected"] = [
            {
                "symbol": rec.get("symbol", ""),
                "reason": rec.get("reason", ""),
                "conviction": rec.get("conviction_score"),
                "rejectedAt": rec.get("timestamp", ""),
            }
            for rec in blocked[:10]
        ]
    
    return narrative


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    logger.info("Generating daily narrative...")
    
    try:
        narrative = generate_narrative()
        
        NARRATIVE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        NARRATIVE_OUTPUT.write_text(json.dumps(narrative, indent=2))
        
        logger.info("✓ Daily narrative written to %s", NARRATIVE_OUTPUT)
        logger.info("  Summary: %s", narrative["summary"])
        logger.info("  Stats: %d screened, %d executed, %d blocked",
                   narrative["stats"]["screened"],
                   narrative["stats"]["executed"],
                   narrative["stats"]["blocked"])
    
    except Exception as e:
        logger.error("Failed to generate narrative: %s", e, exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
