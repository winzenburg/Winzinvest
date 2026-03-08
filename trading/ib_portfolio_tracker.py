#!/usr/bin/env python3
"""
Interactive Brokers Portfolio Tracker (Simplified)
Fetches open positions, P&L, and generates daily summary
Connects to TWS or IBGateway API
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict
import json
import os
from pathlib import Path

try:
    from ib_insync import IB, util
except ImportError:
    print("ERROR: ib_insync not installed. Run: pip install ib_insync")
    exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
IB_HOST = os.getenv('IB_HOST', '127.0.0.1')
IB_PORT = int(os.getenv('IB_PORT', 4002))
IB_ACCOUNT = os.getenv('IB_ACCOUNT', 'DU4661622')
PORTFOLIO_FILE = Path(os.path.expanduser('~/.openclaw/workspace/trading/portfolio.json'))


async def fetch_portfolio(ib: IB) -> Dict:
    """Fetch current portfolio data"""
    portfolio = {
        'timestamp': datetime.now().isoformat(),
        'account': IB_ACCOUNT,
        'positions': [],
        'summary': {
            'total_value': 0,
            'net_liquidation': 0,
            'cash': 0,
            'unrealized_p_l': 0
        }
    }

    try:
        # Collect positions from the updatePortfolio events
        positions_list = ib.portfolio()
        
        for position in positions_list:
            if position.account == IB_ACCOUNT:
                pos_dict = {
                    'symbol': position.contract.symbol,
                    'exchange': position.contract.exchange,
                    'currency': position.contract.currency,
                    'quantity': position.position,
                    'avg_cost': position.averageCost,
                    'market_price': position.marketPrice,
                    'market_value': position.marketValue,
                    'unrealized_p_l': position.unrealizedPNL,
                    'unrealized_p_l_pct': (position.unrealizedPNL / position.marketValue * 100) if position.marketValue != 0 else 0
                }
                
                portfolio['positions'].append(pos_dict)
                portfolio['summary']['unrealized_p_l'] += position.unrealizedPNL
                portfolio['summary']['total_value'] += position.marketValue

        logger.info(f"✅ Fetched {len(portfolio['positions'])} positions")
        
    except Exception as e:
        logger.error(f"❌ Error fetching portfolio: {e}")
        raise

    return portfolio


def format_portfolio_report(portfolio: Dict) -> str:
    """Format portfolio data as readable report"""
    summary = portfolio['summary']
    positions = portfolio['positions']

    report = f"""
╔══════════════════════════════════════════════════════════════╗
║               PORTFOLIO SUMMARY - {portfolio['timestamp'][:10]}
╚══════════════════════════════════════════════════════════════╝

Account: {portfolio['account']}
Total Position Value: ${summary['total_value']:,.2f}
Unrealized P&L: ${summary['unrealized_p_l']:,.2f}

═══════════════════════════════════════════════════════════════

OPEN POSITIONS ({len(positions)} stocks):
"""

    if positions:
        # Header
        report += f"\n{'Symbol':<10} {'Qty':<8} {'Avg Cost':<12} {'Market':<12} {'Market Val':<15} {'U/R P&L':<15} {'%':<8}"
        report += "\n" + "─" * 90

        # Positions (sorted by market value, largest first)
        for pos in sorted(positions, key=lambda x: abs(x['market_value']), reverse=True):
            pnl_indicator = "🟢" if pos['unrealized_p_l'] >= 0 else "🔴"
            report += f"\n{pos['symbol']:<10} {pos['quantity']:<8.0f} ${pos['avg_cost']:<11.2f} ${pos['market_price']:<11.2f} ${pos['market_value']:<14,.2f} {pnl_indicator} ${pos['unrealized_p_l']:<14,.2f} {pos['unrealized_p_l_pct']:<7.2f}%"

        report += f"\n" + "─" * 90
        report += f"\nTOTAL UNREALIZED P&L: ${summary['unrealized_p_l']:,.2f}\n"
    else:
        report += "\nNo open positions.\n"

    report += "\n═══════════════════════════════════════════════════════════════\n"

    return report


async def save_portfolio(portfolio: Dict):
    """Save portfolio data to JSON file"""
    try:
        # Create directory if needed
        PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(portfolio, f, indent=2)
        
        logger.info(f"✅ Portfolio saved to {PORTFOLIO_FILE}")
    except Exception as e:
        logger.error(f"❌ Error saving portfolio: {e}")


async def main():
    """Main execution"""
    logger.info("Starting IB Portfolio Tracker...")
    
    ib = IB()
    try:
        # Connect to IB
        await ib.connectAsync(IB_HOST, IB_PORT, clientId=1)
        logger.info(f"✅ Connected to IB at {IB_HOST}:{IB_PORT}")
        
        # Wait for sync
        await asyncio.sleep(1)
        
        # Fetch portfolio
        portfolio = await fetch_portfolio(ib)
        
        # Format and print report
        report = format_portfolio_report(portfolio)
        print(report)
        
        # Save portfolio
        await save_portfolio(portfolio)
        
        logger.info("✅ Portfolio update complete")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        exit(1)
    finally:
        ib.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
