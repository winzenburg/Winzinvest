#!/usr/bin/env python3
"""
Post screener results to Telegram/notification for manual trading review
"""
import json
import sys
from pathlib import Path
from datetime import datetime

def format_screener_results(results):
    """Format screener results for notification"""
    if not results:
        return "📭 No setups found in today's scan"
    
    msg = f"📊 **Market Scan - {datetime.now().strftime('%H:%M MT')}**\n\n"
    
    for i, result in enumerate(results[:10], 1):  # Top 10
        ticker = result.get('ticker', 'N/A')
        signal = result.get('signal', 'N/A').upper()
        price = result.get('price', 'N/A')
        setup = result.get('setup_type', 'N/A')
        rs_ratio = result.get('rs_ratio', 'N/A')
        volume_ratio = result.get('volume_ratio', 'N/A')
        
        msg += f"{i}. **{ticker}** - {signal} @ ${price}\n"
        msg += f"   Setup: {setup}\n"
        msg += f"   RS: {rs_ratio:.2f} | Vol: {volume_ratio:.1f}x\n\n"
    
    msg += f"\n📈 Total candidates: {len(results)}"
    return msg


def notify_user(message):
    """Send notification - print for now, Telegram later"""
    print(message)
    # TODO: Add Telegram notification when configured
    
    # Save to file for OpenClaw to pick up
    notify_file = Path(__file__).resolve().parents[1] / 'notifications' / f'scan_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
    notify_file.parent.mkdir(exist_ok=True)
    notify_file.write_text(message)
    print(f"\n💾 Saved to: {notify_file}")


if __name__ == '__main__':
    # Example usage
    sample_results = [
        {
            'ticker': 'AAPL',
            'signal': 'buy',
            'price': 175.50,
            'setup_type': 'swing_fast_9_13_50',
            'rs_ratio': 1.08,
            'volume_ratio': 1.5
        },
        {
            'ticker': 'MSFT',
            'signal': 'buy',
            'price': 420.30,
            'setup_type': 'trend_following',
            'rs_ratio': 1.12,
            'volume_ratio': 1.8
        }
    ]
    
    msg = format_screener_results(sample_results)
    notify_user(msg)
