#!/usr/bin/env python3
"""
Gap Protector Module
Monitors positions against earnings and economic events
Auto-liquidates positions that violate gap protection rules
Integration with IB Gateway for market orders
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio

from earnings_calendar import get_earnings_calendar, check_earnings_alert
from econ_calendar import (
    get_economic_calendar, 
    check_econ_alerts, 
    should_liquidate_all_positions,
    MAJOR_EVENTS
)

logger = logging.getLogger(__name__)

# File paths
LIQUIDATION_LOG = Path(os.path.expanduser('~/.openclaw/workspace/trading/logs/gap_liquidations.log'))
PROTECTED_PORTFOLIO = Path(os.path.expanduser('~/.openclaw/workspace/trading/protected_portfolio.json'))


def ensure_log_dir():
    """Create logs directory if needed"""
    LIQUIDATION_LOG.parent.mkdir(parents=True, exist_ok=True)


def log_liquidation(symbol: str, price: float, reason: str, event_date: str = None):
    """
    Log a liquidation event
    Format: timestamp | symbol | price | reason | event_date
    """
    ensure_log_dir()
    try:
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | {symbol:6} | ${price:8.2f} | {reason:30} | {event_date or 'N/A'}\n"
        
        with open(LIQUIDATION_LOG, 'a') as f:
            f.write(log_entry)
        
        logger.info(f"📝 Liquidation logged: {symbol} @ ${price:.2f} ({reason})")
    except Exception as e:
        logger.error(f"Error logging liquidation: {e}")


def load_protected_portfolio() -> Dict:
    """Load current portfolio with earnings/econ data"""
    if PROTECTED_PORTFOLIO.exists():
        try:
            with open(PROTECTED_PORTFOLIO, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading portfolio: {e}")
    return {}


def save_protected_portfolio(portfolio: Dict):
    """Save portfolio with gap protection metadata"""
    try:
        PROTECTED_PORTFOLIO.parent.mkdir(parents=True, exist_ok=True)
        with open(PROTECTED_PORTFOLIO, 'w') as f:
            json.dump(portfolio, f, indent=2, default=str)
        logger.info(f"✅ Saved protected portfolio: {len(portfolio)} positions")
    except Exception as e:
        logger.error(f"Error saving portfolio: {e}")


def enrich_portfolio_with_calendar_data(positions: List[Dict]) -> List[Dict]:
    """
    Enrich portfolio positions with earnings and economic event data
    Adds fields: earnings_date, next_econ_event, days_to_event, should_close
    """
    symbols = [p['symbol'] for p in positions]
    
    # Fetch earnings dates
    earnings_data = get_earnings_calendar(symbols)
    
    # Get economic events
    econ_events = get_economic_calendar()
    
    enriched = []
    for position in positions:
        symbol = position['symbol']
        enriched_pos = position.copy()
        
        # Add earnings data
        earnings_date = earnings_data.get(symbol)
        enriched_pos['earnings_date'] = earnings_date
        enriched_pos['earnings_days_away'] = None
        enriched_pos['earnings_alert'] = False
        
        if earnings_date:
            ed = datetime.fromisoformat(earnings_date).date()
            days = (ed - datetime.now().date()).days
            enriched_pos['earnings_days_away'] = days
            enriched_pos['earnings_alert'] = check_earnings_alert(symbol, earnings_date, days_ahead=2)
        
        # Add next economic event data
        enriched_pos['next_econ_event'] = None
        enriched_pos['econ_days_away'] = None
        enriched_pos['econ_alert'] = False
        
        for event in econ_events:
            event_date = datetime.fromisoformat(event['date']).date()
            if event_date >= datetime.now().date():
                enriched_pos['next_econ_event'] = event
                days = (event_date - datetime.now().date()).days
                enriched_pos['econ_days_away'] = days
                enriched_pos['econ_alert'] = days <= MAJOR_EVENTS.get(event.get('event'), {}).get('alert_days', 1)
                break  # Only store the very next event
        
        # Determine if position should be closed
        enriched_pos['should_close'] = enriched_pos['earnings_alert'] or enriched_pos['econ_alert']
        enriched_pos['close_reason'] = None
        
        if enriched_pos['earnings_alert']:
            enriched_pos['close_reason'] = f"Earnings {enriched_pos['earnings_days_away']}d away"
        elif enriched_pos['econ_alert']:
            event = enriched_pos['next_econ_event']
            enriched_pos['close_reason'] = f"{event.get('event')} {enriched_pos['econ_days_away']}d away"
        
        enriched.append(enriched_pos)
    
    return enriched


def identify_liquidation_candidates(positions: List[Dict]) -> List[Dict]:
    """
    Identify positions that should be liquidated based on:
    1. Earnings within 2 days
    2. Major economic events within 1-3 days
    """
    enriched = enrich_portfolio_with_calendar_data(positions)
    
    candidates = [p for p in enriched if p['should_close']]
    
    return candidates


def format_position_with_gap_protection(position: Dict) -> str:
    """Format a position with gap protection metadata"""
    symbol = position['symbol']
    qty = position.get('quantity', 0)
    price = position.get('market_price', 0)
    value = position.get('market_value', 0)
    
    status = "🚨" if position.get('should_close') else "✅"
    
    line = f"{status} {symbol:6} | {qty:6.0f} @ ${price:8.2f} | ${value:10.2f}"
    
    # Add gap protection info if applicable
    if position.get('earnings_alert'):
        days = position.get('earnings_days_away', '?')
        line += f" | 📢 Earnings in {days}d"
    
    if position.get('econ_alert'):
        days = position.get('econ_days_away', '?')
        event = position.get('next_econ_event', {}).get('event', '?')
        line += f" | 📊 {event} in {days}d"
    
    return line


def format_gap_protection_report(positions: List[Dict]) -> str:
    """Format gap protection report for positions"""
    enriched = enrich_portfolio_with_calendar_data(positions)
    
    report = "\n🛡️  GAP PROTECTION REPORT\n"
    report += "=" * 80 + "\n\n"
    
    # Liquidation candidates
    candidates = [p for p in enriched if p['should_close']]
    
    if candidates:
        report += f"🚨 LIQUIDATE NOW ({len(candidates)} positions):\n"
        report += "-" * 80 + "\n"
        for pos in candidates:
            report += format_position_with_gap_protection(pos) + "\n"
        report += "\n"
    else:
        report += "✅ No positions require liquidation\n\n"
    
    # Safe positions
    safe = [p for p in enriched if not p['should_close']]
    report += f"✅ SAFE ({len(safe)} positions):\n"
    report += "-" * 80 + "\n"
    for pos in safe[:10]:  # Show first 10 safe positions
        report += format_position_with_gap_protection(pos) + "\n"
    
    if len(safe) > 10:
        report += f"  ... and {len(safe) - 10} more\n"
    
    report += "\n" + "=" * 80 + "\n"
    return report


async def liquidate_position_ib(
    symbol: str,
    quantity: float,
    ib_conn,
    reason: str = None
) -> Tuple[bool, Optional[float]]:
    """
    Liquidate a position via IB Gateway
    Returns: (success, close_price)
    
    NOTE: Requires IB connection and proper contract setup
    """
    try:
        from ib_insync import IB, Stock, MarketOrder
        
        if not ib_conn or not ib_conn.isConnected():
            logger.error(f"❌ IB not connected, cannot liquidate {symbol}")
            return False, None
        
        # Create stock contract
        contract = Stock(symbol, 'SMART', 'USD')
        
        # Create market order (sell all)
        order = MarketOrder('SELL', quantity)
        
        # Place order
        logger.info(f"📤 Placing liquidation order for {symbol} ({quantity} shares)...")
        trade = ib_conn.placeOrder(contract, order)
        
        # Wait for order to fill (with timeout)
        ib_conn.sleep(2)  # Let order process
        
        if trade.isDone():
            fills = trade.fills
            if fills:
                close_price = fills[0].execution.price
                logger.info(f"✅ Liquidated {symbol} @ ${close_price:.2f}")
                
                # Log the liquidation
                log_liquidation(symbol, close_price, reason or "Manual liquidation")
                return True, close_price
        
        logger.warning(f"⚠️  Order may not have filled immediately")
        return False, None
        
    except Exception as e:
        logger.error(f"❌ Error liquidating {symbol}: {e}")
        return False, None


async def auto_liquidate_violations(
    positions: List[Dict],
    ib_conn=None,
    dry_run: bool = True
) -> Dict:
    """
    Auto-liquidate positions that violate gap protection rules
    
    Args:
        positions: Current portfolio positions
        ib_conn: IB connection object
        dry_run: If True, log but don't actually liquidate
    
    Returns:
        {
            'liquidated': [{'symbol', 'price', 'reason'}],
            'failed': [{'symbol', 'error'}],
            'skipped': [{'symbol', 'reason'}]
        }
    """
    candidates = identify_liquidation_candidates(positions)
    
    result = {
        'liquidated': [],
        'failed': [],
        'skipped': []
    }
    
    if not candidates:
        logger.info("✅ No liquidation candidates found")
        return result
    
    logger.warning(f"⚠️  Found {len(candidates)} positions to liquidate")
    
    for pos in candidates:
        symbol = pos['symbol']
        qty = pos['quantity']
        reason = pos['close_reason']
        
        if dry_run:
            logger.info(f"[DRY RUN] Would liquidate {symbol} ({qty} shares): {reason}")
            result['skipped'].append({
                'symbol': symbol,
                'reason': f'Dry run: {reason}'
            })
        else:
            try:
                success, price = await liquidate_position_ib(symbol, qty, ib_conn, reason)
                
                if success:
                    result['liquidated'].append({
                        'symbol': symbol,
                        'price': price,
                        'reason': reason,
                        'quantity': qty
                    })
                else:
                    result['failed'].append({
                        'symbol': symbol,
                        'error': 'Order did not fill'
                    })
            except Exception as e:
                result['failed'].append({
                    'symbol': symbol,
                    'error': str(e)
                })
    
    return result


def check_critical_econ_event() -> Optional[Dict]:
    """
    Check if there's a critical economic event that should trigger ALL liquidation
    Returns the event info if found, None otherwise
    """
    check = should_liquidate_all_positions()
    if check['should_liquidate']:
        return check['event']
    return None


def format_liquidation_summary(result: Dict) -> str:
    """Format liquidation result summary"""
    report = "\n📋 LIQUIDATION SUMMARY\n"
    report += "=" * 60 + "\n\n"
    
    if result['liquidated']:
        report += f"✅ LIQUIDATED ({len(result['liquidated'])}):\n"
        for item in result['liquidated']:
            report += f"  {item['symbol']:6} @ ${item['price']:8.2f} - {item['reason']}\n"
        report += "\n"
    
    if result['failed']:
        report += f"❌ FAILED ({len(result['failed'])}):\n"
        for item in result['failed']:
            report += f"  {item['symbol']:6} - {item['error']}\n"
        report += "\n"
    
    if result['skipped']:
        report += f"⏭️  SKIPPED ({len(result['skipped'])}):\n"
        for item in result['skipped']:
            report += f"  {item['symbol']:6} - {item['reason']}\n"
        report += "\n"
    
    report += "=" * 60 + "\n"
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Example usage with mock positions
    mock_positions = [
        {
            'symbol': 'AAPL',
            'quantity': 100,
            'market_price': 180.50,
            'market_value': 18050.00
        },
        {
            'symbol': 'MSFT',
            'quantity': 50,
            'market_price': 420.00,
            'market_value': 21000.00
        },
        {
            'symbol': 'TSLA',
            'quantity': 25,
            'market_price': 250.00,
            'market_value': 6250.00
        }
    ]
    
    # Generate report
    print(format_gap_protection_report(mock_positions))
    
    # Check for critical econ events
    critical = check_critical_econ_event()
    if critical:
        print(f"\n🔴 CRITICAL EVENT: {critical['description']}")
