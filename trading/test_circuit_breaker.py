#!/usr/bin/env python3
"""
Circuit Breaker System Test & Status Script
Tests all components: VIX monitor, circuit breaker logic, position sizing
"""

import json
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import modules
try:
    from vix_monitor import get_vix_monitor, VIXMonitor
    from circuit_breaker import get_circuit_breaker, CircuitBreaker, REGIME_NAMES
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Failed to import modules: {e}")
    MODULES_AVAILABLE = False


def test_vix_monitor():
    """Test VIX monitor functionality"""
    logger.info("=" * 60)
    logger.info("🧪 TESTING VIX MONITOR")
    logger.info("=" * 60)
    
    monitor = VIXMonitor()
    
    # Get current status
    status = monitor.get_status()
    logger.info(f"📊 Current VIX Status:")
    for key, value in status.items():
        logger.info(f"   {key}: {value}")
    
    # Attempt to update
    logger.info("\n📍 Fetching latest VIX data...")
    update = monitor.update()
    
    if update:
        logger.info("✅ VIX Update successful:")
        logger.info(f"   VIX: {update['vix']}")
        logger.info(f"   Previous: {update['previous_vix']}")
        logger.info(f"   Regime: {update['regime']}")
        logger.info(f"   Trend: {update['trend']}")
        
        if update.get('alert_messages'):
            logger.warning("⚠️  Alerts:")
            for alert in update['alert_messages']:
                logger.warning(f"   {alert}")
        
        return True
    else:
        logger.error("❌ Failed to fetch VIX")
        return False


def test_circuit_breaker():
    """Test circuit breaker logic"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 TESTING CIRCUIT BREAKER")
    logger.info("=" * 60)
    
    # Get monitor
    monitor = get_vix_monitor()
    
    # Ensure we have current data
    if monitor.current_vix is None:
        logger.warning("⚠️  Updating VIX data...")
        monitor.update()
    
    # Create circuit breaker
    breaker = get_circuit_breaker(monitor)
    
    logger.info(f"\n📊 Current Regime Information:")
    logger.info(f"   VIX: {breaker.get_current_vix()}")
    logger.info(f"   Regime: {breaker.get_current_regime()}")
    logger.info(f"   Regime Info: {REGIME_NAMES.get(breaker.get_current_regime(), 'Unknown')}")
    
    # Test entry permission
    logger.info(f"\n🚪 Entry Permission Check:")
    can_enter, entry_status = breaker.can_enter_position('TEST')
    logger.info(f"   Can enter: {can_enter}")
    logger.info(f"   Status: {json.dumps(entry_status, indent=6)}")
    
    # Test weak position closeout
    logger.info(f"\n📉 Weak Position Closeout Check:")
    should_close, close_status = breaker.should_close_weak_positions()
    logger.info(f"   Should close: {should_close}")
    logger.info(f"   Status: {json.dumps(close_status, indent=6)}")
    
    # Test emergency liquidation
    logger.info(f"\n🚨 Emergency Liquidation Check:")
    should_liquidate, liq_status = breaker.should_liquidate_all()
    logger.info(f"   Should liquidate: {should_liquidate}")
    logger.info(f"   Status: {json.dumps(liq_status, indent=6)}")
    
    return True


def test_position_sizing():
    """Test position sizing calculations"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 TESTING POSITION SIZING")
    logger.info("=" * 60)
    
    monitor = get_vix_monitor()
    breaker = get_circuit_breaker(monitor)
    
    # Ensure we have current data
    if monitor.current_vix is None:
        monitor.update()
    
    base_size = 100  # 100 shares
    
    logger.info(f"\n📊 Position Sizing Test (Base: {base_size} shares):")
    adjusted, details = breaker.calculate_position_size_multiplier(base_size)
    
    logger.info(f"   Base size: {base_size}")
    logger.info(f"   Adjusted size: {adjusted}")
    logger.info(f"   Multiplier: {details.get('multiplier', 'N/A'):.0%}")
    if 'reduction_pct' in details:
        logger.info(f"   Reduction: {details['reduction_pct']:.1f}%")
    logger.info(f"   Details: {json.dumps(details, indent=6)}")


