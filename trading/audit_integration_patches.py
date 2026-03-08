#!/usr/bin/env python3
"""
Audit Logger Integration Patches
Provides ready-to-use patches for integrating audit logging into existing modules
Each patch shows the exact code to add
"""

import logging

logger = logging.getLogger(__name__)

# =====================================================================
# PATCH 1: stop_manager.py
# =====================================================================
STOP_MANAGER_PATCH = """
# Add to imports at top of stop_manager.py:
from audit_logger import log_stop_placed, log_stop_filled, log_error

# In place_stop() method, after logger.info for placed order:
            # Log the stop placement to audit trail
            try:
                log_stop_placed(
                    symbol=symbol,
                    stop_price=stop_price,
                    order_id=trade.order.orderId,
                    entry_price=entry_price,
                    quantity=quantity,
                    risk_pct=applied_risk_pct,
                    sector=sector or 'default'
                )
            except Exception as audit_error:
                logger.warning(f"⚠️  Failed to log stop placement: {audit_error}")

# In monitor_stops() method, when checking if stop is filled:
                    if trade.orderStatus.status == 'Filled':
                        # Log the stop fill
                        try:
                            log_stop_filled(
                                symbol=order_data['symbol'],
                                fill_price=trade.execution.price,
                                slippage=trade.execution.price - order_data['stop_price'],
                                pnl=realized_pnl,
                                order_id=order_id
                            )
                        except Exception as audit_error:
                            logger.warning(f"⚠️  Failed to log stop fill: {audit_error}")
"""

# =====================================================================
# PATCH 2: webhook_listener.py
# =====================================================================
WEBHOOK_LISTENER_PATCH = """
# Add to imports at top of webhook_listener.py:
from audit_logger import log_webhook_alert, log_entry_signal, log_error

# In the webhook handler function, when processing a signal:
    # Log the webhook alert
    try:
        log_webhook_alert(
            signal_type=signal.get('type', 'unknown'),
            symbol=signal.get('symbol'),
            price=signal.get('price'),
            action=signal.get('action')
        )
    except Exception as audit_error:
        logger.warning(f"⚠️  Failed to log webhook alert: {audit_error}")

# When an entry signal is triggered from webhook:
    # Log the entry signal
    try:
        log_entry_signal(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            reason=f"webhook_alert_{signal_type}",
            signal_type=signal_type,
            confidence=signal.get('confidence', 0)
        )
    except Exception as audit_error:
        logger.warning(f"⚠️  Failed to log entry signal: {audit_error}")
"""

# =====================================================================
# PATCH 3: circuit_breaker.py
# =====================================================================
CIRCUIT_BREAKER_PATCH = """
# Add to imports at top of circuit_breaker.py:
from audit_logger import log_circuit_breaker

# In the method where regime changes are detected:
    def update_regime(self, new_regime: str, vix_level: float):
        \"\"\"Update the current regime and log the change\"\"\"
        if new_regime != self.current_regime:
            old_regime = self.current_regime
            self.current_regime = new_regime
            
            # Log the circuit breaker event
            try:
                config = self.circuit_breaker_config.get(new_regime, {})
                log_circuit_breaker(
                    vix_level=vix_level,
                    regime_change=f"{old_regime}→{new_regime}",
                    action='regime_change',
                    position_size_mult=config.get('position_size_mult'),
                    stop_percent=config.get('stop_percent'),
                    allow_entries=config.get('allow_entries')
                )
            except Exception as audit_error:
                logger.warning(f"⚠️  Failed to log circuit breaker: {audit_error}")
"""

# =====================================================================
# PATCH 4: gap_protector.py
# =====================================================================
GAP_PROTECTOR_PATCH = """
# Add to imports at top of gap_protector.py:
from audit_logger import log_gap_protection, log_position_closed

# When gap protection is triggered:
    # Log the gap protection event
    try:
        log_gap_protection(
            symbol=symbol,
            action='close_position',
            gap_size=gap_percent,
            gap_direction='down' if gap_percent < 0 else 'up',
            current_price=current_price,
            previous_close=previous_close
        )
    except Exception as audit_error:
        logger.warning(f"⚠️  Failed to log gap protection: {audit_error}")

# When the position is actually closed:
    # Log the position closure
    try:
        log_position_closed(
            symbol=symbol,
            exit_price=exit_price,
            reason='gap_protection',
            gap_percent=gap_percent,
            loss_amount=loss
        )
    except Exception as audit_error:
        logger.warning(f"⚠️  Failed to log position closure: {audit_error}")
"""

