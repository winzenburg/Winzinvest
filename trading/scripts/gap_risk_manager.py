#!/usr/bin/env python3
"""
Gap Risk Manager
Closes short positions before market close to avoid overnight gaps
Rules:
- CSP (cash-secured puts): Close or liquidate at 3:55 PM
- Short calls: Buy protective call or liquidate at 3:55 PM
- Especially critical during earnings blackout periods
"""

from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)

# Market close time (ET) = 4:00 PM
MARKET_CLOSE_ET = time(16, 0)
# Action time: 3:55 PM (5 min before close)
ACTION_TIME_ET = time(15, 55)

def is_market_close_approaching(current_time_et: datetime = None) -> bool:
    """
    Check if market close is within 5 minutes.
    
    Args:
        current_time_et: Current time in ET (if None, uses now)
    
    Returns: True if within 5 minutes of close
    """
    if current_time_et is None:
        current_time_et = datetime.now()
    
    current = current_time_et.time()
    return current >= ACTION_TIME_ET

def get_time_to_close_minutes(current_time_et: datetime = None) -> float:
    """
    Get minutes until market close.
    
    Args:
        current_time_et: Current time in ET
    
    Returns: Minutes until close (0 if already closed)
    """
    if current_time_et is None:
        current_time_et = datetime.now()
    
    current = current_time_et.time()
    close = MARKET_CLOSE_ET
    
    # Convert to seconds for calculation
    current_seconds = current.hour * 3600 + current.minute * 60 + current.second
    close_seconds = close.hour * 3600 + close.minute * 60
    
    minutes_left = (close_seconds - current_seconds) / 60.0
    return max(0, minutes_left)

def should_close_gap_risk_positions(current_time_et: datetime = None) -> bool:
    """
    Check if gap risk positions should be closed (within 5 min of close).
    
    Returns: True if should close now
    """
    return is_market_close_approaching(current_time_et)

def get_gap_risk_positions(positions: list, position_types: list = ['CSP', 'short_call']) -> list:
    """
    Get list of positions with gap risk (shorts that need closing before close).
    
    Args:
        positions: List of position dicts with 'symbol', 'quantity', 'type' (CSP/call/etc)
        position_types: Types of positions that have gap risk
    
    Returns: List of gap-risk positions
    """
    gap_risk = []
    for pos in positions:
        if pos.get('quantity', 0) < 0:  # Short positions
            pos_type = pos.get('type', '').upper()
            if pos_type in ['CSP', 'SHORT_CALL']:
                gap_risk.append({
                    'symbol': pos['symbol'],
                    'quantity': abs(pos['quantity']),
                    'type': pos_type,
                    'entry_price': pos.get('entry_price'),
                    'current_price': pos.get('current_price'),
                    'days_to_expiration': pos.get('days_to_expiration', 0),
                })
    
    return gap_risk

def calculate_gap_risk_impact(position: dict, gap_scenarios: list = [1, 2, 5]) -> dict:
    """
    Estimate impact of overnight gaps on short position.
    
    Args:
        position: Position dict
        gap_scenarios: % gap scenarios to model (e.g., [1, 2, 5] = 1%, 2%, 5% gaps)
    
    Returns: {
        'symbol': str,
        'current_value': float,
        'gap_scenarios': [{ gap_pct, estimated_loss }],
        'max_loss': float,
    }
    """
    if not position.get('current_price'):
        return None
    
    current = position['current_price']
    quantity = position['quantity']
    
    scenarios = []
    max_loss = 0
    
    for gap in gap_scenarios:
        # Gap up on short position = loss
        new_price = current * (1 + gap / 100.0)
        loss = (new_price - current) * quantity * 100  # Options are 100 shares per contract
        scenarios.append({
            'gap_pct': gap,
            'new_price': round(new_price, 2),
            'estimated_loss': round(loss, 2),
        })
        max_loss = max(max_loss, loss)
    
    return {
        'symbol': position['symbol'],
        'type': position['type'],
        'current_price': current,
        'current_value': current * quantity * 100,
        'gap_scenarios': scenarios,
        'max_estimated_loss': max_loss,
    }

