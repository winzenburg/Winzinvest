#!/usr/bin/env python3
"""
Audit Trail Query Module
Provides queryable interface to audit.jsonl
Functions to filter, search, and export audit events
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Audit log path
AUDIT_LOG_FILE = os.path.expanduser('~/.openclaw/workspace/trading/logs/audit.jsonl')


class AuditQuery:
    """
    Query interface for audit.jsonl
    Provides efficient filtering and searching
    """
    
    def __init__(self, audit_file: str = AUDIT_LOG_FILE):
        """
        Initialize audit query engine
        
        Args:
            audit_file: Path to audit.jsonl file
        """
        self.audit_file = audit_file
        self.events: List[Dict[str, Any]] = []
        self._load_events()
    
    def _load_events(self):
        """Load all events from audit log"""
        try:
            if not os.path.exists(self.audit_file):
                logger.warning(f"⚠️  Audit file not found: {self.audit_file}")
                return
            
            with open(self.audit_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            event = json.loads(line)
                            self.events.append(event)
                        except json.JSONDecodeError as e:
                            logger.warning(f"⚠️  Failed to parse event line: {e}")
            
            logger.info(f"📂 Loaded {len(self.events)} events from audit log")
        
        except Exception as e:
            logger.error(f"❌ Error loading audit events: {e}")
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse ISO 8601 timestamp"""
        if ts_str.endswith('Z'):
            ts_str = ts_str[:-1]
        return datetime.fromisoformat(ts_str)
    
    def query_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get all events for a specific symbol
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
        
        Returns:
            List of all events mentioning this symbol
        """
        results = []
        symbol_upper = symbol.upper()
        
        for event in self.events:
            data = event.get('data', {})
            
            # Check various symbol fields
            if (data.get('symbol') == symbol_upper or 
                symbol_upper in data.get('symbols', []) or
                any(symbol_upper in str(s) for s in data.get('symbols', []))):
                results.append(event)
        
        logger.info(f"🔍 Found {len(results)} events for {symbol}")
        return results
    
    def query_by_date(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Get all events within a date range
        
        Args:
            start_date: ISO date (e.g., '2026-02-26')
            end_date: ISO date (e.g., '2026-02-27')
        
        Returns:
            List of events in the date range
        """
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date) + timedelta(days=1)
            
            results = []
            for event in self.events:
                ts = self._parse_timestamp(event.get('timestamp', ''))
                if start <= ts < end:
                    results.append(event)
            
            logger.info(f"📅 Found {len(results)} events between {start_date} and {end_date}")
            return results
        
        except Exception as e:
            logger.error(f"❌ Error querying by date: {e}")
            return []
    
    def query_by_event_type(self, event_type: str) -> List[Dict[str, Any]]:
        """
        Get all events of a specific type
        
        Args:
            event_type: Event type (e.g., 'ENTRY_SIGNAL', 'STOP_FILLED')
        
        Returns:
            List of events of this type
        """
        results = [e for e in self.events if e.get('event_type') == event_type]
        logger.info(f"📋 Found {len(results)} {event_type} events")
        return results
    
    def query_by_component(self, component: str) -> List[Dict[str, Any]]:
        """
        Get all events from a specific component
        
        Args:
            component: Component name (e.g., 'ib_gateway', 'screener', 'webhook_listener')
        
        Returns:
            List of events from this component
        """
        results = []
        component_lower = component.lower()
        
        for event in self.events:
            # Check event_type for component context
            if component_lower in event.get('event_type', '').lower():
                results.append(event)
            
            # Check data for component field
            if component_lower in str(event.get('data', {})).lower():
                results.append(event)
        
        # Remove duplicates
        results = list({json.dumps(e, sort_keys=True): e for e in results}.values())
        
        logger.info(f"🔧 Found {len(results)} events from {component}")
        return results
    
    def query_failures(self) -> List[Dict[str, Any]]:
        """
        Get all failures, errors, and blocked actions
        
        Returns:
            List of failure/error/blocked events
        """
        results = []
        
        for event in self.events:
            event_type = event.get('event_type', '')
            data = event.get('data', {})
            
            # Include ERROR_EVENT and blocked risk gates
            if (event_type == 'ERROR_EVENT' or 
                (event_type == 'RISK_GATE_TRIGGERED' and data.get('blocked')) or
                data.get('status') == 'error' or
                'error' in str(data).lower() or
                'failed' in str(data).lower()):
                results.append(event)
        
        logger.info(f"⚠️  Found {len(results)} failure/error events")
        return results
    
    def query_by_time_range(self, hours_ago: int = 24) -> List[Dict[str, Any]]:
        """
        Get all events from the last N hours
        
        Args:
            hours_ago: Number of hours to look back
        
        Returns:
            List of recent events
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_ago)
        results = []
        
        for event in self.events:
            ts = self._parse_timestamp(event.get('timestamp', ''))
            if ts >= cutoff_time:
                results.append(event)
        
        logger.info(f"⏰ Found {len(results)} events in last {hours_ago} hours")
        return results
    
    def export_trade_report(self, symbol: str, start_timestamp: Optional[str] = None,
                           end_timestamp: Optional[str] = None) -> Dict[str, Any]:
        """
        Export full audit trail for a specific trade
        
        Args:
            symbol: Stock symbol
            start_timestamp: Optional start timestamp (ISO format)
            end_timestamp: Optional end timestamp (ISO format)
        
        Returns:
            Dictionary with all events related to this trade
        """
        trade_events = self.query_by_symbol(symbol)
        
        if start_timestamp and end_timestamp:
            try:
                start = self._parse_timestamp(start_timestamp)
                end = self._parse_timestamp(end_timestamp)
                
                trade_events = [
                    e for e in trade_events
                    if start <= self._parse_timestamp(e.get('timestamp', '')) <= end
                ]
            except Exception as e:
                logger.warning(f"⚠️  Error filtering by timestamp: {e}")
        
        # Group events by type
        events_by_type = {}
        for event in trade_events:
            event_type = event.get('event_type')
            if event_type not in events_by_type:
                events_by_type[event_type] = []
            events_by_type[event_type].append(event)
        
        # Calculate summary statistics
        summary = {
            'symbol': symbol,
            'total_events': len(trade_events),
            'events_by_type': {k: len(v) for k, v in events_by_type.items()},
            'entry_signals': len(events_by_type.get('ENTRY_SIGNAL', [])),
            'stops_placed': len(events_by_type.get('STOP_PLACED', [])),
            'stops_filled': len(events_by_type.get('STOP_FILLED', [])),
            'positions_closed': len(events_by_type.get('POSITION_CLOSED', [])),
            'errors': len(events_by_type.get('ERROR_EVENT', [])),
        }
        
        return {
            'symbol': symbol,
            'summary': summary,
            'events_by_type': events_by_type,
            'all_events': trade_events,
            'generated_at': datetime.utcnow().isoformat() + 'Z'
        }
    
    def get_recent_trades(self, limit: int = 10) -> List[Tuple[str, int]]:
        """
        Get list of recently active symbols
        
        Args:
            limit: Number of symbols to return
        
        Returns:
            List of (symbol, event_count) tuples
        """
        symbol_counts = {}
        
        for event in self.events:
            data = event.get('data', {})
            symbol = data.get('symbol')
            if symbol:
                symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        
        # Sort by event count, most recent symbols first
        sorted_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_symbols[:limit]
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """
        Get summary of system health checks
        
        Returns:
            Dictionary with health check statistics
        """
        health_events = self.query_by_event_type('HEALTH_CHECK')
        
        if not health_events:
            return {'status': 'no_health_checks', 'total_checks': 0}
        
        # Group by component
        by_component = {}
        for event in health_events:
            data = event.get('data', {})
            component = data.get('component', 'unknown')
            status = data.get('status', 'unknown')
            
            if component not in by_component:
                by_component[component] = {'ok': 0, 'error': 0, 'warning': 0}
            
            if status == 'ok':
                by_component[component]['ok'] += 1
            elif status == 'error':
                by_component[component]['error'] += 1
            elif status == 'warning':
                by_component[component]['warning'] += 1
        
        # Get latest health status for each component
        latest_status = {}
        for component in by_component:
            component_events = [e for e in health_events 
                              if e.get('data', {}).get('component') == component]
            if component_events:
                latest_event = component_events[-1]
                latest_status[component] = {
                    'status': latest_event.get('data', {}).get('status'),
                    'timestamp': latest_event.get('timestamp'),
                    'latency_ms': latest_event.get('data', {}).get('response_time_ms'),
                }
        
        return {
            'total_checks': len(health_events),
            'by_component': by_component,
            'latest_status': latest_status,
        }
    
    def export_to_csv(self, output_file: str = None, event_type: Optional[str] = None):
        """
        Export audit events to CSV file
        
        Args:
            output_file: Path to output CSV file
            event_type: Optional event type filter
        """
        import csv
        
        # Filter events if type specified
        events_to_export = self.query_by_event_type(event_type) if event_type else self.events
        
        if not events_to_export:
            logger.warning("⚠️  No events to export")
            return
        
        # Generate output filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            event_filter = f"_{event_type}" if event_type else ""
            output_file = f"{self.audit_file.replace('.jsonl', f'_export{event_filter}_{timestamp}.csv')}"
        
        try:
            # Flatten events for CSV
            flat_events = []
            for event in events_to_export:
                flat = {
                    'timestamp': event.get('timestamp'),
                    'event_type': event.get('event_type'),
                }
                # Flatten data fields
                flat.update(event.get('data', {}))
                flat_events.append(flat)
            
            # Get all unique field names
            all_keys = set()
            for event in flat_events:
                all_keys.update(event.keys())
            
            # Write CSV
            with open(output_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                writer.writeheader()
                writer.writerows(flat_events)
            
            logger.info(f"✅ Exported {len(flat_events)} events to {output_file}")
        
        except Exception as e:
            logger.error(f"❌ Error exporting to CSV: {e}")


# Global query instance
_global_audit_query: Optional[AuditQuery] = None


def get_audit_query() -> AuditQuery:
    """Get or create global audit query instance"""
    global _global_audit_query
    
    if _global_audit_query is None:
        _global_audit_query = AuditQuery()
    
    return _global_audit_query


def refresh_audit_query():
    """Refresh the global audit query instance (reload events)"""
    global _global_audit_query
    _global_audit_query = AuditQuery()


# Convenience query functions
def by_symbol(symbol: str) -> List[Dict[str, Any]]:
    """Query all events for a symbol"""
    return get_audit_query().query_by_symbol(symbol)


def by_date(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Query events in date range"""
    return get_audit_query().query_by_date(start_date, end_date)