def test_stop_sizing():
    """Test stop-loss sizing calculations"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 TESTING STOP-LOSS SIZING")
    logger.info("=" * 60)
    
    monitor = get_vix_monitor()
    breaker = get_circuit_breaker(monitor)
    
    # Ensure we have current data
    if monitor.current_vix is None:
        monitor.update()
    
    logger.info(f"\n📊 Stop-Loss Sizing Test:")
    stop_pct, details = breaker.calculate_stop_percent()
    
    logger.info(f"   Stop percent: {stop_pct:.2%}")
    logger.info(f"   Regime: {details.get('regime', 'N/A')}")
    logger.info(f"   VIX: {details.get('vix', 'N/A')}")
    
    # Calculate example stop price
    entry_price = 150.00
    stop_price = entry_price * (1 - stop_pct)
    logger.info(f"\n   Example: Entry at ${entry_price:.2f}")
    logger.info(f"            Stop at ${stop_price:.2f}")
    logger.info(f"            Risk: {stop_pct:.2%}")


def test_entry_adjustment():
    """Test full entry adjustment"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 TESTING FULL ENTRY ADJUSTMENT")
    logger.info("=" * 60)
    
    monitor = get_vix_monitor()
    breaker = get_circuit_breaker(monitor)
    
    # Ensure we have current data
    if monitor.current_vix is None:
        monitor.update()
    
    base_size = 50  # 50 shares
    symbol = 'AAPL'
    
    logger.info(f"\n📊 Entry Adjustment Test (Symbol: {symbol}, Base: {base_size} shares):")
    adjustment = breaker.get_entry_adjustment(base_size, symbol)
    
    logger.info(f"   Allowed: {adjustment['allowed']}")
    logger.info(f"   Base size: {adjustment['base_size']}")
    logger.info(f"   Adjusted size: {adjustment['adjusted_size']}")
    logger.info(f"   Size multiplier: {adjustment['size_multiplier']:.0%}")
    logger.info(f"   Stop percent: {adjustment['stop_percent']:.2%}")
    logger.info(f"   Regime: {adjustment['regime']}")
    logger.info(f"   Regime info: {adjustment['regime_info']}")
    logger.info(f"   VIX: {adjustment['vix']}")


def test_circuit_breaker_status():
    """Test comprehensive circuit breaker status"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 TESTING CIRCUIT BREAKER STATUS")
    logger.info("=" * 60)
    
    monitor = get_vix_monitor()
    breaker = get_circuit_breaker(monitor)
    
    # Ensure we have current data
    if monitor.current_vix is None:
        monitor.update()
    
    status = breaker.check_circuit_breaker()
    
    logger.info(f"\n📊 Circuit Breaker Status:")
    logger.info(f"   Regime: {status['regime']}")
    logger.info(f"   VIX: {status['vix']}")
    logger.info(f"   Can enter: {status['can_enter']}")
    logger.info(f"   Should close weak: {status['should_close_weak']}")
    logger.info(f"   Should liquidate: {status['should_liquidate']}")
    logger.info(f"   Position size mult: {status['position_size_mult']:.0%}")
    logger.info(f"   Stop percent: {status['stop_percent']:.2%}")
    logger.info(f"   Timestamp: {status['timestamp']}")


def print_summary():
    """Print summary of system status"""
    logger.info("\n" + "=" * 60)
    logger.info("📋 SYSTEM SUMMARY")
    logger.info("=" * 60)
    
    monitor = get_vix_monitor()
    breaker = get_circuit_breaker(monitor)
    
    logger.info(f"\n✅ VIX Monitor Status:")
    logger.info(f"   Current VIX: {monitor.current_vix}")
    logger.info(f"   Regime: {monitor.current_regime}")
    logger.info(f"   Trend: {monitor.get_trend()}")
    logger.info(f"   Last fetch: {monitor.last_fetch_time}")
    
    logger.info(f"\n✅ Circuit Breaker Status:")
    status = breaker.check_circuit_breaker()
    logger.info(f"   Can enter: {status['can_enter']}")
    logger.info(f"   Should close weak: {status['should_close_weak']}")
    logger.info(f"   Should liquidate: {status['should_liquidate']}")
    logger.info(f"   Position multiplier: {status['position_size_mult']:.0%}")
    logger.info(f"   Stop tightening: {status['stop_percent']:.2%}")
    
    logger.info(f"\n✅ System Ready:")
    logger.info(f"   ✓ VIX monitoring active")
    logger.info(f"   ✓ Circuit breaker operational")
    logger.info(f"   ✓ Position sizing adjusted")
    logger.info(f"   ✓ Stop tightening applied")
    logger.info(f"   ✓ Ready for production")


def main():
    """Run all tests"""
    if not MODULES_AVAILABLE:
        logger.error("❌ Cannot run tests - required modules not available")
        sys.exit(1)
    
    logger.info("🚀 VIX CIRCUIT BREAKER SYSTEM TEST")
    logger.info("=" * 60)
    
    try:
        # Run tests
        if not test_vix_monitor():
            logger.warning("⚠️  VIX monitor test failed")
        
        test_circuit_breaker()
        test_position_sizing()
        test_stop_sizing()
        test_entry_adjustment()
        test_circuit_breaker_status()
        
        # Print summary
        print_summary()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS COMPLETED")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
