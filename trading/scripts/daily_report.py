#!/usr/bin/env python3
"""
Generate a daily P&L report by comparing portfolio.json to portfolio_previous.json.

Writes trading/logs/daily_report_YYYY-MM-DD.md. After reporting, copies
portfolio.json to portfolio_previous.json for the next run.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "daily_report.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from paths import TRADING_DIR
PORTFOLIO_JSON = TRADING_DIR / "portfolio.json"
PORTFOLIO_PREVIOUS_JSON = TRADING_DIR / "portfolio_previous.json"
LOGS_DIR = TRADING_DIR / "logs"


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as e:
        logger.warning("Could not load %s: %s", path, e)
        return None


def _positions_set(data: Dict[str, Any]) -> set:
    """Return set of (symbol, secType) for positions."""
    positions = data.get("positions") or []
    if not isinstance(positions, list):
        return set()
    out = set()
    for p in positions:
        if isinstance(p, dict):
            sym = p.get("symbol", "")
            sec = p.get("secType", "")
            if sym or sec:
                out.add((str(sym), str(sec)))
    return out


def run() -> bool:
    """Compare current vs previous snapshot, write report, then copy current to previous."""
    logger.info("=== DAILY P&L REPORT ===")
    current = _load_json(PORTFOLIO_JSON)
    if not current:
        logger.error("No portfolio.json found. Run portfolio_snapshot.py first.")
        return False

    previous = _load_json(PORTFOLIO_PREVIOUS_JSON)
    today = datetime.now().date().isoformat()
    report_path = LOGS_DIR / f"daily_report_{today}.md"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"# Daily P&L Report — {today}",
        "",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "## Current snapshot",
        "",
    ]
    summary_cur = current.get("summary") or {}
    lines.append(f"- **Short notional:** ${summary_cur.get('short_notional', 0):,.2f}")
    lines.append(f"- **Long notional:** ${summary_cur.get('long_notional', 0):,.2f}")
    nl = summary_cur.get("net_liquidation")
    lines.append(f"- **Net liquidation:** ${nl:,.2f}" if nl is not None else "- **Net liquidation:** N/A")
    lines.append("")

    if not previous:
        lines.append("## Previous snapshot")
        lines.append("")
        lines.append("No previous snapshot found. Save today's snapshot as previous for tomorrow's comparison:")
        lines.append("")
        lines.append("```")
        lines.append("cp portfolio.json portfolio_previous.json")
        lines.append("```")
        lines.append("")
    else:
        summary_prev = previous.get("summary") or {}
        nl_prev = summary_prev.get("net_liquidation")
        short_prev = summary_prev.get("short_notional", 0) or 0
        long_prev = summary_prev.get("long_notional", 0) or 0
        short_cur = summary_cur.get("short_notional", 0) or 0
        long_cur = summary_cur.get("long_notional", 0) or 0

        lines.append("## Comparison (vs previous snapshot)")
        lines.append("")
        if nl is not None and nl_prev is not None:
            eq_change = nl - nl_prev
            lines.append(f"- **Equity change:** ${eq_change:+,.2f}")
            lines.append("")
        lines.append("- **Short notional:** ${:,.2f} → ${:,.2f} ({:+,.2f})".format(short_prev, short_cur, (short_cur - short_prev)))
        lines.append("- **Long notional:** ${:,.2f} → ${:,.2f} ({:+,.2f})".format(long_prev, long_cur, (long_cur - long_prev)))
        lines.append("")

        cur_pos = _positions_set(current)
        prev_pos = _positions_set(previous)
        added = cur_pos - prev_pos
        removed = prev_pos - cur_pos
        if added or removed:
            lines.append("## Position changes")
            lines.append("")
            if added:
                lines.append("- **Added:** " + ", ".join(f"{s}" for s, _ in sorted(added)))
                lines.append("")
            if removed:
                lines.append("- **Removed:** " + ", ".join(f"{s}" for s, _ in sorted(removed)))
                lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Run portfolio_snapshot.py before this script to refresh portfolio.json.*")

    report_path.write_text("\n".join(lines))
    logger.info("Wrote %s", report_path)

    # Copy current to previous for next run
    try:
        shutil.copy2(PORTFOLIO_JSON, PORTFOLIO_PREVIOUS_JSON)
        logger.info("Copied portfolio.json → portfolio_previous.json")
    except OSError as e:
        logger.warning("Could not copy to portfolio_previous.json: %s", e)

    # Send concise daily summary to Telegram
    _send_telegram_summary(current, previous)

    return True


def _send_telegram_summary(current: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> None:
    """Send a concise daily P&L summary to Telegram."""
    try:
        from notifications import notify_info, is_event_enabled
    except ImportError:
        logger.warning("notifications module not available; skipping Telegram summary")
        return

    if not is_event_enabled("daily_summary"):
        logger.info("daily_summary event disabled in notification prefs — skipping Telegram summary")
        return

    summary_cur = current.get("summary") or {}
    nl = summary_cur.get("net_liquidation")
    positions = current.get("positions") or []
    open_count = len(positions) if isinstance(positions, list) else 0

    daily_pnl_str = "N/A"
    daily_pnl_pct_str = ""
    if previous:
        summary_prev = previous.get("summary") or {}
        nl_prev = summary_prev.get("net_liquidation")
        if nl is not None and nl_prev is not None and nl_prev > 0:
            change = nl - nl_prev
            pct = (change / nl_prev) * 100
            sign = "+" if change >= 0 else ""
            daily_pnl_str = f"{sign}${change:,.2f}"
            daily_pnl_pct_str = f" ({sign}{pct:.2f}%)"

    # Top winner / loser from position unrealizedPnL
    top_winner = ("—", 0.0)
    top_loser = ("—", 0.0)
    for p in (positions if isinstance(positions, list) else []):
        if not isinstance(p, dict):
            continue
        pnl = float(p.get("unrealizedPNL", p.get("unrealized_pnl", 0)) or 0)
        sym = p.get("symbol", "?")
        if pnl > top_winner[1]:
            top_winner = (sym, pnl)
        if pnl < top_loser[1]:
            top_loser = (sym, pnl)

    # Kill switch
    ks_status = "Inactive"
    ks_file = TRADING_DIR / "kill_switch.json"
    if ks_file.exists():
        try:
            ks = json.loads(ks_file.read_text())
            if ks.get("active"):
                ks_status = f"ACTIVE — {ks.get('reason', '?')}"
        except Exception:
            pass

    # Regime
    regime = "Unknown"
    try:
        for regime_fname in ("regime_state.json", "regime_context.json", "regime.json"):
            regime_file = TRADING_DIR / "logs" / regime_fname
            if regime_file.exists():
                regime = json.loads(regime_file.read_text()).get("regime", "Unknown")
                break
    except Exception:
        pass

    nl_str = f"${nl:,.2f}" if nl is not None else "N/A"
    msg_lines = [
        "<b>Daily P&L Summary</b>",
        f"Date: {datetime.now().date().isoformat()}",
        "",
        f"Daily P&L: {daily_pnl_str}{daily_pnl_pct_str}",
        f"Net Liq: {nl_str}",
        f"Open Positions: {open_count}",
        f"Top Winner: {top_winner[0]} (+${top_winner[1]:,.2f})",
        f"Top Loser: {top_loser[0]} (${top_loser[1]:,.2f})",
        f"Kill Switch: {ks_status}",
        f"Regime: {regime}",
    ]
    msg = "\n".join(msg_lines)

    try:
        notify_info(msg)
        logger.info("Sent daily Telegram summary")
    except Exception as e:
        logger.warning("Failed to send Telegram summary: %s", e)


if __name__ == "__main__":
    import sys
    ok = run()
    sys.exit(0 if ok else 1)
