#!/usr/bin/env python3
"""
Audit Logger - Track all gate rejections and system decisions.

Logs:
- Gate rejections with full context
- Order lifecycle events
- System health checks
- Data quality issues

Writes to audit_trail.json for compliance and analysis.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from paths import TRADING_DIR

AUDIT_LOG = TRADING_DIR / "logs" / "audit_trail.json"

logger = logging.getLogger(__name__)


def log_gate_rejection(
    symbol: str,
    signal_type: str,
    failed_gates: List[str],
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a gate rejection event.
    
    Args:
        symbol: Stock symbol
        signal_type: 'LONG' or 'SHORT'
        failed_gates: List of gate names that failed
        context: Additional context (notional, account_equity, etc.)
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": "gate_rejection",
        "symbol": symbol,
        "signal_type": signal_type,
        "failed_gates": failed_gates,
        "context": context or {},
    }
    
    _append_to_audit_log(entry)
    logger.info(f"Gate rejection logged: {symbol} {signal_type} - {', '.join(failed_gates)}")


def log_order_event(
    symbol: str,
    action: str,
    order_type: str,
    quantity: int,
    status: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log an order lifecycle event.
    
    Args:
        symbol: Stock symbol
        action: 'BUY' or 'SELL'
        order_type: 'MARKET', 'LIMIT', 'STOP', etc.
        quantity: Number of shares
        status: 'SUBMITTED', 'FILLED', 'CANCELLED', 'REJECTED'
        context: Additional context (price, reason, etc.)
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": "order_event",
        "symbol": symbol,
        "action": action,
        "order_type": order_type,
        "quantity": quantity,
        "status": status,
        "context": context or {},
    }
    
    _append_to_audit_log(entry)


def log_system_event(
    event_category: str,
    message: str,
    severity: str = "info",
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a system event.
    
    Args:
        event_category: 'connection', 'data_quality', 'health_check', etc.
        message: Human-readable message
        severity: 'info', 'warning', 'error', 'critical'
        context: Additional context
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": "system_event",
        "category": event_category,
        "message": message,
        "severity": severity,
        "context": context or {},
    }
    
    _append_to_audit_log(entry)


def log_slippage_event(
    symbol: str,
    expected_price: float,
    actual_price: float,
    quantity: int,
    action: str,
) -> None:
    """Log significant slippage event."""
    slippage_pct = abs((actual_price - expected_price) / expected_price) * 100
    slippage_bps = slippage_pct * 100
    
    if slippage_bps > 10:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "slippage",
            "symbol": symbol,
            "action": action,
            "expected_price": expected_price,
            "actual_price": actual_price,
            "quantity": quantity,
            "slippage_bps": slippage_bps,
            "slippage_pct": slippage_pct,
        }
        _append_to_audit_log(entry)


def _append_to_audit_log(entry: Dict[str, Any]) -> None:
    """Append entry to audit log file."""
    try:
        existing = []
        if AUDIT_LOG.exists():
            with open(AUDIT_LOG, "r") as f:
                existing = json.load(f)
        
        existing.append(entry)
        
        max_entries = 10000
        if len(existing) > max_entries:
            existing = existing[-max_entries:]
        
        with open(AUDIT_LOG, "w") as f:
            json.dump(existing, f, indent=2)
    
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def get_recent_rejections(hours: int = 24) -> List[Dict[str, Any]]:
    """Get gate rejections from the last N hours."""
    try:
        if not AUDIT_LOG.exists():
            return []
        
        with open(AUDIT_LOG, "r") as f:
            entries = json.load(f)
        
        cutoff = datetime.now().timestamp() - (hours * 3600)
        recent = []
        
        for entry in entries:
            if entry.get("event_type") != "gate_rejection":
                continue
            
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts.timestamp() >= cutoff:
                    recent.append(entry)
            except:
                continue
        
        return recent
    
    except Exception as e:
        logger.error(f"Error reading audit log: {e}")
        return []


def get_rejection_summary(hours: int = 24) -> Dict[str, Any]:
    """Get summary of gate rejections."""
    rejections = get_recent_rejections(hours)
    
    summary = {
        "total_rejections": len(rejections),
        "by_gate": {},
        "by_symbol": {},
        "by_signal_type": {"LONG": 0, "SHORT": 0},
    }
    
    for rej in rejections:
        signal_type = rej.get("signal_type", "UNKNOWN")
        symbol = rej.get("symbol", "UNKNOWN")
        failed_gates = rej.get("failed_gates", [])
        
        summary["by_signal_type"][signal_type] = summary["by_signal_type"].get(signal_type, 0) + 1
        summary["by_symbol"][symbol] = summary["by_symbol"].get(symbol, 0) + 1
        
        for gate in failed_gates:
            summary["by_gate"][gate] = summary["by_gate"].get(gate, 0) + 1
    
    return summary
