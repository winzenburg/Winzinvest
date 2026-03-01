#!/usr/bin/env python3
"""
Integration module for options_assignment_manager with options_monitor
Patches options_monitor to check assignment risk before approving trades
Provides webhook-compatible functions for approval flow
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import os

from options_assignment_manager import OptionsAssignmentManager

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
TRADING_DIR = Path(__file__).resolve().parents[0]
PENDING_DIR = TRADING_DIR / 'pending'
LOGS_DIR = TRADING_DIR / 'logs'
APPROVED_ASSIGNMENTS_LOG = LOGS_DIR / 'approved_options_with_assignments.json'

PENDING_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class OptionsApprovalWithAssignmentCheck:
    """Enhanced approval workflow with assignment risk checking"""
    
    def __init__(self):
        self.manager = OptionsAssignmentManager()
    
    def check_before_approval(self, intent_data: Dict) -> Dict:
        """
        Check assignment risk before approving an options trade
        Called in the approval workflow
        
        Args:
            intent_data: {
                'ticker': str,
                'action': 'SELL',
                'option_type': 'call' or 'put',
                'strike': float,
                'dte': int,
                'quantity': int,
                ...other fields
            }
        
        Returns: {
            'can_approve': bool,
            'assignment_check': Dict,
            'recommendation': str,
            'blocking_issues': List[str],
            'warnings': List[str]
        }
        """
        ticker = intent_data.get('ticker')
        option_type = intent_data.get('option_type', 'call').lower()
        strike = float(intent_data.get('strike', 0))
        dte = int(intent_data.get('dte', 0))
        quantity = int(intent_data.get('quantity', 1))
        
        if not all([ticker, strike, dte]):
            return {
                'can_approve': False,
                'blocking_issues': ['Missing required fields: ticker, strike, dte'],
                'warnings': []
            }
        
        # Run comprehensive safety check
        check_result = self.manager.check_option_safety(
            ticker, strike, dte, option_type, quantity
        )
        
        blocking_issues = []
        warnings = []
        
        # Extract blocking issues
        if not check_result['safe_to_sell']:
            blocking_issues = check_result['alerts']
        else:
            # Check for warnings even if safe
            assignment = check_result['checks']['assignment_risk']
            if assignment.get('assignment_likelihood', 0) > 25:
                warnings.append(
                    f"Assignment risk is {assignment['assignment_likelihood']:.1f}% - "
                    f"monitor position for assignment"
                )
            
            earnings = check_result['checks']['earnings_conflict']
            if earnings.get('earnings_in_days', 100) < 15:
                warnings.append(
                    f"Earnings in {earnings['earnings_in_days']} days - "
                    f"increased assignment risk near event"
                )
        
        return {
            'can_approve': check_result['safe_to_sell'],
            'assignment_check': check_result,
            'recommendation': check_result['overall_recommendation'],
            'blocking_issues': blocking_issues,
            'warnings': warnings,
            'timestamp': datetime.now().isoformat()
        }
    
    def format_approval_message(self, approval_result: Dict) -> Tuple[str, List]:
        """
        Format approval result for Telegram notification
        Returns: (message, inline_buttons)
        """
        ticker = approval_result['assignment_check']['symbol']
        strike = approval_result['assignment_check']['strike']
        opt_type = approval_result['assignment_check']['type'].upper()
        dte = approval_result['assignment_check']['dte']
        
        assignment = approval_result['assignment_check']['checks']['assignment_risk']
        assignment_prob = assignment.get('assignment_likelihood', 0)
        
        msg = f"*{ticker} ${strike} {opt_type} ({dte} DTE)*\n\n"
        msg += f"📊 *Assignment Risk*: {assignment_prob:.1f}%\n"
        msg += f"   {assignment.get('recommendation', 'N/A')}\n\n"
        
        if approval_result['blocking_issues']:
            msg += "❌ *BLOCKING ISSUES*:\n"
            for issue in approval_result['blocking_issues']:
                msg.replace('⚠️ ', '').replace('❌ ', '')
                msg += f"   • {issue}\n"
            msg += "\n"
        
        if approval_result['warnings']:
            msg += "⚠️ *WARNINGS*:\n"
            for warning in approval_result['warnings']:
                msg += f"   • {warning}\n"
            msg += "\n"
        
        msg += f"*Recommendation*: {approval_result['recommendation']}\n"
        
        # Buttons
        buttons = []
        if approval_result['can_approve']:
            buttons.append([
                {"text": "✅ APPROVE", "callback_data": f"approve_{ticker}_{strike}_{opt_type}"},
                {"text": "❌ REJECT", "callback_data": f"reject_{ticker}_{strike}_{opt_type}"}
            ])
        else:
            buttons.append([
                {"text": "⏸️ REVIEW MANUALLY", "callback_data": f"review_{ticker}_{strike}_{opt_type}"},
                {"text": "❌ REJECT", "callback_data": f"reject_{ticker}_{strike}_{opt_type}"}
            ])
        
        return msg, buttons
    
    def log_approved_option(self, ticker: str, strike: float, dte: int, 
                           option_type: str, assignment_prob: float, 
                           approval_result: Dict):
        """Log approved option for future reference"""
        log_entry = {
            'symbol': ticker,
            'strike': strike,
            'dte': dte,
            'type': option_type,
            'assignment_probability': assignment_prob,
            'assignment_check': approval_result['assignment_check'],
            'approved_at': datetime.now().isoformat(),
            'safe_to_sell': approval_result['can_approve']
        }
        
        # Append to log
        try:
            if APPROVED_ASSIGNMENTS_LOG.exists():
                with open(APPROVED_ASSIGNMENTS_LOG, 'r') as f:
                    log_data = json.load(f)
            else:
                log_data = {'version': '1.0', 'approvals': []}
            
            log_data['approvals'].append(log_entry)
            
            with open(APPROVED_ASSIGNMENTS_LOG, 'w') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to log approved option: {e}")


def assignment_check_hook(intent_data: Dict) -> Dict:
    """
    Hook function for options_monitor approval workflow
    
    This should be called in options_monitor.py before approving a SELL order:
    
    Usage in options_monitor.py:
    ```
    from options_monitor_integration import assignment_check_hook
    
    approval_result = assignment_check_hook(intent_data)
    if not approval_result['can_approve']:
        # Block approval and notify user
        send_telegram(approval_result['message'])
        return False
    
    # Continue with approval
    return True
    ```
    """
    checker = OptionsApprovalWithAssignmentCheck()
    return checker.check_before_approval(intent_data)


def send_telegram_with_assignment_check(intent_data: Dict, base_url: str = None) -> Tuple[str, List]:
    """
    Enhanced Telegram formatting with assignment check
    Replaces the format_telegram_message call in options_monitor
    
    Returns: (message, buttons)
    """
    checker = OptionsApprovalWithAssignmentCheck()
    approval_result = checker.check_before_approval(intent_data)
    return checker.format_approval_message(approval_result)


# Patches for options_monitor.py
def get_options_monitor_patch() -> str:
    """
    Returns the patch to apply to options_monitor.py
    
    This shows the changes needed in options_monitor.py to integrate assignment checking
    """
    return """
