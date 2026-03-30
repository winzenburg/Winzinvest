#!/usr/bin/env python3
"""
Generate Weekly Insight Email — Pull-Based Transparency

Sends a weekly digest showing:
- What the system did this week
- Key decisions and their outcomes
- Performance context vs. previous weeks
- Upcoming signals to watch (if any)

NOT a push notification to trade. A transparency report for curious monitoring.

Scheduled: Every Friday at 5 PM MT (after market close)
"""

import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"
TRADE_DB = TRADING_DIR / "logs" / "trades.db"
REGIME_CONTEXT = TRADING_DIR / "logs" / "regime_context.json"
OUTPUT_HTML = TRADING_DIR / "logs" / "weekly_insight_latest.html"


def load_week_executions() -> List[Dict[str, Any]]:
    """Load this week's execution records (Mon-Fri)."""
    if not EXECUTION_LOG.exists():
        return []
    
    # Find Monday of this week
    today = datetime.now()
    days_since_monday = today.weekday()  # 0=Mon, 6=Sun
    monday = (today - timedelta(days=days_since_monday)).date()
    monday_iso = monday.isoformat()
    
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
                
                ts = obj.get("timestamp") or obj.get("timestamp_iso") or ""
                if ts >= monday_iso:
                    records.append(obj)
            
            except (json.JSONDecodeError, ValueError):
                continue
    
    except Exception as e:
        logger.warning("Could not load execution log: %s", e)
    
    return records


