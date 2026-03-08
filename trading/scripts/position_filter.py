#!/usr/bin/env python3
"""
Position filter: load current short symbols for exclusion from screener and executors.

Source of truth: workspace / "current_short_symbols.json"
- Schema: {"symbols": ["AAPL", "MSFT", ...], "updated_at": "2026-03-07T12:00:00"}
- The file is NOT created by this module; it is maintained by an external "sync positions"
  step (cron or manual script). If the file is missing or invalid, we treat it as empty.
- Optional: when an IB connection is passed and connected, merge in live short stock
  positions (secType STK, position < 0) for defense in depth.
"""

from pathlib import Path
from typing import Any, Optional, Set


def _is_valid_current_shorts_file(data: object) -> bool:
    """Type guard: data must be a dict with 'symbols' a list of non-empty strings."""
    if not isinstance(data, dict):
        return False
    symbols = data.get("symbols")
    if not isinstance(symbols, list):
        return False
    return all(isinstance(s, str) and len(s.strip()) > 0 for s in symbols)


def _symbols_from_file(workspace: Path) -> Set[str]:
    """Read symbols from current_short_symbols.json; return empty set if missing/invalid."""
    path = workspace / "current_short_symbols.json"
    if not path.exists():
        return set()
    try:
        import json
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return set()
    if not _is_valid_current_shorts_file(data):
        return set()
    return {s.strip().upper() for s in data["symbols"] if isinstance(s, str) and s.strip()}


def _symbols_from_ib(ib: Any) -> Set[str]:
    """Return set of stock symbols with negative position (short)."""
    out: Set[str] = set()
    if ib is None:
        return out
    try:
        connected = getattr(ib, "isConnected", None)
        if callable(connected) and not connected():
            return out
        positions = ib.positions()
    except Exception:
        return out
    for pos in positions:
        try:
            contract = getattr(pos, "contract", None)
            position = getattr(pos, "position", 0)
            if contract is None:
                continue
            sec_type = getattr(contract, "secType", "")
            symbol = getattr(contract, "symbol", "")
            if sec_type == "STK" and isinstance(position, (int, float)) and position < 0:
                if isinstance(symbol, str) and symbol.strip():
                    out.add(symbol.strip().upper())
        except Exception:
            continue
    return out


def load_current_short_symbols(workspace: Path, ib: Optional[Any] = None) -> Set[str]:
    """
    Load the set of symbols that are currently short (to exclude from new short signals).

    - workspace: trading directory; current_short_symbols.json is read from workspace.
    - ib: optional ib_insync.IB instance; if connected, short stock positions are merged in.
    - Returns: union of symbols from file and from IB (no duplicates). Empty set if both empty.
    """
    symbols = _symbols_from_file(workspace)
    from_ib = _symbols_from_ib(ib)
    return symbols | from_ib

