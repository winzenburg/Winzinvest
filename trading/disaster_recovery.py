#!/usr/bin/env python3
"""
Disaster Recovery Module
Handles restoration from backups and reconciliation after crashes
Provides step-by-step recovery procedures
"""

import json
import logging
import os
import subprocess
import sys
import tarfile
import tempfile
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
TRADING_DIR = os.path.join(WORKSPACE, 'trading')
LOGS_DIR = os.path.join(TRADING_DIR, 'logs')
PORTFOLIO_FILE = os.path.join(TRADING_DIR, 'portfolio.json')
RECOVERY_LOG = os.path.join(LOGS_DIR, 'disaster_recovery.jsonl')
BACKUP_LOG = os.path.join(LOGS_DIR, 'cloud_backup.jsonl')


class DisasterRecoveryManager:
    """Handles disaster recovery scenarios"""
    
    def __init__(self, workspace_path: str = WORKSPACE):
        """Initialize recovery manager"""
        self.workspace_path = workspace_path
        self.trading_dir = TRADING_DIR
        self.timestamp = datetime.now()
    
    def restore_from_backup(self, backup_date: Optional[str] = None, 
                           archive_path: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Restore portfolio.json from a backup
        
        Args:
            backup_date: Date of backup to restore (YYYY-MM-DD format)
            archive_path: Direct path to backup archive
            
        Returns:
            (success: bool, result: dict)
        """
        try:
            # Find backup archive
            if archive_path:
                if not os.path.exists(archive_path):
                    return False, {'error': f'Backup archive not found: {archive_path}'}
                source_archive = archive_path
            else:
                # Look for most recent backup
                backups = self._get_available_backups()
                if not backups:
                    return False, {'error': 'No backups available'}
                
                source_archive = backups[0]['path']
                logger.info(f"Using most recent backup: {source_archive}")
            
            # Create backup of current state first
            current_backup = self._backup_current_state()
            logger.info(f"✅ Current state backed up to: {current_backup}")
            
            # Extract archive
            logger.info(f"📦 Extracting backup archive: {source_archive}")
            temp_dir = tempfile.mkdtemp(prefix='recovery_')
            
            try:
                with tarfile.open(source_archive, 'r:gz') as tar:
                    tar.extractall(temp_dir)
                
                # Restore files
                restored_files = []
                
                # Restore portfolio.json
                portfolio_src = os.path.join(temp_dir, 'portfolio.json')
                if os.path.exists(portfolio_src):
                    shutil.copy2(portfolio_src, PORTFOLIO_FILE)
                    restored_files.append('portfolio.json')
                    logger.info(f"✅ Restored portfolio.json")
                
                # Restore other files if needed
                other_files = ['stops_executed.json', 'audit.jsonl', 'reconciliation.jsonl']
                for filename in other_files:
                    src = os.path.join(temp_dir, filename)
                    dst = os.path.join(LOGS_DIR, filename)
                    if os.path.exists(src):
                        shutil.copy2(src, dst)
                        restored_files.append(filename)
                        logger.info(f"✅ Restored {filename}")
                
                result = {
                    'action': 'restore_from_backup',
                    'backup_source': source_archive,
                    'current_state_backup': current_backup,
                    'files_restored': restored_files,
                    'timestamp': self.timestamp.isoformat(),
                    'status': 'success'
                }
                
                logger.info(f"✅ Restoration complete - restored {len(restored_files)} files")
                return True, result
                
            finally:
                # Clean up temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(f"❌ Error restoring from backup: {e}")
            return False, {'error': str(e)}
    
    def query_ib_positions(self) -> Tuple[bool, Dict]:
        """
        Query IB Gateway for current positions
        
        Returns:
            (success: bool, positions: dict)
        """
        try:
            # Import post_execution_verification to use its IB connection
            from post_execution_verification import PostExecutionVerifier
            
            verifier = PostExecutionVerifier()
            if not verifier.connect(timeout_seconds=15):
                return False, {'error': 'Cannot connect to IB Gateway'}
            
            try:
                ib_positions = verifier.fetch_ib_positions()
                logger.info(f"✅ Retrieved {len(ib_positions)} positions from IB Gateway")
                return True, ib_positions
            finally:
                verifier.disconnect()
                
        except ImportError:
            logger.error("Cannot import post_execution_verification module")
            return False, {'error': 'post_execution_verification module not available'}
        except Exception as e:
            logger.error(f"❌ Error querying IB Gateway: {e}")
            return False, {'error': str(e)}
    
    def load_restored_portfolio(self) -> Tuple[bool, Dict]:
        """Load portfolio state from restored portfolio.json"""
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
            
            position_dict = {}
            for pos in data.get('positions', []):
                symbol = pos.get('symbol')
                qty = pos.get('quantity', 0)
                
                if symbol:
                    if symbol not in position_dict:
                        position_dict[symbol] = 0
                    position_dict[symbol] += qty
            
            logger.info(f"✅ Loaded {len(position_dict)} positions from restored portfolio")
            return True, position_dict
            
        except Exception as e:
            logger.error(f"❌ Error loading restored portfolio: {e}")
            return False, {'error': str(e)}
    
    def compare_and_reconcile(self) -> Tuple[bool, Dict]:
        """
        Compare restored portfolio with IB Gateway positions
        
        Returns:
            (reconciliation_ok: bool, report: dict)
        """
        try:
            logger.info("🔍 Starting disaster recovery reconciliation...")
            
            # Get IB positions
            ib_ok, ib_positions = self.query_ib_positions()
            if not ib_ok:
                return False, {
                    'error': 'Cannot query IB positions',
                    'ib_result': ib_positions,
                    'recommendation': 'Verify IB Gateway is running and accessible'
                }
            
            # Get restored portfolio
            portfolio_ok, portfolio_positions = self.load_restored_portfolio()
            if not portfolio_ok:
                return False, {
                    'error': 'Cannot load restored portfolio',
                    'portfolio_result': portfolio_positions,
                    'recommendation': 'Check if restoration was successful'
                }
            
            # Compare
            discrepancies = []
            all_symbols = set(ib_positions.keys()) | set(portfolio_positions.keys())
            
            for symbol in all_symbols:
                ib_qty = ib_positions.get(symbol, 0)
                portfolio_qty = portfolio_positions.get(symbol, 0)
                
                if ib_qty != portfolio_qty:
                    discrepancies.append({
                        'symbol': symbol,
                        'portfolio_qty': portfolio_qty,
                        'ib_qty': ib_qty,
                        'variance': ib_qty - portfolio_qty
                    })
            
            # Generate report
            report = {
                'action': 'compare_and_reconcile',
                'timestamp': self.timestamp.isoformat(),
                'ib_positions': ib_positions,
                'portfolio_positions': portfolio_positions,
                'discrepancy_count': len(discrepancies),
                'discrepancies': discrepancies,
                'status': 'OK' if len(discrepancies) == 0 else 'MISMATCHES_FOUND'
            }
            
            if len(discrepancies) == 0:
                logger.info("✅ Reconciliation successful - positions match perfectly!")
                return True, report
            else:
                logger.warning(f"⚠️  Found {len(discrepancies)} discrepancies")
                return False, report
                
        except Exception as e:
            logger.error(f"❌ Error during reconciliation: {e}")
            return False, {'error': str(e)}
    
    def generate_recovery_report(self) -> Dict:
        """
        Generate complete disaster recovery report
        
        Returns:
            Recovery status report
        """
        report = {
            'recovery_started': self.timestamp.isoformat(),
            'workspace': self.workspace_path,
            'steps': []
        }
        
        # Step 1: Try to restore from backup
        logger.info("\n📋 STEP 1: Restore from backup")
        restore_ok, restore_result = self.restore_from_backup()
        report['steps'].append({
            'step': 1,
            'action': 'restore_from_backup',
            'success': restore_ok,
            'result': restore_result
        })
        
        if not restore_ok:
            report['status'] = 'RESTORE_FAILED'
            logger.error("❌ Restoration failed - cannot proceed with recovery")
            return report
        
        # Step 2: Query IB Gateway
        logger.info("\n📋 STEP 2: Query IB Gateway for current positions")
        ib_ok, ib_positions = self.query_ib_positions()
        report['steps'].append({
            'step': 2,
            'action': 'query_ib_positions',
            'success': ib_ok,
            'result': ib_positions if ib_ok else {'error': ib_positions}
        })
        
        if not ib_ok:
            report['status'] = 'IB_GATEWAY_UNAVAILABLE'
            logger.error("❌ IB Gateway unavailable - cannot verify recovery")
            return report
        
        # Step 3: Reconcile
        logger.info("\n📋 STEP 3: Compare and reconcile positions")
        reconcile_ok, reconcile_result = self.compare_and_reconcile()
        report['steps'].append({
            'step': 3,
            'action': 'compare_and_reconcile',
            'success': reconcile_ok,
            'result': reconcile_result
        })
        
        # Final status
        if reconcile_ok:
            report['status'] = 'RECOVERY_SUCCESS'
            report['recommendation'] = 'System is ready to resume trading'
            logger.info("✅ RECOVERY COMPLETE - System ready to resume")
        else:
            report['status'] = 'RECOVERY_PARTIAL'
            report['recommendation'] = 'Investigate discrepancies before resuming trading'
            logger.warning("⚠️  Recovery partial - manual investigation required")
        
        # Log report
        self._log_recovery(report)
        
        return report
    
    def _backup_current_state(self) -> str:
        """Create timestamped backup of current portfolio state"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(LOGS_DIR, 'disaster_recovery_backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_path = os.path.join(backup_dir, f'portfolio_backup_{timestamp}.json')
            
            if os.path.exists(PORTFOLIO_FILE):
                shutil.copy2(PORTFOLIO_FILE, backup_path)
            
            return backup_path
        except Exception as e:
            logger.error(f"Error backing up current state: {e}")
            return ""
    
    def _get_available_backups(self) -> List[Dict]:
        """Get list of available backups"""
        backups = []
        
        try:
            # Read from backup log
            if os.path.exists(BACKUP_LOG):
                with open(BACKUP_LOG, 'r') as f:
                    for line in f:
                        if line.strip():
                            backup_info = json.loads(line)
                            if backup_info.get('github', {}).get('archive_path'):
                                backups.append({
                                    'timestamp': backup_info.get('timestamp'),
                                    'path': backup_info['github']['archive_path'],
                                    'status': backup_info.get('status')
                                })
            
            # Sort by timestamp (most recent first)
            backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
        except Exception as e:
            logger.warning(f"Error reading backup log: {e}")
        
        return backups
    
    def _log_recovery(self, report: Dict):
        """Log recovery report to disaster_recovery.jsonl"""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            with open(RECOVERY_LOG, 'a') as f:
                f.write(json.dumps(report) + '\n')
            logger.info(f"📝 Recovery logged to {RECOVERY_LOG}")
        except Exception as e:
            logger.error(f"Failed to log recovery: {e}")
    
    def print_recovery_report(self, report: Dict):
        """Print recovery report"""
        print("\n" + "="*70)
        print("DISASTER RECOVERY REPORT")
        print("="*70)
        print(f"Started: {report.get('recovery_started')}")
        print(f"Status: {report.get('status')}")
        print(f"Recommendation: {report.get('recommendation', 'None')}")
        
        print(f"\nRecovery Steps ({len(report.get('steps', []))}):")
        print("-"*70)
        
        for step in report.get('steps', []):
            status = "✅ PASS" if step['success'] else "❌ FAIL"
            print(f"Step {step['step']}: {step['action']} [{status}]")
            
            if not step['success'] and 'error' in str(step['result']):
                print(f"  Error: {step['result'].get('error', 'Unknown error')}")
        
        print("="*70 + "\n")


def run_disaster_recovery() -> Dict:
    """Convenience function to run complete disaster recovery"""
    recovery = DisasterRecoveryManager()
    report = recovery.generate_recovery_report()
    recovery.print_recovery_report(report)
    return report


if __name__ == '__main__':
    logger.info("="*70)
    logger.info("DISASTER RECOVERY SYSTEM")
    logger.info("="*70)
    
    report = run_disaster_recovery()
    
    # Exit with status code
    if report.get('status') == 'RECOVERY_SUCCESS':
        sys.exit(0)
    else:
        sys.exit(1)
