#!/usr/bin/env python3
"""
Test IB Gateway connection
"""
import sys
from ib_insync import IB, util

def test_connection():
    ib = IB()
    
    print("Attempting to connect to IB Gateway...")
    print("Host: 127.0.0.1")
    print("Port: 4002 (paper trading)")
    print("Client ID: 101")
    print()
    
    try:
        ib.connect('127.0.0.1', 4002, clientId=101, timeout=10)
        print("✅ Connected successfully!")
        print()
        
        # Get account info
        print("Account Summary:")
        account = ib.managedAccounts()[0]
        print(f"  Account: {account}")
        
        # Get account values
        account_values = ib.accountSummary(account)
        for av in account_values:
            if av.tag in ['TotalCashValue', 'NetLiquidation', 'BuyingPower']:
                print(f"  {av.tag}: ${float(av.value):,.2f}")
        
        # Get positions
        positions = ib.positions()
        if positions:
            print(f"\nCurrent Positions: {len(positions)}")
            for pos in positions:
                print(f"  {pos.contract.symbol}: {pos.position} shares @ ${pos.avgCost:.2f}")
        else:
            print("\nNo current positions")
        
        ib.disconnect()
        print("\n✅ Connection test successful!")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Is IB Gateway running?")
        print("2. Are you logged into PAPER TRADING (not live)?")
        print("3. Is API enabled in IB Gateway settings?")
        print("4. Is Socket Port set to 4002?")
        print("5. Is 'Enable ActiveX and Socket Clients' checked?")
        return False

if __name__ == '__main__':
    sys.exit(0 if test_connection() else 1)
