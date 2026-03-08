#!/usr/bin/env python3
"""
Integration Test for Trade Reconciliation System
Tests all modules can be imported and basic functions work
"""

import sys
import os
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Colors for output
class Colors:
    PASS = '\033[92m'  # Green
    FAIL = '\033[91m'  # Red
    INFO = '\033[94m'  # Blue
    END = '\033[0m'    # Reset

def test_module_import(module_name, import_statement):
    """Test if a module can be imported"""
    try:
        exec(import_statement)
        print(f"{Colors.PASS}✅ PASS{Colors.END} - {module_name}")
        return True
    except Exception as e:
        print(f"{Colors.FAIL}❌ FAIL{Colors.END} - {module_name}: {e}")
        return False

def test_file_exists(filepath):
    """Test if a required file exists"""
    try:
        if os.path.exists(filepath):
            print(f"{Colors.PASS}✅ PASS{Colors.END} - {os.path.basename(filepath)} exists")
            return True
        else:
            print(f"{Colors.FAIL}❌ FAIL{Colors.END} - {os.path.basename(filepath)} NOT FOUND")
            return False
    except Exception as e:
        print(f"{Colors.FAIL}❌ FAIL{Colors.END} - Error checking {filepath}: {e}")
        return False

def test_git_available():
    """Test if git is available"""
    try:
        import subprocess
        result = subprocess.run(['git', '--version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            print(f"{Colors.PASS}✅ PASS{Colors.END} - Git is available")
            return True
        else:
            print(f"{Colors.FAIL}❌ FAIL{Colors.END} - Git not found")
            return False
    except Exception as e:
        print(f"{Colors.FAIL}❌ FAIL{Colors.END} - Git check failed: {e}")
        return False

def main():
    """Run all integration tests"""
    
    print("=" * 70)
    print("TRADE RECONCILIATION SYSTEM - INTEGRATION TEST")
    print("=" * 70)
    print()
    
    results = {}
    
    # ===== Module Import Tests =====
    print(f"{Colors.INFO}1. MODULE IMPORTS{Colors.END}")
    print("-" * 70)
    
    results['post_execution_verification'] = test_module_import(
        'post_execution_verification',
        'from post_execution_verification import PostExecutionVerifier'
    )
    
    results['daily_reconciliation'] = test_module_import(
        'daily_reconciliation',
        'from daily_reconciliation import DailyReconciler'
    )
    
    results['git_auto_commit'] = test_module_import(
        'git_auto_commit',
        'from git_auto_commit import GitAutoCommitter'
    )
    
    results['cloud_backup'] = test_module_import(
        'cloud_backup',
        'from cloud_backup import CloudBackup'
    )
    
    results['disaster_recovery'] = test_module_import(
        'disaster_recovery',
        'from disaster_recovery import DisasterRecoveryManager'
    )
    
    results['commission_tracker'] = test_module_import(
        'commission_tracker',
        'from commission_tracker import CommissionTracker'
    )
    
    results['slippage_tracker'] = test_module_import(
        'slippage_tracker',
        'from slippage_tracker import SlippageTracker'
    )
    
    print()
    
    # ===== File Existence Tests =====
    print(f"{Colors.INFO}2. REQUIRED FILES{Colors.END}")
    print("-" * 70)
    
    workspace = os.path.expanduser('~/.openclaw/workspace')
    trading_dir = os.path.join(workspace, 'trading')
    logs_dir = os.path.join(trading_dir, 'logs')
    
    files_to_check = [
        os.path.join(trading_dir, 'portfolio.json'),
        os.path.join(logs_dir, 'stops_executed.json'),
        os.path.join(trading_dir, 'DISASTER_RECOVERY_RUNBOOK.md'),
        os.path.join(trading_dir, 'INTEGRATION_PATCHES.md'),
    ]
    
    for filepath in files_to_check:
        results[f"file_{os.path.basename(filepath)}"] = test_file_exists(filepath)
    
    print()
    
    # ===== External Tools Tests =====
    print(f"{Colors.INFO}3. EXTERNAL TOOLS{Colors.END}")
    print("-" * 70)
    
    results['git_available'] = test_git_available()
    
    print()
    
    # ===== Functionality Tests =====
    print(f"{Colors.INFO}4. BASIC FUNCTIONALITY{Colors.END}")
    print("-" * 70)
    
    # Test post_execution_verification basic setup
    try:
        from post_execution_verification import PostExecutionVerifier
        verifier = PostExecutionVerifier()
        if hasattr(verifier, 'fetch_ib_positions'):
            print(f"{Colors.PASS}✅ PASS{Colors.END} - PostExecutionVerifier has required methods")
            results['post_exec_methods'] = True
        else:
            print(f"{Colors.FAIL}❌ FAIL{Colors.END} - PostExecutionVerifier missing methods")
            results['post_exec_methods'] = False
    except Exception as e:
        print(f"{Colors.FAIL}❌ FAIL{Colors.END} - PostExecutionVerifier test failed: {e}")
        results['post_exec_methods'] = False
    
    # Test git_auto_commit basic setup
    try:
        from git_auto_commit import GitAutoCommitter
        committer = GitAutoCommitter()
        if hasattr(committer, 'auto_commit_trade'):
            print(f"{Colors.PASS}✅ PASS{Colors.END} - GitAutoCommitter has required methods")
            results['git_commit_methods'] = True
        else:
            print(f"{Colors.FAIL}❌ FAIL{Colors.END} - GitAutoCommitter missing methods")
            results['git_commit_methods'] = False
    except Exception as e:
        print(f"{Colors.FAIL}❌ FAIL{Colors.END} - GitAutoCommitter test failed: {e}")
        results['git_commit_methods'] = False
    
    # Test cloud backup basic setup
    try:
        from cloud_backup import CloudBackup
        backup = CloudBackup()
        if hasattr(backup, 'run_daily_backup'):
            print(f"{Colors.PASS}✅ PASS{Colors.END} - CloudBackup has required methods")
            results['cloud_backup_methods'] = True
        else:
            print(f"{Colors.FAIL}❌ FAIL{Colors.END} - CloudBackup missing methods")
            results['cloud_backup_methods'] = False
    except Exception as e:
        print(f"{Colors.FAIL}❌ FAIL{Colors.END} - CloudBackup test failed: {e}")
        results['cloud_backup_methods'] = False
    
    # Test disaster recovery basic setup
    try:
        from disaster_recovery import DisasterRecoveryManager
        recovery = DisasterRecoveryManager()
        if hasattr(recovery, 'generate_recovery_report'):
            print(f"{Colors.PASS}✅ PASS{Colors.END} - DisasterRecoveryManager has required methods")
            results['disaster_recovery_methods'] = True
        else:
            print(f"{Colors.FAIL}❌ FAIL{Colors.END} - DisasterRecoveryManager missing methods")
            results['disaster_recovery_methods'] = False
    except Exception as e:
        print(f"{Colors.FAIL}❌ FAIL{Colors.END} - DisasterRecoveryManager test failed: {e}")
        results['disaster_recovery_methods'] = False
    
    print()
    
    # ===== Summary =====
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nResults: {passed}/{total} tests passed")
    print()
    
    # List failures
    failures = [k for k, v in results.items() if not v]
    if failures:
        print(f"{Colors.FAIL}Failed tests:{Colors.END}")
        for test in failures:
            print(f"  - {test}")
        print()
    
    # Overall result
    if passed == total:
        print(f"{Colors.PASS}✅ ALL TESTS PASSED!{Colors.END}")
        print("\nSystem is ready for production use.")
        print("\nNext steps:")
        print("1. Run setup_cron.sh to schedule daily jobs")
        print("2. Integrate patches from INTEGRATION_PATCHES.md")
        print("3. Test with a manual trade entry")
        print("4. Monitor logs for 1 week")
        return 0
    else:
        print(f"{Colors.FAIL}❌ SOME TESTS FAILED{Colors.END}")
        print("\nPlease fix the issues above before proceeding.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
