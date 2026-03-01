#!/usr/bin/env python3
"""
Audit Trail Dashboard
Interactive dashboard for monitoring audit trail, health checks, and trading activity
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import audit modules
try:
    from audit_query import get_audit_query, AuditQuery
    from audit_summary import AuditSummary
    from audit_config import AUDIT_LOG_FILE, HEALTH_LOG_FILE
except ImportError as e:
    logger.error(f"❌ Failed to import audit modules: {e}")
    sys.exit(1)


class AuditDashboard:
    """Interactive audit trail dashboard"""
    
    def __init__(self):
        """Initialize dashboard"""
        self.query = get_audit_query()
        self.summary = AuditSummary()
    
    def print_header(self, title: str):
        """Print a formatted header"""
        width = 70
        print("\n" + "="*width)
        print(f"  {title}")
        print("="*width)
    
    def print_summary_line(self, label: str, value: Any, color_code: str = ""):
        """Print a formatted summary line"""
        print(f"  {label:<40} {str(value):>20}")
    
    def display_dashboard(self):
        """Display the main dashboard"""
        self.print_header("📊 AUDIT TRAIL DASHBOARD")
        
        # Get summaries
        daily = self.summary.daily_summary()
        health = self.summary.health_score(24)
        recent = self.query.get_recent_trades(5)
        
        # System Health
        print("\n🏥 SYSTEM HEALTH (Last 24h):")
        print(f"  Health Score: {health.get('health_score', 0)}/100")
        print(f"  Message: {health.get('message', 'N/A')}")
        print(f"  Healthy Checks: {health.get('healthy', 0)}")
        print(f"  Failed Checks: {health.get('unhealthy', 0)}")
        print(f"  Failures: {health.get('failures', 0)}")
        
        # Daily Activity
        print("\n📈 TODAY'S ACTIVITY:")
        print(f"  Total Events: {daily.get('total_events', 0)}")
        print(f"  Unique Symbols: {daily.get('unique_symbols', 0)}")
        print(f"  Entry Signals: {daily.get('entry_signals', 0)}")
        print(f"  Stops Placed: {daily.get('stops_placed', 0)}")
        print(f"  Stops Filled: {daily.get('stops_filled', 0)}")
        print(f"  Positions Closed: {daily.get('positions_closed', 0)}")
        
        # P&L
        pnl = daily.get('pnl', {})
        print("\n💰 P&L:")
        print(f"  Total P&L: ${pnl.get('total_pnl', 0):.2f}")
        print(f"  Winning Trades: {pnl.get('winning_trades', 0)}")
        print(f"  Losing Trades: {pnl.get('losing_trades', 0)}")
        
        # Risk Events
        print("\n⚠️  RISK EVENTS:")
        print(f"  Errors: {daily.get('errors', 0)}")
        print(f"  Risk Gates Triggered: {daily.get('risk_gates_triggered', 0)}")
        
        # Recent Symbols
        print("\n📍 RECENT SYMBOLS:")
        for symbol, count in recent:
            print(f"  {symbol:<10} {count:>5} events")
        
        # File Info
        audit_size = self._get_file_size(AUDIT_LOG_FILE)
        health_size = self._get_file_size(HEALTH_LOG_FILE)
        print(f"\n📁 LOG FILES:")
        print(f"  Audit Log: {audit_size}")
        print(f"  Health Log: {health_size}")
        
        print("\n" + "="*70 + "\n")
    
    def display_recent_events(self, limit: int = 20, event_type: Optional[str] = None):
        """Display recent events"""
        if event_type:
            events = self.query.query_by_event_type(event_type)
            title = f"RECENT {event_type} EVENTS"
        else:
            events = self.query.events
            title = "RECENT EVENTS"
        
        self.print_header(f"📋 {title} (Last {limit})")
        
        # Sort by timestamp and get last N
        recent = sorted(events, key=lambda e: e.get('timestamp', ''))[-limit:]
        
        for event in recent:
            ts = event.get('timestamp', 'N/A')
            event_type = event.get('event_type', 'UNKNOWN')
            data = event.get('data', {})
            
            # Format based on event type
            if event_type == 'ENTRY_SIGNAL':
                symbol = data.get('symbol', '?')
                price = data.get('entry_price', 0)
                qty = data.get('quantity', 0)
                reason = data.get('reason', '')[:30]
                print(f"  {ts} | ENTRY: {symbol} @ ${price} x{qty} ({reason})")
            
            elif event_type == 'STOP_FILLED':
                symbol = data.get('symbol', '?')
                fill = data.get('fill_price', 0)
                pnl = data.get('pnl', 0)
                print(f"  {ts} | STOP: {symbol} filled @ ${fill} (P&L: ${pnl:.2f})")
            
            elif event_type == 'POSITION_CLOSED':
                symbol = data.get('symbol', '?')
                price = data.get('exit_price', 0)
                reason = data.get('reason', '')
                print(f"  {ts} | CLOSE: {symbol} @ ${price} ({reason})")
            
            elif event_type == 'ERROR_EVENT':
                error = data.get('message', 'Unknown error')[:40]
                print(f"  {ts} | ERROR: {error}")
            
            else:
                print(f"  {ts} | {event_type}: {str(data)[:50]}")
        
        print("\n")
    
    def display_failures(self, hours: int = 24):
        """Display recent failures"""
        failures = self.summary.failure_summary(hours)
        
        self.print_header(f"❌ FAILURES & ERRORS (Last {hours}h)")
        
        print(f"\nTotal Failures: {failures.get('total_failures', 0)}")
        
        if failures.get('total_failures', 0) > 0:
            print("\nBy Type:")
            for event_type, count in failures.get('by_type', {}).items():
                print(f"  {event_type}: {count}")
            
            print("\nBy Component:")
            for component, count in failures.get('by_component', {}).items():
                print(f"  {component}: {count}")
            
            print("\nRecent Failures:")
            for event in failures.get('recent_failures', [])[-5:]:
                ts = event.get('timestamp', 'N/A')
                data = event.get('data', {})
                msg = data.get('message', data.get('error', 'Unknown'))[:40]
                print(f"  {ts} | {msg}")
        
        print("\n")
    
    def display_health_status(self):
        """Display health monitoring status"""
        health_summary = self.query.get_system_health_summary()
        
        self.print_header("🏥 HEALTH MONITORING STATUS")
        
        print(f"\nTotal Health Checks: {health_summary.get('total_checks', 0)}")
        
        if health_summary.get('by_component'):
            print("\nComponent Status:")
            for component, stats in health_summary.get('by_component', {}).items():
                ok = stats.get('ok', 0)
                error = stats.get('error', 0)
                warning = stats.get('warning', 0)
                total = ok + error + warning
                pct = int((ok / total * 100) if total > 0 else 0)
                
                status_str = "✅" if error == 0 else "⚠️" if warning > 0 else "❌"
                print(f"  {status_str} {component:<20} OK:{ok:>3} ERROR:{error:>3} WARNING:{warning:>3} ({pct}%)")
        
        if health_summary.get('latest_status'):
            print("\nLatest Check Results:")
            for component, status in health_summary.get('latest_status', {}).items():
                ts = status.get('timestamp', 'N/A')[-5:]  # Last 5 chars
                stat = status.get('status', 'UNKNOWN')
                latency = status.get('latency_ms', 'N/A')
                print(f"  {component:<20} {stat:<10} ({latency}ms) at {ts}")
        
        print("\n")
    
    def display_trade_report(self, symbol: str):
        """Display detailed trade report for a symbol"""
        report = self.query.export_trade_report(symbol)
        summary = report.get('summary', {})
        
        self.print_header(f"📊 TRADE REPORT: {symbol}")
        
        print(f"\nTotal Events: {summary.get('total_events', 0)}")
        print("\nEvent Breakdown:")
        for event_type, count in summary.get('events_by_type', {}).items():
            print(f"  {event_type:<25} {count:>5}")
        
        print(f"\nTrade Summary:")
        print(f"  Entry Signals: {summary.get('entry_signals', 0)}")
        print(f"  Stops Placed: {summary.get('stops_placed', 0)}")
        print(f"  Stops Filled: {summary.get('stops_filled', 0)}")
        print(f"  Positions Closed: {summary.get('positions_closed', 0)}")
        print(f"  Errors: {summary.get('errors', 0)}")
        
        print("\nDetailed Events:")
        for event in report.get('all_events', [])[-10:]:
            ts = event.get('timestamp', 'N/A')
            event_type = event.get('event_type', 'UNKNOWN')
            print(f"  {ts} | {event_type}")
        
        print("\n")
    
    def _get_file_size(self, filepath: str) -> str:
        """Get file size in human-readable format"""
        try:
            size = os.path.getsize(filepath)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except:
            return "N/A"
    
    def interactive_menu(self):
        """Interactive menu system"""
        while True:
            print("\n" + "="*70)
            print("  AUDIT DASHBOARD MENU")
            print("="*70)
            print("\n  1. Display Main Dashboard")
            print("  2. Show Recent Events")
            print("  3. Show Entry Signals")
            print("  4. Show Stops Filled")
            print("  5. Show Position Closes")
            print("  6. Show Failures & Errors")
            print("  7. Show Health Status")
            print("  8. Show Trade Report (by symbol)")
            print("  9. Daily Summary")
            print("  10. Weekly Summary")
            print("  0. Exit")
            print("\n" + "="*70)
            
            choice = input("\nSelect option (0-10): ").strip()
            
            if choice == '1':
                self.display_dashboard()
            elif choice == '2':
                self.display_recent_events(limit=20)
            elif choice == '3':
                self.display_recent_events(limit=20, event_type='ENTRY_SIGNAL')
            elif choice == '4':
                self.display_recent_events(limit=20, event_type='STOP_FILLED')
            elif choice == '5':
                self.display_recent_events(limit=20, event_type='POSITION_CLOSED')
            elif choice == '6':
                self.display_failures()
            elif choice == '7':
                self.display_health_status()
            elif choice == '8':
                symbol = input("\nEnter symbol: ").strip().upper()
                if symbol:
                    self.display_trade_report(symbol)
            elif choice == '9':
                date = input("\nEnter date (YYYY-MM-DD) or press Enter for today: ").strip()
                daily = self.summary.daily_summary(date if date else None)
                self.print_header("📊 DAILY SUMMARY")
                for key, value in daily.items():
                    print(f"  {key}: {value}")
            elif choice == '10':
                self.print_header("📅 WEEKLY SUMMARY")
                weekly = self.summary.weekly_summary()
                for key, value in weekly.items():
                    if key != 'daily_summaries':
                        print(f"  {key}: {value}")
            elif choice == '0':
                print("\n👋 Goodbye!\n")
                break
            else:
                print("\n❌ Invalid option, try again")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Audit Trail Dashboard')
    parser.add_argument('--quick', action='store_true', help='Quick dashboard (no menu)')
    parser.add_argument('--symbol', type=str, help='Show trade report for symbol')
    parser.add_argument('--recent', type=int, default=20, help='Show recent N events')
    parser.add_argument('--failures', action='store_true', help='Show failures')
    parser.add_argument('--health', action='store_true', help='Show health status')
    
    args = parser.parse_args()
    
    dashboard = AuditDashboard()
    
    if args.quick:
        dashboard.display_dashboard()
    elif args.symbol:
        dashboard.display_trade_report(args.symbol)
    elif args.recent:
        dashboard.display_recent_events(limit=args.recent)
    elif args.failures:
        dashboard.display_failures()
    elif args.health:
        dashboard.display_health_status()
    else:
        # Interactive menu
        dashboard.interactive_menu()


if __name__ == '__main__':
    main()