def by_type(event_type: str) -> List[Dict[str, Any]]:
    """Query events of a specific type"""
    return get_audit_query().query_by_event_type(event_type)


def by_component(component: str) -> List[Dict[str, Any]]:
    """Query events from a component"""
    return get_audit_query().query_by_component(component)


def failures() -> List[Dict[str, Any]]:
    """Query all failures and errors"""
    return get_audit_query().query_failures()


def recent_hours(hours: int = 24) -> List[Dict[str, Any]]:
    """Query events from last N hours"""
    return get_audit_query().query_by_time_range(hours)


def trade_report(symbol: str) -> Dict[str, Any]:
    """Get full trade report for symbol"""
    return get_audit_query().export_trade_report(symbol)


def recent_trades(limit: int = 10) -> List[Tuple[str, int]]:
    """Get recently active symbols"""
    return get_audit_query().get_recent_trades(limit)


def health_summary() -> Dict[str, Any]:
    """Get system health summary"""
    return get_audit_query().get_system_health_summary()


if __name__ == '__main__':
    # Test the audit query interface
    print("🧪 Testing Audit Query Interface...")
    
    query = get_audit_query()
    
    # Test various queries
    print("\n📋 Recent trades:")
    for symbol, count in query.get_recent_trades(5):
        print(f"  {symbol}: {count} events")
    
    print("\n❌ Recent failures/errors:")
    failures = query.query_failures()
    for event in failures[-3:]:
        print(f"  {event.get('timestamp')}: {event.get('event_type')} - {event.get('data')}")
    
    print("\n💚 System health:")
    health = query.get_system_health_summary()
    print(f"  Total health checks: {health.get('total_checks')}")
    
    print(f"\n✅ Query interface ready!")
