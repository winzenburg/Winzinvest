#!/usr/bin/env python3
"""
Dynamic Position Sizing Manager
Adjusts position sizes based on:
1. Earnings calendar (±7 days = 50% size)
2. VIX level (high volatility = smaller size)
3. Account drawdown (larger drawdowns = smaller size)
"""

import yfinance as yf
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Base position size (0.5% of account = $9,685 on $1.94M)
BASE_POSITION_SIZE = 0.005

# VIX thresholds for position sizing
VIX_THRESHOLDS = {
    'extreme': 30,   # VIX > 30: 25% size
    'high': 25,      # VIX 25-30: 50% size
    'elevated': 20,  # VIX 20-25: 75% size
    'normal': 0,     # VIX < 20: 100% size
}

def get_vix_level() -> dict:
    """
    Fetch current VIX level.
    
    Returns: {
        'vix': float,
        'timestamp': str,
        'category': 'extreme' | 'high' | 'elevated' | 'normal',
        'error': str or None,
    }
    """
    try:
        vix = yf.Ticker('^VIX')
        hist = vix.history(period='1d')
        if hist.empty:
            return {'vix': None, 'error': 'No VIX data', 'category': 'unknown'}
        
        current_vix = float(hist['Close'].iloc[-1])
        
        # Categorize
        if current_vix > VIX_THRESHOLDS['extreme']:
            category = 'extreme'
        elif current_vix > VIX_THRESHOLDS['high']:
            category = 'high'
        elif current_vix > VIX_THRESHOLDS['elevated']:
            category = 'elevated'
        else:
            category = 'normal'
        
        return {
            'vix': round(current_vix, 2),
            'timestamp': datetime.now().isoformat(),
            'category': category,
            'error': None,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch VIX: {e}")
        return {
            'vix': None,
            'error': str(e),
            'category': 'unknown',
        }

def get_vix_multiplier(vix: float = None) -> dict:
    """
    Calculate position size multiplier based on VIX level.
    
    Args:
        vix: VIX level (if None, fetches current)
    
    Returns: {
        'vix': float,
        'category': str,
        'multiplier': float (0.25 to 1.0),
        'position_size_pct': float,
    }
    """
    if vix is None:
        vix_data = get_vix_level()
        if vix_data['error']:
            # Default to normal if can't fetch
            return {
                'vix': None,
                'category': 'unknown',
                'multiplier': 1.0,
                'position_size_pct': BASE_POSITION_SIZE * 100,
                'note': 'Using default (no VIX data)',
            }
        vix = vix_data['vix']
    
    # Calculate multiplier based on VIX
    if vix > VIX_THRESHOLDS['extreme']:
        multiplier = 0.25  # 25% of normal
        category = 'extreme'
    elif vix > VIX_THRESHOLDS['high']:
        multiplier = 0.50  # 50% of normal
        category = 'high'
    elif vix > VIX_THRESHOLDS['elevated']:
        multiplier = 0.75  # 75% of normal
        category = 'elevated'
    else:
        multiplier = 1.0  # 100% of normal
        category = 'normal'
    
    return {
        'vix': vix,
        'category': category,
        'multiplier': multiplier,
        'position_size_pct': (BASE_POSITION_SIZE * multiplier) * 100,
    }

def get_earnings_multiplier(symbol: str, days_until_earnings: int = None) -> dict:
    """
    Calculate position size multiplier based on earnings proximity.
    
    Args:
        symbol: Stock symbol
        days_until_earnings: Days until earnings (if None, assume safe)
    
    Returns: {
        'symbol': str,
        'days_until_earnings': int,
        'multiplier': float (0.5 to 1.0),
        'phase': 'pre' | 'earnings' | 'post' | 'safe',
        'position_size_pct': float,
    }
    """
    if days_until_earnings is None:
        # Safe default (not in earnings window)
        return {
            'symbol': symbol,
            'days_until_earnings': None,
            'multiplier': 1.0,
            'phase': 'safe',
            'position_size_pct': BASE_POSITION_SIZE * 100,
        }
    
    # Earnings window: ±7 days
    if -7 <= days_until_earnings <= 7:
        multiplier = 0.5  # 50% size
        if days_until_earnings == 0:
            phase = 'earnings'
        elif days_until_earnings > 0:
            phase = 'pre'
        else:
            phase = 'post'
    else:
        multiplier = 1.0  # 100% size
        phase = 'safe'
    
    return {
        'symbol': symbol,
        'days_until_earnings': days_until_earnings,
        'multiplier': multiplier,
        'phase': phase,
        'position_size_pct': (BASE_POSITION_SIZE * multiplier) * 100,
    }

def get_drawdown_multiplier(account_value: float, peak_value: float = None) -> dict:
    """
    Calculate position size multiplier based on account drawdown.
    
    Args:
        account_value: Current account value
        peak_value: Peak account value (if None, uses current as peak)
    
    Returns: {
        'current_value': float,
        'peak_value': float,
        'drawdown_pct': float,
        'multiplier': float (0.5 to 1.0),
        'position_size_pct': float,
    }
    """
    if peak_value is None:
        peak_value = account_value
    
    if peak_value == 0:
        multiplier = 1.0
        drawdown_pct = 0
    else:
        drawdown_pct = ((peak_value - account_value) / peak_value) * 100
        
        # Scaling: 10% drawdown = 100% size, 5% = 100%, 0% = 100%
        # Below 5%: reduce to 50% at 10% drawdown
        if drawdown_pct >= 10:
            multiplier = 0.5  # Hard stop at 10% drawdown
        elif drawdown_pct >= 5:
            # Linear interpolation: 5% = 100%, 10% = 50%
            multiplier = 1.0 - (drawdown_pct - 5) * 0.1
        else:
            multiplier = 1.0
    
    return {
        'current_value': account_value,
        'peak_value': peak_value,
        'drawdown_pct': round(drawdown_pct, 2),
        'multiplier': round(multiplier, 2),
        'position_size_pct': (BASE_POSITION_SIZE * multiplier) * 100,
    }

def calculate_composite_position_size(
    symbol: str,
    account_value: float,
    vix: float = None,
    days_until_earnings: int = None,
    peak_value: float = None
) -> dict:
    """
    Calculate final position size using ALL factors (VIX + earnings + drawdown).
    
    Returns: {
        'symbol': str,
        'base_position_size': float,
        'vix_multiplier': float,
        'earnings_multiplier': float,
        'drawdown_multiplier': float,
        'composite_multiplier': float,
        'final_position_size_pct': float,
        'final_position_size_dollars': float,
        'factors': dict with details,
    }
    """
    # Get each multiplier
    vix_mult = get_vix_multiplier(vix)['multiplier']
    earnings_mult = get_earnings_multiplier(symbol, days_until_earnings)['multiplier']
    drawdown_mult = get_drawdown_multiplier(account_value, peak_value)['multiplier']
    
    # Composite = multiply all factors
    composite = vix_mult * earnings_mult * drawdown_mult
    
    final_pct = BASE_POSITION_SIZE * composite
    final_dollars = account_value * final_pct
    
    return {
        'symbol': symbol,
        'account_value': account_value,
        'base_position_size': BASE_POSITION_SIZE,
        'vix_multiplier': round(vix_mult, 2),
        'earnings_multiplier': round(earnings_mult, 2),
        'drawdown_multiplier': round(drawdown_mult, 2),
        'composite_multiplier': round(composite, 3),
        'final_position_size_pct': round(final_pct * 100, 3),
        'final_position_size_dollars': round(final_dollars, 2),
        'factors': {
            'vix': vix,
            'days_until_earnings': days_until_earnings,
            'drawdown_pct': ((peak_value - account_value) / peak_value * 100 if peak_value else 0),
        },
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n=== Test: VIX Multiplier ===")
    for vix_level in [15, 20, 25, 30, 35]:
        mult = get_vix_multiplier(vix_level)
        print(f"VIX {vix_level}: {mult['category']:10} → {mult['multiplier']:.1%} size (${mult['position_size_pct']:.3f}% of $1.94M = ${1940000 * mult['position_size_pct']/100:.0f})")
    
    print("\n=== Test: Earnings Multiplier ===")
    for days in [-8, -5, 0, 5, 8, 15]:
        mult = get_earnings_multiplier('AAPL', days)
        status = f"{days:+3} days ({mult['phase']:8})"
        print(f"{status}: {mult['multiplier']:.1%} size (${mult['position_size_pct']:.3f}%)")
    
    print("\n=== Test: Drawdown Multiplier ===")
    account = 1940000
    for dd in [0, 3, 5, 7, 10, 15]:
        peak = account / (1 - dd/100)
        mult = get_drawdown_multiplier(account, peak)
        print(f"Drawdown {dd:2}%: {mult['multiplier']:.1%} size (${mult['position_size_pct']:.3f}%)")
    
    print("\n=== Test: Composite Sizing ===")
    composite = calculate_composite_position_size(
        symbol='AAPL',
        account_value=1940000,
        vix=25,
        days_until_earnings=3,
        peak_value=1940000
    )
    print(f"Symbol: {composite['symbol']}")
    print(f"Base: 0.5% (${9685:.0f})")
    print(f"VIX 25 (high): ×{composite['vix_multiplier']}")
    print(f"Earnings +3d: ×{composite['earnings_multiplier']}")
    print(f"Drawdown: ×{composite['drawdown_multiplier']}")
    print(f"→ Final: {composite['composite_multiplier']:.1%} = {composite['final_position_size_pct']:.3f}% (${composite['final_position_size_dollars']:.0f})")
