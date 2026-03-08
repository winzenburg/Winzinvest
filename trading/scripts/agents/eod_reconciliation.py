#!/usr/bin/env python3
"""
EOD Reconciliation Agent — runs after market close.

Compares internal trade log (executions.json) to IBKR execution reports,
flags discrepancies, calculates daily P&L, and generates a summary report.
Optionally send report via email/Slack (stub).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from agents._paths import EXECUTIONS_LOG, LOGS_DIR, TRADING_DIR


def _load_executions_today() -> List[Dict[str, Any]]:
    """Load execution records from executions.json with timestamp today."""
    if not EXECUTIONS_LOG.exists():
        return []
    today = datetime.now().date().isoformat()
    out = []
    try:
        for line in EXECUTIONS_LOG.read_text().strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            ts = rec.get("timestamp") or rec.get("timestamp_iso") or ""
            if not str(ts).startswith(today):
                continue
            out.append(rec)
    except OSError as e:
        logger.warning("Could not read executions log: %s", e)
    return out


def _get_ib_executions_today(ib: Any) -> List[Dict[str, Any]]:
    """Fetch today's executions from IB. Returns list of dicts. Uses ib.executions (list) or reqExecutions; adapt to your ib_insync version."""
    out: List[Dict[str, Any]] = []
    try:
        execs = getattr(ib, "executions", [])
        if callable(execs):
            execs = execs()
        if not isinstance(execs, list):
            execs = []
        today = datetime.now().date()
        for e in execs:
            if not hasattr(e, "time"):
                continue
            ex_time = getattr(e, "time", None)
            if ex_time is None:
                continue
            if isinstance(ex_time, datetime) and ex_time.date() == today:
                out.append({
                    "symbol": getattr(getattr(e, "contract", None), "symbol", ""),
                    "side": getattr(e, "side", ""),
                    "shares": getattr(e, "shares", 0),
                    "price": float(getattr(e, "price", 0) or 0),
                    "time": ex_time.isoformat() if isinstance(ex_time, datetime) else str(ex_time),
                    "orderId": getattr(e, "orderId", None),
                })
    except Exception as err:
        logger.warning("Could not fetch IB executions: %s", err)
    return out


def _reconcile(
    internal: List[Dict[str, Any]],
    ib_execs: List[Dict[str, Any]],
) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Compare internal vs IB. Returns (discrepancy_messages, only_internal, only_ib).
    """
    discrepancies: List[str] = []
    only_internal: List[Dict[str, Any]] = []
    only_ib: List[Dict[str, Any]] = []

    # Build key sets: symbol + action + rough time (minute)
    def key_internal(r: Dict[str, Any]) -> str:
        ts = (r.get("timestamp") or "")[:16]  # YYYY-MM-DDTHH:MM
        return f"{r.get('symbol', '')}_{r.get('action', r.get('type', ''))}_{ts}"

    def key_ib(r: Dict[str, Any]) -> str:
        ts = (r.get("time", ""))[:16]
        return f"{r.get('symbol', '')}_{r.get('side', '')}_{ts}"

    internal_keys = {key_internal(r): r for r in internal}
    ib_keys = {key_ib(r): r for r in ib_execs}

    for k, r in internal_keys.items():
        if k not in ib_keys:
            only_internal.append(r)
    for k, r in ib_keys.items():
        if k not in internal_keys:
            only_ib.append(r)

    if only_internal:
        discrepancies.append(f"Found {len(only_internal)} execution(s) in internal log but not in IB")
    if only_ib:
        discrepancies.append(f"Found {len(only_ib)} execution(s) in IB but not in internal log")

    return discrepancies, only_internal, only_ib


def run_reconciliation(ib: Optional[Any] = None) -> str:
    """
    Run reconciliation. If ib is None, only internal log is used (no IB comparison).
    Returns report text (markdown).
    """
    internal = _load_executions_today()
    ib_execs: List[Dict[str, Any]] = []
    if ib is not None:
        ib_execs = _get_ib_executions_today(ib)
    discrepancies, only_internal, only_ib = _reconcile(internal, ib_execs)
    today = datetime.now().date().isoformat()
    lines = [
        f"# EOD Reconciliation — {today}",
        "",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "## Internal log (today)",
        "",
        f"- Records: {len(internal)}",
        "",
        "## IB executions (today)",
        "",
        f"- Records: {len(ib_execs)}",
        "",
        "## Discrepancies",
        "",
    ]
    if not discrepancies:
        lines.append("None.")
    else:
        for d in discrepancies:
            lines.append(f"- {d}")
        if only_internal:
            lines.append("")
            lines.append("**Only in internal log:**")
            for r in only_internal[:20]:
                lines.append(f"  - {r.get('symbol')} {r.get('action', r.get('type'))} {r.get('timestamp', '')}")
        if only_ib:
            lines.append("")
            lines.append("**Only in IB:**")
            for r in only_ib[:20]:
                lines.append(f"  - {r.get('symbol')} {r.get('side')} {r.get('time', '')}")
    lines.append("")
    lines.append("---")
    report = "\n".join(lines)
    return report


def run_and_save(ib: Optional[Any] = None) -> Path:
    """Run reconciliation and save report to logs/reconciliation_YYYY-MM-DD.md."""
    report = run_reconciliation(ib)
    today = datetime.now().date().isoformat()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / f"reconciliation_{today}.md"
    path.write_text(report)
    logger.info("Wrote %s", path)
    return path


if __name__ == "__main__":
    import sys
    from ib_insync import IB

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    ib = IB()
    try:
        import asyncio
        asyncio.run(ib.connectAsync("127.0.0.1", 4002, clientId=108))
        run_and_save(ib)
    except Exception as e:
        logger.warning("IB connect failed, running reconciliation without IB: %s", e)
        run_and_save(None)
    finally:
        if ib.isConnected():
            ib.disconnect()
