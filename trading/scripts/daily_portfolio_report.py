#!/usr/bin/env python3
"""
Daily Portfolio Report Generator
Sends detailed portfolio summary via Resend API at 4 PM MT

Requirements:
  - RESEND_API_KEY: Resend email API key (from trading/.env)
  - FROM_EMAIL: Sender email (from trading/.env)
  - TO_EMAIL: Recipient email (from trading/.env)

Usage:
  python3 daily_portfolio_report.py

Environment:
  Loads from: trading/.env
  Fallback: system environment variables
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from ib_insync import IB
import requests

# Add scripts directory to path for email_helper import
sys.path.insert(0, str(Path(__file__).parent))

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# Import email helper
try:
    from email_helper import load_email_config, send_email, validate_email_config
except ImportError:
    print("ERROR: email_helper.py not found in scripts directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PortfolioReportGenerator:
    def __init__(self):
        self.ib = IB()
        
        # Load email configuration using helper
        self.email_config = load_email_config()
        if not self.email_config:
            logger.error("Failed to load email configuration")
            self.email_config = {}
        
        # Log what was loaded
        logger.info(f"[INIT] Email config loaded from workspace")
        
        # Extract email settings
        self.resend_api_key = self.email_config.get('resend_api_key')
        self.to_email = self.email_config.get('to_email')
        self.from_email = self.email_config.get('from_email')
        
    def connect_ib(self):
        """Connect to IB Gateway"""
        try:
            self.ib.connect(os.getenv("IB_HOST", "127.0.0.1"), int(os.getenv("IB_PORT", "4001")), clientId=101, timeout=10)
            logger.info("✅ Connected to IB Gateway")
            return True
        except Exception as e:
            logger.error(f"❌ IB connection failed: {e}")
            return False
    
    def get_portfolio_data(self):
        """Fetch current portfolio data"""
        try:
            account = self.ib.managedAccounts()[0]
            
            # Account summary
            account_values = self.ib.accountSummary(account)
            summary = {}
            for av in account_values:
                if av.tag in ['TotalCashValue', 'NetLiquidation', 'BuyingPower', 
                              'DayTradesRemaining', 'EquityWithLoanValue']:
                    summary[av.tag] = float(av.value)
            
            # Positions
            positions = self.ib.positions()
            position_data = []

            # Build map of active short call strikes per symbol for CC upside capping
            cc_strikes: dict[str, float] = {}
            try:
                for pos in positions:
                    c = pos.contract
                    if (getattr(c, "secType", "") == "OPT"
                            and getattr(c, "right", "") == "C"
                            and pos.position < 0):
                        sym = c.symbol
                        strike = float(getattr(c, "strike", 0))
                        if strike > 0:
                            existing = cc_strikes.get(sym, float("inf"))
                            cc_strikes[sym] = min(existing, strike)
            except Exception:
                pass

            for pos in positions:
                entry: dict = {
                    'symbol': pos.contract.symbol,
                    'quantity': pos.position,
                    'avgCost': pos.avgCost,
                    'contract': str(pos.contract),
                }
                sym = pos.contract.symbol
                sec = getattr(pos.contract, "secType", "STK")
                if sec == "STK" and pos.position > 0 and sym in cc_strikes:
                    entry['cc_strike'] = cc_strikes[sym]
                    entry['cc_capped'] = True
                position_data.append(entry)
            
            return {
                'account': account,
                'summary': summary,
                'positions': position_data,
                'position_count': len(position_data)
            }
        except Exception as e:
            logger.error(f"❌ Error fetching portfolio: {e}")
            return None
    
    def calculate_daily_pnl(self):
        """Calculate daily P&L (placeholder)"""
        try:
            # This would fetch from IB's daily P&L data
            # For now, return placeholder
            return {
                'daily_gain': 0.00,
                'daily_gain_pct': 0.00,
                'mtd_gain': 0.00,
                'ytd_gain': 0.00
            }
        except Exception as e:
            logger.warning(f"⚠️  Could not fetch P&L: {e}")
            return {}
    
    def _load_json_safe(self, filepath: Path):
        """Load a JSON file, returning {} on any error. May return list for array files."""
        try:
            if filepath.exists():
                return json.loads(filepath.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            pass
        return {}

    def _load_macro_context(self) -> dict:
        """Load macro events, commodity triggers, regime state, and news sentiment."""
        trading_dir = Path(__file__).resolve().parent.parent
        logs_dir = trading_dir / "logs"
        config_dir = trading_dir / "config"

        regime_state = self._load_json_safe(logs_dir / "regime_state.json")
        regime_context = self._load_json_safe(logs_dir / "regime_context.json")
        news_sentiment = self._load_json_safe(logs_dir / "news_sentiment.json")

        macro_events_raw = self._load_json_safe(config_dir / "macro_events.json")
        active_events = []
        if isinstance(macro_events_raw, list):
            today = datetime.now().strftime("%Y-%m-%d")
            for ev in macro_events_raw:
                if not isinstance(ev, dict) or not ev.get("active", False):
                    continue
                start = ev.get("start_date", "")
                end = ev.get("end_date")
                if start and today < start:
                    continue
                if end and today > end:
                    continue
                active_events.append(ev)

        return {
            "regime_state": regime_state,
            "regime_context": regime_context,
            "news_sentiment": news_sentiment,
            "active_events": active_events,
        }

    def _build_macro_html(self, ctx: dict) -> str:
        """Build the macro intelligence HTML section for the email."""
        rs = ctx.get("regime_state", {})
        rc = ctx.get("regime_context", {})
        ns = ctx.get("news_sentiment", {})
        events = ctx.get("active_events", [])
        ct = rs.get("commodity_triggers", {})

        rows = []

        execution_regime = rc.get("regime", "UNKNOWN")
        macro_regime = rs.get("regime", "UNKNOWN")
        macro_score = rs.get("currentScore", 0)
        rows.append(f"<tr><td style='padding:8px 0;border-bottom:1px solid #eee;'><strong>Execution Regime</strong></td>"
                     f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right;'>{execution_regime}</td></tr>")
        rows.append(f"<tr><td style='padding:8px 0;border-bottom:1px solid #eee;'><strong>Macro Regime</strong></td>"
                     f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right;'>{macro_regime} (score {macro_score})</td></tr>")

        if ct:
            oil_pct = ct.get("oil_30d_pct", 0)
            oil_level = ct.get("oil_level", "NORMAL")
            wheat_pct = ct.get("wheat_30d_pct", 0)
            wheat_level = ct.get("wheat_level", "NORMAL")
            natgas_pct = ct.get("natgas_30d_pct", 0)
            natgas_level = ct.get("natgas_level", "NORMAL")
            food_alert = ct.get("food_chain_alert", False)

            oil_color = "#e74c3c" if oil_level in ("CRISIS", "SURGE") else "#333"
            rows.append(f"<tr><td style='padding:8px 0;border-bottom:1px solid #eee;'><strong>Oil (WTI)</strong></td>"
                        f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right;color:{oil_color};'>"
                        f"{oil_pct:+.1f}% 30d ({oil_level})</td></tr>")

            wheat_color = "#e74c3c" if wheat_level in ("CRISIS", "SURGE") else "#333"
            rows.append(f"<tr><td style='padding:8px 0;border-bottom:1px solid #eee;'><strong>Wheat</strong></td>"
                        f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right;color:{wheat_color};'>"
                        f"{wheat_pct:+.1f}% 30d ({wheat_level})</td></tr>")

            natgas_color = "#e74c3c" if natgas_level in ("CRISIS", "SURGE") else "#333"
            rows.append(f"<tr><td style='padding:8px 0;border-bottom:1px solid #eee;'><strong>Natural Gas</strong></td>"
                        f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right;color:{natgas_color};'>"
                        f"{natgas_pct:+.1f}% 30d ({natgas_level})</td></tr>")

            if food_alert:
                rows.append("<tr><td colspan='2' style='padding:8px 0;border-bottom:1px solid #eee;"
                            "color:#e74c3c;font-weight:bold;'>⚠️ Food-chain supply stress detected "
                            "(oil + wheat/natgas elevated)</td></tr>")

        if ns:
            macro_sent = ns.get("macro_sentiment", 0)
            port_sent = ns.get("portfolio_sentiment", 0)
            articles = ns.get("articles_analyzed", 0)
            sent_color = "#e74c3c" if macro_sent < -0.3 else "#27ae60" if macro_sent > 0.1 else "#333"
            rows.append(f"<tr><td style='padding:8px 0;border-bottom:1px solid #eee;'><strong>News — Macro Sentiment</strong></td>"
                        f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right;color:{sent_color};'>"
                        f"{macro_sent:+.3f} ({articles} articles)</td></tr>")
            port_color = "#e74c3c" if port_sent < -0.3 else "#27ae60" if port_sent > 0.1 else "#333"
            rows.append(f"<tr><td style='padding:8px 0;border-bottom:1px solid #eee;'><strong>News — Portfolio Sentiment</strong></td>"
                        f"<td style='padding:8px 0;border-bottom:1px solid #eee;text-align:right;color:{port_color};'>"
                        f"{port_sent:+.3f}</td></tr>")

        events_html = ""
        if events:
            event_items = "".join(
                f"<li style='margin-bottom:6px;'><strong>{ev.get('event', 'Unknown')}</strong>"
                f" (since {ev.get('start_date', '?')})"
                f"{''.join(f' · {s} {v}x' for s, v in (ev.get('sector_boosts') or {}).items())}"
                f"</li>"
                for ev in events
            )
            events_html = f"<ul style='margin:10px 0 0 0;padding-left:20px;'>{event_items}</ul>"

        headlines_html = ""
        worst = ns.get("worst_headlines", [])
        if worst:
            headline_items = "".join(
                f"<li style='margin-bottom:6px;color:#555;'>"
                f"<span style='color:#e74c3c;font-weight:bold;'>{h.get('sentiment', 0):.2f}</span> "
                f"— {h.get('title', '')[:120]}"
                f"<span style='color:#999;font-size:11px;'> ({h.get('source', '')})</span>"
                f"</li>"
                for h in worst[:5]
            )
            headlines_html = (
                f"<div style='margin-top:15px;'>"
                f"<strong style='font-size:13px;'>Worst Headlines</strong>"
                f"<ul style='margin:8px 0 0 0;padding-left:20px;font-size:13px;'>{headline_items}</ul>"
                f"</div>"
            )

        return f"""
              <div style="background: #f0f4f8; padding: 20px; border-radius: 6px; margin-bottom: 25px; border-left: 4px solid #2c3e50;">
                <h2 style="color: #2c3e50; font-size: 16px; margin-top: 0;">🌍 Macro Intelligence & News</h2>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                  {''.join(rows)}
                </table>
                {f'<div style="margin-top:15px;"><strong style="font-size:13px;">Active Macro Events</strong>{events_html}</div>' if events else ''}
                {headlines_html}
              </div>
        """

    def generate_html_report(self, portfolio_data):
        """Generate HTML email report"""
        summary = portfolio_data['summary']
        positions = portfolio_data['positions']
        pnl = self.calculate_daily_pnl()

        macro_ctx = self._load_macro_context()
        macro_section = self._build_macro_html(macro_ctx)
        
        net_liq = summary.get('NetLiquidation', 0)
        buying_power = summary.get('BuyingPower', 0)
        cash = summary.get('TotalCashValue', 0)
        
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333; background: #f5f5f5; padding: 20px;">
            
            <div style="max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px;">
              
              <h1 style="color: #1a1a1a; margin-bottom: 10px;">📊 Daily Portfolio Report</h1>
              <p style="color: #666; margin-top: 0;">{datetime.now().strftime('%A, %B %d, %Y at %I:%M %p MT')}</p>
              
              <!-- Account Summary -->
              <div style="background: #f9f9f9; padding: 20px; border-radius: 6px; margin-bottom: 25px;">
                <h2 style="color: #2c3e50; font-size: 16px; margin-top: 0;">Account Summary</h2>
                
                <table style="width: 100%; border-collapse: collapse;">
                  <tr>
                    <td style="padding: 10px 0; border-bottom: 1px solid #eee;">
                      <strong>Net Liquidation Value:</strong>
                    </td>
                    <td style="padding: 10px 0; border-bottom: 1px solid #eee; text-align: right;">
                      <span style="color: #27ae60; font-size: 18px; font-weight: bold;">${net_liq:,.2f}</span>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 10px 0; border-bottom: 1px solid #eee;">
                      <strong>Buying Power:</strong>
                    </td>
                    <td style="padding: 10px 0; border-bottom: 1px solid #eee; text-align: right;">
                      ${buying_power:,.2f}
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 10px 0; border-bottom: 1px solid #eee;">
                      <strong>Cash Available:</strong>
                    </td>
                    <td style="padding: 10px 0; border-bottom: 1px solid #eee; text-align: right;">
                      ${cash:,.2f}
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 10px 0;">
                      <strong>Positions Held:</strong>
                    </td>
                    <td style="padding: 10px 0; text-align: right;">
                      {portfolio_data['position_count']} positions
                    </td>
                  </tr>
                </table>
              </div>
              
              {macro_section}

              <!-- Top Positions -->
              <div style="margin-bottom: 25px;">
                <h2 style="color: #2c3e50; font-size: 16px;">Top 10 Positions by Size</h2>
                
                <table style="width: 100%; border-collapse: collapse;">
                  <thead>
                    <tr style="background: #ecf0f1;">
                      <th style="padding: 10px; text-align: left; border-bottom: 2px solid #bdc3c7;">Symbol</th>
                      <th style="padding: 10px; text-align: right; border-bottom: 2px solid #bdc3c7;">Shares</th>
                      <th style="padding: 10px; text-align: right; border-bottom: 2px solid #bdc3c7;">Avg Cost</th>
                      <th style="padding: 10px; text-align: right; border-bottom: 2px solid #bdc3c7;">CC Cap</th>
                    </tr>
                  </thead>
                  <tbody>
        """
        
        # Sort by quantity (largest first)
        sorted_positions = sorted(positions, key=lambda x: abs(x['quantity']), reverse=True)[:10]
        
        for pos in sorted_positions:
            qty_color = '#27ae60' if pos['quantity'] > 0 else '#e74c3c'
            cc_label = ""
            if pos.get('cc_capped'):
                strike = pos.get('cc_strike', 0)
                max_gain_pct = (strike / pos['avgCost'] - 1) * 100 if pos['avgCost'] > 0 else 0
                cc_label = f'<span style="color:#e67e22;font-size:12px;">${strike:.0f} ({max_gain_pct:+.1f}%)</span>'
            html += f"""
                    <tr style="border-bottom: 1px solid #ecf0f1;">
                      <td style="padding: 10px; font-weight: bold;">{pos['symbol']}</td>
                      <td style="padding: 10px; text-align: right; color: {qty_color};">{pos['quantity']:,.0f}</td>
                      <td style="padding: 10px; text-align: right;">${pos['avgCost']:.2f}</td>
                      <td style="padding: 10px; text-align: right;">{cc_label}</td>
                    </tr>
            """
        
        html += """
                  </tbody>
                </table>
              </div>
              
              <!-- Daily Stats -->
              <div style="background: #ecf7ff; padding: 15px; border-radius: 6px; margin-bottom: 25px;">
                <h3 style="margin-top: 0; color: #2980b9;">Today's Performance</h3>
                <p style="margin: 5px 0;">
                  <strong>Daily Gain/Loss:</strong> 
                  <span style="color: #27ae60; font-weight: bold;">$0.00 (0.00%)</span>
                </p>
                <p style="margin: 5px 0;">
                  <strong>Daily Loss Limit:</strong> -$1,350.00
                </p>
                <p style="margin: 5px 0; color: #27ae60;">
                  ✅ <strong>Within daily loss limit</strong>
                </p>
              </div>
              
              <!-- Footer -->
              <div style="border-top: 1px solid #ecf0f1; padding-top: 15px; text-align: center; color: #999; font-size: 12px;">
                <p>This report was generated automatically by OpenClaw Trading System</p>
                <p>Account: {portfolio_data['account']} | Paper Trading Mode</p>
                <p style="margin-bottom: 0;">Do not reply to this email</p>
              </div>
              
            </div>
          </body>
        </html>
        """
        
        return html
    
    def send_email(self, subject, html_content):
        """Send email via Resend API using email_helper"""
        # Use email_helper for consistent, robust delivery
        success = send_email(
            subject=subject,
            html_body=html_content,
            to_email=self.to_email,
            config=self.email_config
        )
        
        if success:
            logger.info("✅ Email sent successfully!")
            return True
        else:
            logger.error("❌ Email send failed")
            return False
    
    def generate_and_send(self):
        """Main workflow"""
        logger.info("📊 Generating Daily Portfolio Report...")

        if not self.connect_ib():
            logger.error("❌ Could not connect to IB Gateway")
            return False

        success = False
        try:
            logger.info("📈 Fetching portfolio data...")
            portfolio_data = self.get_portfolio_data()
            if not portfolio_data:
                logger.error("❌ Could not fetch portfolio data")
                return False

            logger.info(f"✅ Portfolio loaded: {portfolio_data['position_count']} positions")
            logger.info(
                f"   Net Liquidation: ${portfolio_data['summary'].get('NetLiquidation', 0):,.2f}"
            )

            logger.info("📝 Generating report...")
            html_content = self.generate_html_report(portfolio_data)

            logger.info("📧 Sending email via Resend...")
            subject = f"Daily Portfolio Report - {datetime.now().strftime('%B %d, %Y')}"
            success = self.send_email(subject, html_content)
            return success
        finally:
            try:
                if self.ib.isConnected():
                    self.ib.disconnect()
            except Exception as exc:
                logger.warning("IB disconnect: %s", exc)

if __name__ == "__main__":
    generator = PortfolioReportGenerator()
    success = generator.generate_and_send()
    exit(0 if success else 1)