def recommend_gap_mitigation(position: dict) -> dict:
    """
    Recommend how to mitigate gap risk for a position.
    
    Args:
        position: Position dict (short position)
    
    Returns: {
        'symbol': str,
        'type': str,
        'risk_level': 'low' | 'medium' | 'high',
        'recommendations': [str],
        'priority': 'close_now' | 'close_by_eod' | 'monitor',
    }
    """
    dte = position.get('days_to_expiration', 0)
    current = position.get('current_price', 0)
    
    risk_level = 'medium'
    recommendations = []
    priority = 'close_by_eod'
    
    # High risk: short options expiring soon
    if dte <= 2:
        risk_level = 'high'
        priority = 'close_now'
        recommendations.append(f"Close immediately (expires in {dte} days)")
        recommendations.append("High assignment risk overnight")
    
    # Medium risk: normal short options
    elif dte <= 7:
        risk_level = 'medium'
        priority = 'close_by_eod'
        recommendations.append(f"Close before end of day (expires in {dte} days)")
        recommendations.append("Avoid overnight gap risk")
    
    # Low risk: longer dated
    else:
        risk_level = 'low'
        priority = 'monitor'
        recommendations.append("Monitor gap risk; can hold overnight if thesis intact")
    
    # Add general recommendations
    recommendations.append("Alternative: Buy protective call if bullish")
    recommendations.append("Alternative: Reduce position size by 50%")
    
    return {
        'symbol': position['symbol'],
        'type': position['type'],
        'dte': dte,
        'risk_level': risk_level,
        'recommendations': recommendations,
        'priority': priority,
    }

def get_eod_checklist(positions: list, current_time_et: datetime = None) -> dict:
    """
    Generate end-of-day checklist for gap risk management.
    
    Args:
        positions: List of current positions
        current_time_et: Current time in ET
    
    Returns: {
        'time_remaining_min': float,
        'should_act': bool,
        'gap_risk_positions': [position],
        'actions': [str],
        'summary': str,
    }
    """
    minutes = get_time_to_close_minutes(current_time_et)
    should_act = should_close_gap_risk_positions(current_time_et)
    
    gap_risk = get_gap_risk_positions(positions)
    
    actions = []
    if should_act and gap_risk:
        actions.append(f"⏰ {minutes:.1f} minutes to close: EXECUTE NOW")
        for pos in gap_risk:
            actions.append(f"  - Close {pos['symbol']} {pos['type']} ({pos['quantity']} contracts)")
    elif gap_risk:
        actions.append(f"⏰ {minutes:.1f} minutes to close: Prepare liquidation orders")
        for pos in gap_risk:
            actions.append(f"  - Ready to close: {pos['symbol']} {pos['type']}")
    else:
        actions.append("✅ No gap risk positions to manage")
    
    summary = "URGENT" if should_act else "OK"
    if gap_risk:
        summary += f": {len(gap_risk)} position(s) need gap risk attention"
    
    return {
        'time_remaining_min': minutes,
        'should_act': should_act,
        'gap_risk_positions': gap_risk,
        'actions': actions,
        'summary': summary,
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test
    print("\n=== Test: Time to Close ===")
    from datetime import datetime
    
    test_time_early = datetime.strptime("2026-02-23 14:00:00", "%Y-%m-%d %H:%M:%S")
    test_time_close = datetime.strptime("2026-02-23 15:57:00", "%Y-%m-%d %H:%M:%S")
    
    print(f"Early (2 PM): {get_time_to_close_minutes(test_time_early):.1f} min to close")
    print(f"Close (3:57 PM): {get_time_to_close_minutes(test_time_close):.1f} min to close")
    print(f"Should close at 3:57 PM? {should_close_gap_risk_positions(test_time_close)}")
    
    print("\n=== Test: Gap Risk Analysis ===")
    test_pos = {
        'symbol': 'AAPL',
        'quantity': 1,
        'type': 'CSP',
        'current_price': 185,
        'days_to_expiration': 3,
    }
    impact = calculate_gap_risk_impact(test_pos)
    print(f"Position: {test_pos['symbol']} {test_pos['type']}")
    for scenario in impact['gap_scenarios']:
        print(f"  Gap +{scenario['gap_pct']}%: Loss ${scenario['estimated_loss']}")
    
    print("\n=== Test: Mitigation Recommendations ===")
    mitigate = recommend_gap_mitigation(test_pos)
    print(f"Risk Level: {mitigate['risk_level'].upper()}")
    print(f"Priority: {mitigate['priority']}")
    for rec in mitigate['recommendations']:
        print(f"  • {rec}")
