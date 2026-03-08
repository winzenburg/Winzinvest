#!/usr/bin/env python3
"""
Audit Summary & Reporting Module
Daily, weekly, and custom summaries from audit logs
Export reports for analysis
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import audit query
try:
    from audit_query import AuditQuery, get_audit_query
except ImportError:
    logger.error("❌ audit_query module not available")
    AuditQuery = None

AUDIT_LOG_FILE = os.path.expanduser('~/.openclaw/workspace/trading/logs/audit.jsonl')
REPORTS_DIR = os.path.expanduser('~/.openclaw/workspace/trading/reports')

# Ensure reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)


class AuditSummary:
    """Generate audit summaries and reports"""
    
    def __init__(self):
        """Initialize summary generator"""
        self.query = get_audit_query() if AuditQuery else None
    
    def _get_timestamp(self) -> str:
        """Get ISO 8601 timestamp"""
        return datetime.utcnow().isoformat() + 'Z'
    
    def daily_summary(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate daily summary
        
        Args:
            date_str: Date in format YYYY-MM-DD (default: today)
        
        Returns:
            Dictionary with daily stats
        """
        if not self.query:
            logger.error("❌ Query not available")
            return {}
        
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # Get tomorrow's date for range
            date_obj = datetime.fromisoformat(date_str)
            next_day = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Get all events for the day
            events = self.query.query_by_date(date_str, next_day)
            
            # Count events by type
            event_types = {}
            symbols = set()
            
            for event in events:
                event_type = event.get('event_type')
                event_types[event_type] = event_types.get(event_type, 0) + 1
                
                # Track symbols
                data = event.get('data', {})
                if data.get('symbol'):
                    symbols.add(data.get('symbol'))
            
            # Calculate statistics
            summary = {
                'date': date_str,
                'generated_at': self._get_timestamp(),
                'total_events': len(events),
                'unique_symbols': len(symbols),
                'symbols': sorted(list(symbols)),
                'event_counts': event_types,
                'entry_signals': event_types.get('ENTRY_SIGNAL', 0),
                'stops_placed': event_types.get('STOP_PLACED', 0),
                'stops_filled': event_types.get('STOP_FILLED', 0),
                'positions_closed': event_types.get('POSITION_CLOSED', 0),
                'errors': event_types.get('ERROR_EVENT', 0),
                'risk_gates_triggered': event_types.get('RISK_GATE_TRIGGERED', 0),
            }
            
            # Calculate P&L if available
            pnl_data = self._calculate_pnl(events)
            summary['pnl'] = pnl_data
            
            logger.info(f"📅 Daily summary for {date_str}: {summary['total_events']} events, "
                       f"{summary['entry_signals']} entries, {summary['stops_filled']} stops filled")
            
            return summary
        
        except Exception as e:
            logger.error(f"❌ Error generating daily summary: {e}")
            return {}
    
    def weekly_summary(self, weeks_ago: int = 0) -> Dict[str, Any]:
        """
        Generate weekly summary
        
        Args:
            weeks_ago: Number of weeks back (0 = current week)
        
        Returns:
            Dictionary with weekly stats
        """
        if not self.query:
            logger.error("❌ Query not available")
            return {}
        
        try:
            # Calculate week start and end
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday() + (weeks_ago * 7))
            week_end = week_start + timedelta(days=7)
            
            start_str = week_start.strftime('%Y-%m-%d')
            end_str = week_end.strftime('%Y-%m-%d')
            
            # Get all events for the week
            events = self.query.query_by_date(start_str, end_str)
            
            # Generate daily summaries
            daily_summaries = []
            current_date = week_start
            while current_date < week_end:
                daily_summary = self.daily_summary(current_date.strftime('%Y-%m-%d'))
                daily_summaries.append(daily_summary)
                current_date += timedelta(days=1)
            
            # Aggregate statistics
            total_entries = sum(s.get('entry_signals', 0) for s in daily_summaries)
            total_stops_filled = sum(s.get('stops_filled', 0) for s in daily_summaries)
            total_positions_closed = sum(s.get('positions_closed', 0) for s in daily_summaries)
            total_errors = sum(s.get('errors', 0) for s in daily_summaries)
            
            # Calculate win rate
            win_rate = 0
            if total_positions_closed > 0:
                # This is simplified - in reality you'd check P&L
                win_rate = (total_stops_filled * 0.5) / total_positions_closed if total_positions_closed > 0 else 0
            
            summary = {
                'period': f"{start_str} to {end_str}",
                'generated_at': self._get_timestamp(),
                'total_events': len(events),
                'daily_summaries': daily_summaries,
                'aggregate': {
                    'entry_signals': total_entries,
                    'stops_filled': total_stops_filled,
                    'positions_closed': total_positions_closed,
                    'errors': total_errors,
                    'avg_signals_per_day': total_entries / 7 if total_entries > 0 else 0,
                    'fill_rate': (total_stops_filled / total_entries * 100) if total_entries > 0 else 0,
                },
            }
            
            logger.info(f"📊 Weekly summary: {total_entries} entries, {total_stops_filled} fills, "
                       f"{total_errors} errors")
            
            return summary
        
        except Exception as e:
            logger.error(f"❌ Error generating weekly summary: {e}")
            return {}
    
    def _calculate_pnl(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate P&L from events"""
        pnl_data = {
            'total_pnl': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'entries': 0,
            'exits': 0,
        }
        
        try:
            # Simple P&L calculation
            positions = {}
            
            for event in events:
                event_type = event.get('event_type')
                data = event.get('data', {})
                symbol = data.get('symbol')
                
                if not symbol:
                    continue
                
                if event_type == 'ENTRY_SIGNAL':
                    if symbol not in positions:
                        positions[symbol] = {
                            'entry_price': data.get('entry_price'),
                            'quantity': data.get('quantity'),
                            'entry_time': event.get('timestamp'),
                        }
                    pnl_data['entries'] += 1
                
                elif event_type == 'POSITION_CLOSED':
                    if symbol in positions:
                        entry_price = positions[symbol]['entry_price']
                        exit_price = data.get('exit_price')
                        quantity = positions[symbol]['quantity']
                        
                        trade_pnl = (exit_price - entry_price) * quantity
                        pnl_data['total_pnl'] += trade_pnl
                        
                        if trade_pnl > 0:
                            pnl_data['winning_trades'] += 1
                        else:
                            pnl_data['losing_trades'] += 1
                        
                        pnl_data['exits'] += 1
                        del positions[symbol]
        
        except Exception as e:
            logger.warning(f"⚠️  Error calculating P&L: {e}")
        
        return pnl_data
    
    def failure_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Generate summary of failures and errors
        
        Args:
            hours: Hours to look back
        
        Returns:
            Dictionary with failure stats
        """
        if not self.query:
            logger.error("❌ Query not available")
            return {}
        
        try:
            failures = self.query.query_failures()
            
            # Filter by time if specified
            if hours > 0:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                failures = [f for f in failures 
                          if datetime.fromisoformat(f.get('timestamp', '').replace('Z', '')) >= cutoff]
            
            # Group by type
            by_type = {}
            by_component = {}
            
            for failure in failures:
                event_type = failure.get('event_type')
                data = failure.get('data', {})
                component = data.get('component', 'unknown')
                
                by_type[event_type] = by_type.get(event_type, 0) + 1
                by_component[component] = by_component.get(component, 0) + 1
            
            summary = {
                'time_window': f'last {hours} hours',
                'generated_at': self._get_timestamp(),
                'total_failures': len(failures),
                'by_type': by_type,
                'by_component': by_component,
                'recent_failures': failures[-10:],  # Last 10
            }
            
            logger.info(f"⚠️  Failure summary: {len(failures)} failures in last {hours}h")
            
            return summary
        
        except Exception as e:
            logger.error(f"❌ Error generating failure summary: {e}")
            return {}
    
    def export_daily_report(self, date_str: Optional[str] = None, format: str = 'json') -> str:
        """
        Export daily report to file
        
        Args:
            date_str: Date (default: today)
            format: Export format ('json' or 'csv')
        
        Returns:
            Path to exported file
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        summary = self.daily_summary(date_str)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if format == 'json':
            filename = f"daily_report_{date_str}_{timestamp}.json"
            filepath = os.path.join(REPORTS_DIR, filename)
            
            with open(filepath, 'w') as f:
                json.dump(summary, f, indent=2)
        
        elif format == 'csv':
            import csv
            filename = f"daily_report_{date_str}_{timestamp}.csv"
            filepath = os.path.join(REPORTS_DIR, filename)
            
            # Flatten and export
            flat = {
                'date': summary.get('date'),
                'total_events': summary.get('total_events'),
                'entry_signals': summary.get('entry_signals'),
                'stops_placed': summary.get('stops_placed'),
                'stops_filled': summary.get('stops_filled'),
                'positions_closed': summary.get('positions_closed'),
                'errors': summary.get('errors'),
                'total_pnl': summary.get('pnl', {}).get('total_pnl', 0),
            }
            
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=flat.keys())
                writer.writeheader()
                writer.writerow(flat)
        
        logger.info(f"📊 Exported daily report to {filepath}")
        return filepath
    
    def health_score(self, hours: int = 24) -> Dict[str, Any]:
        """
        Calculate system health score
        
        Args:
            hours: Hours to analyze
        
        Returns:
            Dictionary with health score breakdown
        """
        if not self.query:
            logger.error("❌ Query not available")
            return {}
        
        try:
            # Get health checks
            health_events = self.query.query_by_event_type('HEALTH_CHECK')
            
            # Filter by time
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            health_events = [e for e in health_events 
                           if datetime.fromisoformat(e.get('timestamp', '').replace('Z', '')) >= cutoff]
            
            if not health_events:
                return {'score': 0, 'message': 'No health data available'}
            
            # Count OK vs Error
            ok_count = sum(1 for e in health_events if e.get('data', {}).get('status') == 'ok')
            error_count = sum(1 for e in health_events if e.get('data', {}).get('status') == 'error')
            
            # Calculate score (0-100)
            score = int((ok_count / len(health_events)) * 100) if health_events else 0
            
            # Get failures
            failures = self.query.query_failures()
            failure_count = len([f for f in failures 
                               if datetime.fromisoformat(f.get('timestamp', '').replace('Z', '')) >= cutoff])
            
            return {
                'health_score': score,
                'timeframe': f'{hours}h',
                'total_checks': len(health_events),
                'healthy': ok_count,
                'unhealthy': error_count,
                'failures': failure_count,
                'message': self._get_health_message(score),
            }
        
        except Exception as e:
            logger.error(f"❌ Error calculating health score: {e}")
            return {'score': 0, 'error': str(e)}
    
    def _get_health_message(self, score: int) -> str:
        """Get health status message based on score"""
        if score >= 95:
            return "✅ System is healthy"
        elif score >= 85:
            return "⚠️  System health is good, minor issues detected"
        elif score >= 70:
            return "⚠️  System health is degraded, attention needed"
        else:
            return "🚨 System health is critical"


def generate_daily_report(date_str: Optional[str] = None) -> Dict[str, Any]:
    """Generate and return daily report"""
    summary_gen = AuditSummary()
    return summary_gen.daily_summary(date_str)


def generate_weekly_report(weeks_ago: int = 0) -> Dict[str, Any]:
    """Generate and return weekly report"""
    summary_gen = AuditSummary()
    return summary_gen.weekly_summary(weeks_ago)


def print_summary(date_str: Optional[str] = None):
    """Print formatted summary to console"""
    summary = generate_daily_report(date_str)
    
    if not summary:
        print("❌ Could not generate summary")
        return
    
    print("\n" + "="*60)
    print(f"📊 Daily Summary - {summary.get('date')}")
    print("="*60)
    
    print(f"\n📈 Events: {summary.get('total_events')} total")
    print(f"   Symbols: {summary.get('unique_symbols')}")
    
    print(f"\n🎯 Trading Activity:")
    print(f"   Entry Signals: {summary.get('entry_signals')}")
    print(f"   Stops Placed: {summary.get('stops_placed')}")
    print(f"   Stops Filled: {summary.get('stops_filled')}")
    print(f"   Positions Closed: {summary.get('positions_closed')}")
    
    pnl = summary.get('pnl', {})
    print(f"\n💰 P&L:")
    print(f"   Total P&L: ${pnl.get('total_pnl', 0):.2f}")
    print(f"   Winning Trades: {pnl.get('winning_trades', 0)}")
    print(f"   Losing Trades: {pnl.get('losing_trades', 0)}")
    
    print(f"\n⚠️  Risk:")
    print(f"   Errors: {summary.get('errors')}")
    print(f"   Risk Gates Triggered: {summary.get('risk_gates_triggered')}")
    
    print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    # Generate and display daily summary
    print("📊 Generating audit summaries...")
    
    # Daily summary
    print_summary()
    
    # Weekly summary
    print("\n📅 Generating weekly summary...")
    summary_gen = AuditSummary()
    weekly = summary_gen.weekly_summary()
    if weekly:
        print(f"✅ Weekly summary: {weekly['aggregate']}")
    
    # Health score
    print("\n🏥 Calculating health score...")
    health = summary_gen.health_score(24)
    print(f"✅ Health Score: {health.get('health_score')}/100 - {health.get('message')}")
    
    # Failure summary
    print("\n❌ Failure summary (last 24h)...")
    failures = summary_gen.failure_summary(24)
    print(f"✅ Failures: {failures.get('total_failures')}")
    
    print("\n✅ Summary generation complete!")