# =====================================================================
# PATCH 5: options_monitor.py
# =====================================================================
OPTIONS_MONITOR_PATCH = """
# Add to imports at top of options_monitor.py:
from audit_logger import log_options_decision

# When making an options trading decision:
    # Log the options decision
    try:
        log_options_decision(
            symbol=symbol,
            strike=strike_price,
            decision='buy_csp' if decision == 'sell' else 'sell_call',
            reason=reasoning,
            iv_rank=current_iv_rank,
            delta=option_delta,
            theta=option_theta,
            expiration_days=dte
        )
    except Exception as audit_error:
        logger.warning(f"⚠️  Failed to log options decision: {audit_error}")
"""

# =====================================================================
# PATCH 6: screener.py
# =====================================================================
SCREENER_PATCH = """
# Add to imports at top of screener.py:
from audit_logger import log_screener_run

# At the end of screener run, before returning results:
    # Log the screener run
    try:
        log_screener_run(
            candidates_found=len(results),
            symbols=list(results.keys()) if results else [],
            filters_passed={
                'price_filter': price_count,
                'volume_filter': volume_count,
                'trend_filter': trend_count,
                'liquidity_filter': liquidity_count,
            }
        )
    except Exception as audit_error:
        logger.warning(f"⚠️  Failed to log screener run: {audit_error}")
    
    return results
"""

# =====================================================================
# PATCH 7: Universal Error Logging
# =====================================================================
UNIVERSAL_ERROR_PATCH = """
# Add to imports in any module:
from audit_logger import log_error

# Wrap exception handling to log errors:
    try:
        # your code here
        pass
    except Exception as e:
        # Log the error to audit trail
        try:
            log_error(
                error_type=type(e).__name__,
                component='module_name',
                message=str(e),
                traceback=traceback.format_exc()
            )
        except:
            pass  # If audit logging fails, at least try to continue
        
        # Then handle as normal
        logger.error(f"Error: {e}")
"""

# =====================================================================
# APPLICATION FUNCTIONS
# =====================================================================

def apply_stop_manager_integration():
    """Apply audit logging integration to stop_manager.py"""
    logger.info("📄 Integration patch for stop_manager.py:")
    print(STOP_MANAGER_PATCH)
    return STOP_MANAGER_PATCH


def apply_webhook_listener_integration():
    """Apply audit logging integration to webhook_listener.py"""
    logger.info("📄 Integration patch for webhook_listener.py:")
    print(WEBHOOK_LISTENER_PATCH)
    return WEBHOOK_LISTENER_PATCH


def apply_circuit_breaker_integration():
    """Apply audit logging integration to circuit_breaker.py"""
    logger.info("📄 Integration patch for circuit_breaker.py:")
    print(CIRCUIT_BREAKER_PATCH)
    return CIRCUIT_BREAKER_PATCH


def apply_gap_protector_integration():
    """Apply audit logging integration to gap_protector.py"""
    logger.info("📄 Integration patch for gap_protector.py:")
    print(GAP_PROTECTOR_PATCH)
    return GAP_PROTECTOR_PATCH


def apply_options_monitor_integration():
    """Apply audit logging integration to options_monitor.py"""
    logger.info("📄 Integration patch for options_monitor.py:")
    print(OPTIONS_MONITOR_PATCH)
    return OPTIONS_MONITOR_PATCH


def apply_screener_integration():
    """Apply audit logging integration to screener.py"""
    logger.info("📄 Integration patch for screener.py:")
    print(SCREENER_PATCH)
    return SCREENER_PATCH


def apply_error_logging_integration():
    """Apply universal error logging integration"""
    logger.info("📄 Universal error logging patch:")
    print(UNIVERSAL_ERROR_PATCH)
    return UNIVERSAL_ERROR_PATCH


def print_all_patches():
    """Print all integration patches"""
    print("\n" + "="*70)
    print("AUDIT LOGGING INTEGRATION PATCHES")
    print("="*70)
    
    patches = [
        ("stop_manager.py", STOP_MANAGER_PATCH),
        ("webhook_listener.py", WEBHOOK_LISTENER_PATCH),
        ("circuit_breaker.py", CIRCUIT_BREAKER_PATCH),
        ("gap_protector.py", GAP_PROTECTOR_PATCH),
        ("options_monitor.py", OPTIONS_MONITOR_PATCH),
        ("screener.py", SCREENER_PATCH),
        ("ALL MODULES - Error Logging", UNIVERSAL_ERROR_PATCH),
    ]
    
    for name, patch in patches:
        print(f"\n{'='*70}")
        print(f"FILE: {name}")
        print(f"{'='*70}")
        print(patch)
    
    print("\n" + "="*70)
    print("END OF PATCHES")
    print("="*70)


if __name__ == '__main__':
    print("🔧 Audit Logger Integration Patches\n")
    print_all_patches()
    print("\n✅ Patches ready for manual integration")
    print("See AUDIT_INTEGRATION_GUIDE.md for detailed instructions")
