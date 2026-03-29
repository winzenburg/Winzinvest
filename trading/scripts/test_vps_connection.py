#!/usr/bin/env python3
"""Quick test script to verify IB Gateway connection from VPS"""

from ib_insync import IB
import sys

ib = IB()
try:
    print("Attempting to connect to IB Gateway on localhost:4001...")
    ib.connect('127.0.0.1', 4001, clientId=999, timeout=10)
    
    accounts = ib.managedAccounts()
    print(f'✅ IB Gateway API Connected!')
    print(f'Accounts: {accounts}')
    
    positions = ib.positions()
    print(f'Open positions: {len(positions)}')
    
    if positions:
        print(f'\nFirst 5 positions:')
        for p in positions[:5]:
            print(f'  - {p.contract.symbol}: {p.position} @ ${p.avgCost:.2f}')
    
    # Test getting account summary
    account_values = ib.accountSummary()
    nlv = next((v.value for v in account_values if v.tag == 'NetLiquidation'), 'N/A')
    print(f'\nNet Liquidation Value: ${nlv}')
    
    ib.disconnect()
    print(f'\n✅ Connection test SUCCESSFUL!')
    sys.exit(0)
    
except Exception as e:
    print(f'❌ Connection failed: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