def analyze_week(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze this week's activity."""
    entered = [r for r in records if r.get("status", "").upper() in ("FILLED", "FILL")]
    exited = [r for r in records if "exit" in r.get("status", "").lower()]
    blocked = [r for r in records if r.get("status", "").upper() in ("REJECTED", "BLOCKED", "SKIPPED")]
    
    # Calculate P&L from exits
    total_pnl = sum(r.get("realized_pnl", 0) for r in exited if r.get("realized_pnl"))
    wins = [r for r in exited if r.get("realized_pnl", 0) > 0]
    losses = [r for r in exited if r.get("realized_pnl", 0) < 0]
    
    win_rate = (len(wins) / len(exited) * 100) if exited else 0
    
    # Best and worst
    best_trade = max((r.get("realized_pnl", 0) for r in exited), default=0)
    worst_trade = min((r.get("realized_pnl", 0) for r in exited), default=0)
    
    # Rejection reasons
    reason_counts: Dict[str, int] = {}
    for rec in blocked:
        reason = rec.get("reason", "Unknown")[:50]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    
    top_rejection = max(reason_counts.items(), key=lambda x: x[1]) if reason_counts else ("N/A", 0)
    
    return {
        "entries": len(entered),
        "exits": len(exited),
        "blocked": len(blocked),
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "wins": len(wins),
        "losses": len(losses),
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "top_rejection_reason": top_rejection[0],
        "top_rejection_count": top_rejection[1],
        "regime_changes": 0,  # TODO: track regime transitions if log exists
    }


def get_current_regime() -> str:
    """Load current market regime."""
    if not REGIME_CONTEXT.exists():
        return "MIXED"
    
    try:
        data = json.loads(REGIME_CONTEXT.read_text())
        return data.get("regime", "MIXED")
    except Exception:
        return "MIXED"


def build_html_email(analysis: Dict[str, Any], regime: str) -> str:
    """Generate HTML email content."""
    
    # Header
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.6;
      color: #334155;
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
      background-color: #f8fafc;
    }}
    .container {{
      background: white;
      border-radius: 12px;
      padding: 32px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    h1 {{
      font-family: Georgia, serif;
      font-size: 28px;
      font-weight: 700;
      color: #0f172a;
      margin: 0 0 8px 0;
    }}
    .subtitle {{
      font-size: 14px;
      color: #64748b;
      margin-bottom: 24px;
    }}
    .section {{
      margin-bottom: 28px;
    }}
    .section-title {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #64748b;
      margin-bottom: 12px;
    }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 20px;
    }}
    .stat-card {{
      background: #f1f5f9;
      padding: 16px;
      border-radius: 8px;
      text-align: center;
    }}
    .stat-value {{
      font-size: 24px;
      font-weight: 700;
      color: #0f172a;
    }}
    .stat-label {{
      font-size: 11px;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-top: 4px;
    }}
    .pnl-positive {{ color: #059669; }}
    .pnl-negative {{ color: #dc2626; }}
    .regime-badge {{
      display: inline-block;
      padding: 4px 12px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .regime-uptrend {{ background: #d1fae5; color: #065f46; }}
    .regime-choppy {{ background: #dbeafe; color: #1e40af; }}
    .regime-mixed {{ background: #fef3c7; color: #92400e; }}
    .regime-downtrend {{ background: #fee2e2; color: #991b1b; }}
    .footer {{
      margin-top: 32px;
      padding-top: 20px;
      border-top: 1px solid #e2e8f0;
      font-size: 12px;
      color: #94a3b8;
      text-align: center;
    }}
    .cta {{
      display: inline-block;
      margin-top: 20px;
      padding: 12px 24px;
      background: #0f172a;
      color: white;
      text-decoration: none;
      border-radius: 8px;
      font-weight: 600;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Your Week in Review</h1>
    <p class="subtitle">
      {datetime.now().strftime("%B %d, %Y")} — What your system did this week
    </p>
    
    <div class="section">
      <div class="section-title">This Week's Activity</div>
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-value">{analysis["entries"]}</div>
          <div class="stat-label">New Entries</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{analysis["exits"]}</div>
          <div class="stat-label">Closed Trades</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{analysis["blocked"]}</div>
          <div class="stat-label">Blocked Signals</div>
        </div>
      </div>
    </div>
    
    <div class="section">
      <div class="section-title">Performance</div>
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-value {'pnl-positive' if analysis['total_pnl'] >= 0 else 'pnl-negative'}">
            {'$' + f"{analysis['total_pnl']:,.0f}" if analysis['total_pnl'] >= 0 else '-$' + f"{abs(analysis['total_pnl']):,.0f}"}
          </div>
          <div class="stat-label">Total P&L</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{analysis["win_rate"]:.1f}%</div>
          <div class="stat-label">Win Rate</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{analysis["wins"]}/{analysis["losses"]}</div>
          <div class="stat-label">W / L</div>
        </div>
      </div>
    </div>
    
    <div class="section">
      <div class="section-title">Risk Management</div>
      <p style="color: #475569; font-size: 14px; line-height: 1.7;">
        The system blocked <strong>{analysis["blocked"]}</strong> signal{"s" if analysis["blocked"] != 1 else ""} this week.
        {'Top reason: <strong>' + analysis["top_rejection_reason"] + '</strong> (' + str(analysis["top_rejection_count"]) + ' times).' if analysis["top_rejection_count"] > 0 else 'All screened signals passed risk gates.'}
      </p>
    </div>
    
    <div class="section">
      <div class="section-title">Market Context</div>
      <p style="color: #475569; font-size: 14px; line-height: 1.7;">
        Current execution regime: 
        <span class="regime-badge {'regime-uptrend' if 'UPTREND' in regime else 'regime-choppy' if 'CHOPPY' in regime else 'regime-mixed' if 'MIXED' in regime else 'regime-downtrend'}">
          {regime.replace("_", " ")}
        </span>
      </p>
      <p style="color: #64748b; font-size: 13px; margin-top: 8px;">
        The system adapts position sizing and entry criteria based on regime. 
        {'Aggressive allocation in strong trends.' if 'STRONG' in regime and 'UPTREND' in regime else 'Reduced allocation in unfavorable conditions.' if 'UNFAVORABLE' in regime or 'DOWNTREND' in regime else 'Standard allocation in neutral/choppy conditions.'}
      </p>
    </div>
    
    <div style="text-align: center;">
      <a href="https://winzinvest.com/institutional" class="cta">
        View Full Dashboard
      </a>
    </div>
    
    <div class="footer">
      <p>
        This is a weekly transparency report from Winzinvest.<br>
        You're receiving this because you're a Mission Control subscriber.
      </p>
      <p style="margin-top: 12px;">
        <a href="https://winzinvest.com/settings/email-preferences" style="color: #64748b; text-decoration: underline;">
          Email Preferences
        </a>
      </p>
    </div>
  </div>
</body>
</html>
"""
    
    return html


def send_email(to_email: str, html_content: str) -> bool:
    """Send email via SMTP (configure SMTP settings in .env)."""
    import os
    
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_email = os.getenv("SMTP_FROM", smtp_user)
    
    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning("SMTP not configured — skipping email send")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Your Week in Review — {datetime.now().strftime('%B %d, %Y')}"
        msg['From'] = from_email
        msg['To'] = to_email
        
        # Plain text fallback
        text_part = MIMEText("View this email in HTML for the full report.", 'plain')
        html_part = MIMEText(html_content, 'html')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        logger.info("✓ Weekly insight sent to %s", to_email)
        return True
    
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def get_subscriber_emails() -> List[str]:
    """Get list of active subscribers who haven't opted out of weekly insights."""
    # TODO: Query from database when available
    # For now, read from config file
    
    config_path = TRADING_DIR / "config" / "email_subscribers.json"
    if not config_path.exists():
        logger.info("No email_subscribers.json found — returning empty list")
        return []
    
    try:
        data = json.loads(config_path.read_text())
        subscribers = data.get("weekly_insights", [])
        return [s for s in subscribers if isinstance(s, str) and '@' in s]
    except Exception as e:
        logger.warning("Could not load subscribers: %s", e)
        return []


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    logger.info("Generating weekly insight email...")
    
    try:
        records = load_week_executions()
        analysis = analyze_week(records)
        regime = get_current_regime()
        
        html = build_html_email(analysis, regime)
        
        # Save to file for preview/debugging
        OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_HTML.write_text(html)
        logger.info("✓ Email HTML saved to %s", OUTPUT_HTML)
        
        # Send to subscribers
        subscribers = get_subscriber_emails()
        if not subscribers:
            logger.info("No subscribers configured — skipping send")
            return 0
        
        sent_count = 0
        for email in subscribers:
            if send_email(email, html):
                sent_count += 1
        
        logger.info("✓ Sent weekly insight to %d/%d subscribers", sent_count, len(subscribers))
    
    except Exception as e:
        logger.error("Failed to generate weekly insight: %s", e, exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
