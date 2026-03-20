#!/usr/bin/env python3
"""
Close Final 2 REM Positions via IB Gateway API
- REM Long: SELL 5 shares @ market
- REM Short: BUY 5 shares @ market (close short)
"""
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from ib_insync import IB, Order, Contract, util

from env_loader import load_env as _load_env_fn
_load_env_fn()
_env_path = Path(__file__).resolve().parent.parent / ".env"  # kept for kill-switch path

# Configuration
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 101

# Position details
POSITIONS_TO_CLOSE = [
    {'symbol': 'REM', 'qty': 5, 'side': 'SELL', 'entry_price': 22.67},
    {'symbol': 'REM', 'qty': 5, 'side': 'BUY', 'entry_price': 22.67}
]


def create_market_order(qty: int, action: str) -> Order:
    """Create a market order"""
    order = Order()
    order.action = action  # 'BUY' or 'SELL'
    order.orderType = 'MKT'
    order.totalQuantity = qty
    order.timeInForce = 'DAY'
    return order


def create_rem_contract() -> Contract:
    """Create REM contract"""
    contract = Contract()
    contract.symbol = 'REM'
    contract.secType = 'STK'
    contract.exchange = 'SMART'
    contract.currency = 'USD'
    return contract


def _kill_switch_active() -> bool:
    """Return True (fail-closed) if kill switch is active or unreadable."""
    ks_path = _env_path.parent / "kill_switch.json"
    try:
        if not ks_path.exists():
            return False
        data = json.loads(ks_path.read_text())
        return bool(data.get("active"))
    except Exception:
        return True  # fail closed


def close_positions():
    """Main function to close positions"""
    if _kill_switch_active():
        print("❌ Kill switch is ACTIVE — close_rem_positions aborted. Deactivate manually first.")
        return {
            'status': 'aborted',
            'timestamp': datetime.now().isoformat(),
            'positions_closed': 0,
            'execution_results': [],
            'total_realized_pnl': 0.0,
            'errors': ['kill switch active'],
        }

    ib = IB()
    results = {
        'status': 'failed',
        'timestamp': datetime.now().isoformat(),
        'positions_closed': 0,
        'execution_results': [],
        'total_realized_pnl': 0.0,
        'errors': []
    }
    
    try:
        # Connect to IB Gateway
        print(f"🔌 Connecting to IB Gateway at {IB_HOST}:{IB_PORT}...")
        ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, timeout=10)
        time.sleep(1)
        print("✅ Connected successfully!")
        
        # Get account info
        account = ib.managedAccounts()[0]
        print(f"📊 Account: {account}")
        
        # Create REM contract
        rem_contract = create_rem_contract()
        
        # Place orders for each position
        orders_placed = []
        for position_info in POSITIONS_TO_CLOSE:
            symbol = position_info['symbol']
            qty = position_info['qty']
            side = position_info['side']
            entry_price = position_info['entry_price']
            
            print(f"\n📌 Placing {side} order for {qty} shares of {symbol}...")
            
            # Create and place order
            order = create_market_order(qty, side)
            trade = ib.placeOrder(rem_contract, order)
            orders_placed.append({
                'trade': trade,
                'side': side,
                'qty': qty,
                'entry_price': entry_price
            })
            
            print(f"   Order ID: {trade.order.orderId}")
            print(f"   Status: {trade.orderStatus.status}")
        
        # Wait for all orders to fill (with timeout)
        print("\n⏳ Waiting for order execution...")
        max_wait = 30  # seconds
        wait_start = time.time()
        
        while time.time() - wait_start < max_wait:
            all_filled = True
            for order_info in orders_placed:
                trade = order_info['trade']
                if trade.orderStatus.status not in ['Filled', 'Cancelled']:
                    all_filled = False
                    break
            
            if all_filled:
                break
            
            ib.sleep(0.5)
        
        # Process execution results
        total_pnl = 0.0
        for order_info in orders_placed:
            trade = order_info['trade']
            side = order_info['side']
            qty = order_info['qty']
            entry_price = order_info['entry_price']
            
            if trade.orderStatus.status == 'Filled':
                # Get execution price from filled order
                fills = trade.fills
                if fills:
                    # Average price of all fills
                    total_fill_qty = sum(fill.execution.shares for fill in fills)
                    avg_price = sum(fill.execution.price * fill.execution.shares for fill in fills) / total_fill_qty
                    
                    # Calculate P&L
                    # For SELL: entry is cost basis, executed price is sale price
                    # For BUY (closing short): entry price is short price, executed is buyback price
                    if side == 'SELL':
                        # Long position close: profit = (sale_price - entry_price) * qty
                        pnl = (avg_price - entry_price) * qty
                    else:  # BUY (closing short)
                        # Short position close: profit = (entry_price - purchase_price) * qty
                        pnl = (entry_price - avg_price) * qty
                    
                    total_pnl += pnl
                    
                    execution_result = {
                        'symbol': 'REM',
                        'qty': qty,
                        'side': side,
                        'entry_price': entry_price,
                        'close_price': avg_price,
                        'pnl': round(pnl, 2)
                    }
                    
                    results['execution_results'].append(execution_result)
                    results['positions_closed'] += 1
                    
                    print(f"✅ {side} {qty} REM @ ${avg_price:.2f}")
                    print(f"   Entry: ${entry_price:.2f} | Close: ${avg_price:.2f} | P&L: ${pnl:.2f}")
                    
            else:
                error_msg = f"Order {trade.order.orderId} not filled: {trade.orderStatus.status}"
                results['errors'].append(error_msg)
                print(f"❌ {error_msg}")
        
        # Final results
        results['total_realized_pnl'] = round(total_pnl, 2)
        
        if results['positions_closed'] == 2:
            results['status'] = 'completed'
            print(f"\n✅ SUCCESS: All 2 positions closed!")
            print(f"💰 Total Realized P&L: ${total_pnl:.2f}")
        else:
            print(f"\n⚠️  PARTIAL: {results['positions_closed']}/2 positions closed")
        
    except Exception as e:
        error_msg = f"Exception: {str(e)}"
        results['errors'].append(error_msg)
        print(f"❌ Error: {e}")
    finally:
        try:
            ib.disconnect()
        except Exception:
            pass
    
    return results


if __name__ == '__main__':
    # Run main
    results = close_positions()
    
    # Print JSON result
    print("\n" + "="*70)
    print("EXECUTION RESULT:")
    print("="*70)
    print(json.dumps(results, indent=2))
    
    # Exit with success if completed
    sys.exit(0 if results['status'] == 'completed' else 1)
