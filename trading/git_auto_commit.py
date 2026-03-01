#!/usr/bin/env python3
"""
Git Auto-Commit Module
Auto-commits trading files to GitHub after every trade
Provides full audit trail and disaster recovery via git history
"""

import json
import logging
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
TRADING_DIR = os.path.join(WORKSPACE, 'trading')
GIT_DIR = WORKSPACE


class GitAutoCommitter:
    """Handles git auto-commits for trading operations"""
    
    def __init__(self, repo_path: str = GIT_DIR):
        """Initialize git manager"""
        self.repo_path = repo_path
        self.git_available = self._check_git()
        
        # Files to include in trades commits
        self.trade_files = [
            'trading/portfolio.json',
            'trading/logs/stops_executed.json',
            'trading/logs/audit.jsonl',
            'trading/logs/pending_stops.json',
            'trading/logs/reconciliation.jsonl',
            'trading/logs/post_execution_verification.jsonl'
        ]
    
    def _check_git(self) -> bool:
        """Check if git is available and repo exists"""
        try:
            result = subprocess.run(['git', '--version'], 
                                  capture_output=True, 
                                  timeout=5)
            git_exists = result.returncode == 0
            
            if git_exists:
                logger.info("✅ Git is available")
            else:
                logger.warning("⚠️  Git not found in PATH")
            
            return git_exists
        except Exception as e:
            logger.error(f"❌ Git check failed: {e}")
            return False
    
    def _run_git_command(self, command: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
        """Run a git command and return (success, output)"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                error_msg = result.stderr or result.stdout
                logger.error(f"Git command failed: {' '.join(command)}\n{error_msg}")
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            logger.error(f"Git command timed out: {' '.join(command)}")
            return False, "Command timeout"
        except Exception as e:
            logger.error(f"Error running git command: {e}")
            return False, str(e)
    
    def is_git_repo(self) -> bool:
        """Check if we're in a git repository"""
        if not self.git_available:
            return False
        
        success, _ = self._run_git_command(['git', 'rev-parse', '--git-dir'])
        return success
    
    def get_git_status(self) -> Dict:
        """Get git status"""
        success, output = self._run_git_command(['git', 'status', '--porcelain'])
        
        if not success:
            return {'error': 'Failed to get git status'}
        
        changed_files = [line.strip() for line in output.split('\n') if line.strip()]
        
        return {
            'has_changes': len(changed_files) > 0,
            'changed_files': changed_files,
            'file_count': len(changed_files)
        }
    
    def stage_trading_files(self, specific_files: Optional[List[str]] = None) -> Tuple[bool, Dict]:
        """
        Stage trading-related files for commit
        
        Args:
            specific_files: List of specific files to stage (defaults to self.trade_files)
            
        Returns:
            (success: bool, result: dict)
        """
        if not self.git_available:
            return False, {'error': 'Git not available'}
        
        if not self.is_git_repo():
            return False, {'error': 'Not in a git repository'}
        
        files_to_stage = specific_files or self.trade_files
        
        try:
            for file_path in files_to_stage:
                full_path = os.path.join(self.repo_path, file_path)
                
                # Only stage if file exists
                if os.path.exists(full_path):
                    success, _ = self._run_git_command(['git', 'add', file_path])
                    if success:
                        logger.info(f"✅ Staged {file_path}")
                    else:
                        logger.warning(f"⚠️  Failed to stage {file_path}")
                else:
                    logger.debug(f"ℹ️  File not found (skipping): {file_path}")
            
            status = self.get_git_status()
            return True, status
            
        except Exception as e:
            logger.error(f"❌ Error staging files: {e}")
            return False, {'error': str(e)}
    
    def create_commit(self, message: str, specific_files: Optional[List[str]] = None) -> Tuple[bool, Dict]:
        """
        Create a git commit with trading changes
        
        Args:
            message: Commit message (e.g., "[TRADE] AAPL entry $150, qty 10")
            specific_files: Specific files to commit
            
        Returns:
            (success: bool, result: dict)
        """
        if not self.git_available:
            return False, {'error': 'Git not available'}
        
        if not self.is_git_repo():
            return False, {'error': 'Not in a git repository'}
        
        try:
            # Stage files first
            stage_success, stage_result = self.stage_trading_files(specific_files)
            if not stage_success:
                return False, {'error': 'Failed to stage files', 'stage_result': stage_result}
            
            # Check if there's anything to commit
            status = self.get_git_status()
            if not status.get('has_changes'):
                logger.info("ℹ️  No changes to commit")
                return True, {'status': 'no_changes', 'message': 'No files to commit'}
            
            # Create commit
            success, output = self._run_git_command(['git', 'commit', '-m', message])
            
            if success:
                logger.info(f"✅ Commit created: {message}")
                return True, {
                    'message': message,
                    'timestamp': datetime.now().isoformat(),
                    'output': output.strip()
                }
            else:
                logger.error(f"❌ Failed to create commit: {output}")
                return False, {'error': output}
                
        except Exception as e:
            logger.error(f"❌ Error creating commit: {e}")
            return False, {'error': str(e)}
    
    def push_to_github(self, branch: str = 'main') -> Tuple[bool, Dict]:
        """
        Push commits to GitHub
        
        Args:
            branch: Branch to push to (default: main)
            
        Returns:
            (success: bool, result: dict)
        """
        if not self.git_available:
            return False, {'error': 'Git not available'}
        
        if not self.is_git_repo():
            return False, {'error': 'Not in a git repository'}
        
        try:
            success, output = self._run_git_command(['git', 'push', 'origin', branch])
            
            if success:
                logger.info(f"✅ Pushed to GitHub (branch: {branch})")
                return True, {
                    'branch': branch,
                    'timestamp': datetime.now().isoformat(),
                    'output': output.strip()
                }
            else:
                logger.warning(f"⚠️  Push to GitHub failed: {output}")
                # Don't fail completely - local commit is still valuable
                return False, {'error': output, 'note': 'Local commit saved'}
                
        except Exception as e:
            logger.error(f"❌ Error pushing to GitHub: {e}")
            return False, {'error': str(e), 'note': 'Local commit saved'}
    
    def auto_commit_trade(self, trade_info: Dict, push: bool = True) -> Tuple[bool, Dict]:
        """
        Auto-commit a trade (entry, exit, stop placement, etc.)
        
        Args:
            trade_info: Trade details dict with keys: symbol, action, price, qty, etc.
            push: Whether to push to GitHub immediately
            
        Returns:
            (success: bool, result: dict)
        """
        try:
            # Build commit message
            symbol = trade_info.get('symbol', 'UNKNOWN')
            action = trade_info.get('action', 'TRADE').upper()
            price = trade_info.get('price', '?')
            qty = trade_info.get('qty', trade_info.get('quantity', '?'))
            reason = trade_info.get('reason', '')
            
            if reason:
                message = f"[TRADE] {symbol} {action} ${price}, qty {qty} - {reason}"
            else:
                message = f"[TRADE] {symbol} {action} ${price}, qty {qty}"
            
            # Create commit
            commit_success, commit_result = self.create_commit(message)
            
            if not commit_success:
                logger.error(f"❌ Failed to commit trade: {commit_result}")
                return False, commit_result
            
            # Push if requested
            push_success, push_result = True, {'skipped': True}
            if push:
                push_success, push_result = self.push_to_github()
            
            return commit_success, {
                'trade': trade_info,
                'commit': commit_result,
                'push': push_result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error auto-committing trade: {e}")
            return False, {'error': str(e)}
    
    def get_trade_history(self, limit: int = 20) -> List[Dict]:
        """
        Get recent trade commits from git log
        
        Args:
            limit: Number of commits to retrieve
            
        Returns:
            List of commit dicts
        """
        if not self.is_git_repo():
            return []
        
        try:
            format_str = '%H|%h|%ai|%s'
            success, output = self._run_git_command(
                ['git', 'log', '--grep=TRADE', f'-{limit}', f'--format={format_str}']
            )
            
            if not success:
                logger.warning("Failed to get trade history")
                return []
            
            commits = []
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 4:
                        commits.append({
                            'hash': parts[0],
                            'short_hash': parts[1],
                            'timestamp': parts[2],
                            'message': parts[3]
                        })
            
            return commits
            
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return []


def auto_commit_trade(symbol: str, action: str, price: float, qty: float, 
                     reason: str = '', push: bool = True) -> Tuple[bool, Dict]:
    """Convenience function for auto-committing trades"""
    committer = GitAutoCommitter()
    
    trade_info = {
        'symbol': symbol,
        'action': action,
        'price': price,
        'qty': qty,
        'reason': reason,
        'timestamp': datetime.now().isoformat()
    }
    
    return committer.auto_commit_trade(trade_info, push=push)


if __name__ == '__main__':
    committer = GitAutoCommitter()
    
    print("Git Auto-Commit Module")
    print("=" * 70)
    
    if not committer.git_available:
        print("❌ Git not available on this system")
        sys.exit(1)
    
    if not committer.is_git_repo():
        print("❌ Not in a git repository")
        sys.exit(1)
    
    print("✅ Git is configured and repository is available")
    
    # Show recent trade commits
    history = committer.get_trade_history(limit=10)
    if history:
        print("\nRecent trades (from git history):")
        print("-" * 70)
        for commit in history:
            print(f"{commit['timestamp']} | {commit['message']}")
    else:
        print("\nNo trade commits found in history")