# PATCH for options_monitor.py - Add assignment risk checking

# 1. Add import at top:
from options_monitor_integration import assignment_check_hook, send_telegram_with_assignment_check

# 2. In create_pending_intent() function, add assignment data:
def create_pending_intent(opp):
    # ... existing code ...
    
    intent = {
        'id': intent_id,
        'token': token,
        'ticker': opp['ticker'],
        'type': opp['type'],
        'option_type': 'call' if opp['type'] == 'covered_call' else 'put',
        'strike': opp['suggested_strike'],
        'dte': opp['suggested_dte'],
        'action': 'SELL',
        'quantity': 1,
        'underlying_price': opp['current'],
        'canary': True,
        'ts': int(time.time() * 1000),
        'metrics': {
            'gain_pct': opp.get('gain_pct'),
            'pullback_pct': opp.get('pullback_pct'),
            'days_held': opp.get('days_held'),
            'vol_ratio': opp.get('vol_ratio')
        }
    }
    
    # NEW: Check assignment risk before creating pending intent
    assignment_check = assignment_check_hook(intent)
    if not assignment_check['can_approve']:
        logger.warning(f"Assignment check blocked {opp['ticker']}: {assignment_check['blocking_issues']}")
        # Skip creating this pending intent
        return None, None
    
    # ... rest of existing code ...
    return intent_id, token

# 3. Modify format_telegram_message to use assignment checking:
def format_telegram_message(opportunities):
    # Replace the old formatting with:
    all_buttons = []
    
    for opp in opportunities[:5]:
        intent_id, token = create_pending_intent(opp)
        if intent_id is None:  # Blocked by assignment check
            continue
        
        # Use enhanced formatting with assignment data
        msg, buttons = send_telegram_with_assignment_check(intent_data)
        all_buttons.extend(buttons)
    
    # ... rest of existing code ...

# 4. In main(), after scanning opportunities:
# Add logging of assignment checks:
if all_opportunities:
    msg, buttons = format_telegram_message(all_opportunities)
    if msg:
        print("\\n" + msg.replace('*', '').replace('_', ''))
        
        # NEW: Check assignment before sending to Telegram
        blocked_count = sum(1 for opp in all_opportunities 
                           if not assignment_check_hook(opp)['can_approve'])
        if blocked_count > 0:
            print(f"\\n⚠️ Blocked {blocked_count} opportunities due to assignment risk")
        
        if send_telegram(msg, buttons):
            print(f"\\n✅ Sent to Telegram ({len(buttons)} opportunities)")
"""


def main():
    """Test integration"""
    print("✅ Options Monitor Integration Module")
    print("\nThis module provides assignment risk checking for options_monitor.py")
    print("\nKey functions:")
    print("  • assignment_check_hook(intent_data) - Check before approval")
    print("  • send_telegram_with_assignment_check(intent_data) - Enhanced formatting")
    print("\nSee get_options_monitor_patch() for code changes needed")
    
    # Test with sample data
    test_intent = {
        'ticker': 'AAPL',
        'option_type': 'call',
        'strike': 230,
        'dte': 35,
        'quantity': 1,
        'action': 'SELL'
    }
    
    print(f"\n{'='*60}")
    print("Test: AAPL call option")
    print('='*60)
    
    checker = OptionsApprovalWithAssignmentCheck()
    result = checker.check_before_approval(test_intent)
    
    print(f"\n✅ Can Approve: {result['can_approve']}")
    print(f"📊 Recommendation: {result['recommendation']}")
    
    if result['blocking_issues']:
        print("\n❌ Blocking Issues:")
        for issue in result['blocking_issues']:
            print(f"   • {issue}")
    
    if result['warnings']:
        print("\n⚠️ Warnings:")
        for warning in result['warnings']:
            print(f"   • {warning}")


if __name__ == '__main__':
    main()
