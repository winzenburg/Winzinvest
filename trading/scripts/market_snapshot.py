#!/usr/bin/env python3
"""
Quick market snapshot for morning briefs
Pulls SPY, QQQ, and key indicators from TradingView
"""

from tradingview_ta import TA_Handler, Interval
import sys

def get_market_snapshot():
    """Get current market data for SPY and QQQ"""
    
    results = {
        'spy': None,
        'qqq': None,
        'error': None
    }
    
    try:
        # SPY (S&P 500)
        spy = TA_Handler(
            symbol="SPY",
            screener="america",
            exchange="AMEX",
            interval=Interval.INTERVAL_5_MINUTES
        )
        spy_data = spy.get_analysis()
        
        results['spy'] = {
            'price': spy_data.indicators['close'],
            'change': spy_data.indicators['change'],
            'change_pct': (spy_data.indicators['change'] / spy_data.indicators['close']) * 100,
            'volume': spy_data.indicators['volume'],
            'rsi': spy_data.indicators['RSI'],
            'recommendation': spy_data.summary['RECOMMENDATION']
        }
        
        # QQQ (Nasdaq 100)
        qqq = TA_Handler(
            symbol="QQQ",
            screener="america",
            exchange="NASDAQ",
            interval=Interval.INTERVAL_5_MINUTES
        )
        qqq_data = qqq.get_analysis()
        
        results['qqq'] = {
            'price': qqq_data.indicators['close'],
            'change': qqq_data.indicators['change'],
            'change_pct': (qqq_data.indicators['change'] / qqq_data.indicators['close']) * 100,
            'volume': qqq_data.indicators['volume'],
            'rsi': qqq_data.indicators['RSI'],
            'recommendation': qqq_data.summary['RECOMMENDATION']
        }
        
    except Exception as e:
        results['error'] = str(e)
    
    return results

if __name__ == "__main__":
    data = get_market_snapshot()
    
    if data['error']:
        print(f"Error: {data['error']}")
        sys.exit(1)
    
    # Print formatted output
    print("📈 MARKET SNAPSHOT")
    print()
    
    if data['spy']:
        spy = data['spy']
        print(f"SPY: ${spy['price']:.2f} ({spy['change']:+.2f} / {spy['change_pct']:+.2f}%)")
        print(f"  RSI: {spy['rsi']:.1f} | Signal: {spy['recommendation']}")
    
    if data['qqq']:
        qqq = data['qqq']
        print(f"QQQ: ${qqq['price']:.2f} ({qqq['change']:+.2f} / {qqq['change_pct']:+.2f}%)")
        print(f"  RSI: {qqq['rsi']:.1f} | Signal: {qqq['recommendation']}")
