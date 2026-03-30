#!/usr/bin/env python3
"""
Quick helper to find your IBKR account ID(s).

Connects to IB Gateway/TWS and prints all managed accounts.
Use this to populate account_user_map.json.
"""

import asyncio
import os
import sys
from pathlib import Path

# Load env
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().split("\n"):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from ib_insync import IB


async def main():
    ib = IB()
    
    # Try all common ports
    host = os.getenv("IB_HOST", "127.0.0.1")
    ports = [
        int(os.getenv("IB_PORT", "4001")),
        4001,  # Gateway live
        4002,  # Gateway paper
        7496,  # TWS live
        7497,  # TWS paper
    ]
    
    connected = False
    for port in ports:
        try:
            print(f"Trying {host}:{port}...", end=" ")
            await ib.connectAsync(host, port, clientId=999, timeout=10)
            print("✓ Connected")
            connected = True
            break
        except Exception as e:
            print(f"✗ {type(e).__name__}")
    
    if not connected:
        print("\n❌ Could not connect to IB Gateway or TWS")
        print("Make sure Gateway/TWS is running and API connections are enabled")
        return
    
    print(f"\n{'='*60}")
    print("IBKR ACCOUNT ID(S)")
    print('='*60)
    
    accounts = ib.managedAccounts()
    if not accounts:
        print("No accounts found")
    else:
        for acc in accounts:
            print(f"  {acc}")
            
            # Determine if paper or live
            if acc.startswith("DU"):
                acc_type = "Paper Trading"
            elif acc.startswith("U"):
                acc_type = "Live Trading"
            else:
                acc_type = "Unknown"
            
            print(f"    Type: {acc_type}")
    
    print(f"\n{'='*60}")
    print("NEXT STEPS")
    print('='*60)
    print("\n1. Copy the account ID above")
    print("2. Edit: trading/config/account_user_map.json")
    print("3. Add mapping:")
    print(f'   {{"{accounts[0] if accounts else "U1234567"}": "your-email@example.com"}}')
    print("\n4. Set DASHBOARD_API_TOKEN in trading/.env")
    print("5. Set INTERNAL_API_TOKEN in Vercel")
    print("\nSee trading/DASHBOARD_INTEGRATION_SETUP.md for full instructions.")
    
    ib.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
