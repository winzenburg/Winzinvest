#!/usr/bin/env python3
"""
Test IB Gateway connection — uses IB_PORT / IB_HOST from trading/.env
"""
import os
import sys
from pathlib import Path
from ib_insync import IB, util

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
TRADING_MODE = os.getenv("TRADING_MODE", "live")


def test_connection():
    ib = IB()

    print("Attempting to connect to IB Gateway...")
    print(f"Host: {IB_HOST}")
    print(f"Port: {IB_PORT} ({TRADING_MODE} trading)")
    print("Client ID: 101")
    print()

    try:
        ib.connect(IB_HOST, IB_PORT, clientId=101, timeout=10)
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
        print(f"1. Is IB Gateway running?")
        print(f"2. Are you logged into {TRADING_MODE.upper()} account?")
        print("3. Is API enabled in IB Gateway settings?")
        print(f"4. Is Socket Port set to {IB_PORT}?")
        print("5. Is 'Enable ActiveX and Socket Clients' checked?")
        return False

if __name__ == '__main__':
    sys.exit(0 if test_connection() else 1)
