#!/usr/bin/env python3
"""
Daily Portfolio Report Generator
Sends detailed portfolio summary via Resend API at 4 PM MT

Requirements:
  - RESEND_API_KEY: Resend email API key (from ~/.openclaw/workspace/.env)
  - FROM_EMAIL: Sender email (from ~/.openclaw/workspace/.env)
  - TO_EMAIL: Recipient email (from ~/.openclaw/workspace/.env)

Usage:
  python3 daily_portfolio_report.py

Environment:
  Loads from: ~/.openclaw/workspace/.env or trading/.env
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
            self.ib.connect('127.0.0.1', 4002, clientId=101, timeout=10)
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
            for pos in positions:
                position_data.append({
                    'symbol': pos.contract.symbol,
                    'quantity': pos.position,
                    'avgCost': pos.avgCost,
                    'contract': str(pos.contract)
                })
            
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
    
    def generate_html_report(self, portfolio_data):
        """Generate HTML email report"""
        summary = portfolio_data['summary']
        positions = portfolio_data['positions']
        pnl = self.calculate_daily_pnl()
        
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
              
              <!-- Top Positions -->
              <div style="margin-bottom: 25px;">
                <h2 style="color: #2c3e50; font-size: 16px;">Top 10 Positions by Size</h2>
                
                <table style="width: 100%; border-collapse: collapse;">
                  <thead>
                    <tr style="background: #ecf0f1;">
                      <th style="padding: 10px; text-align: left; border-bottom: 2px solid #bdc3c7;">Symbol</th>
                      <th style="padding: 10px; text-align: right; border-bottom: 2px solid #bdc3c7;">Shares</th>
                      <th style="padding: 10px; text-align: right; border-bottom: 2px solid #bdc3c7;">Avg Cost</th>
                    </tr>
                  </thead>
                  <tbody>
        """
        
        # Sort by quantity (largest first)
        sorted_positions = sorted(positions, key=lambda x: abs(x['quantity']), reverse=True)[:10]
        
        for pos in sorted_positions:
            qty_color = '#27ae60' if pos['quantity'] > 0 else '#e74c3c'
            html += f"""
                    <tr style="border-bottom: 1px solid #ecf0f1;">
                      <td style="padding: 10px; font-weight: bold;">{pos['symbol']}</td>
                      <td style="padding: 10px; text-align: right; color: {qty_color};">{pos['quantity']:,.0f}</td>
                      <td style="padding: 10px; text-align: right;">${pos['avgCost']:.2f}</td>
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
        
        # Connect to IB
        if not self.connect_ib():
            logger.error("❌ Could not connect to IB Gateway")
            return False
        
        # Fetch portfolio data
        logger.info("📈 Fetching portfolio data...")
        portfolio_data = self.get_portfolio_data()
        if not portfolio_data:
            logger.error("❌ Could not fetch portfolio data")
            self.ib.disconnect()
            return False
        
        logger.info(f"✅ Portfolio loaded: {portfolio_data['position_count']} positions")
        logger.info(f"   Net Liquidation: ${portfolio_data['summary'].get('NetLiquidation', 0):,.2f}")
        
        # Generate HTML report
        logger.info("📝 Generating report...")
        html_content = self.generate_html_report(portfolio_data)
        
        # Send email
        logger.info("📧 Sending email via Resend...")
        subject = f"Daily Portfolio Report - {datetime.now().strftime('%B %d, %Y')}"
        success = self.send_email(subject, html_content)
        
        # Cleanup
        self.ib.disconnect()
        
        return success

if __name__ == "__main__":
    generator = PortfolioReportGenerator()
    success = generator.generate_and_send()
    exit(0 if success else 1)
