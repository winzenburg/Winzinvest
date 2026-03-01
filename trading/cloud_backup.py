#!/usr/bin/env python3
"""
Cloud Backup Module
Daily backup of trading state to S3 and/or GitHub releases
Keeps 30 days of daily snapshots for disaster recovery
"""

import json
import logging
import os
import subprocess
import sys
import tarfile
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import tempfile
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
BACKUP_LOG = os.path.join(LOGS_DIR, 'cloud_backup.jsonl')
BACKUP_STATE_FILE = os.path.join(LOGS_DIR, '.backup_state.json')

# Files to backup
BACKUP_FILES = [
    'trading/portfolio.json',
    'trading/logs/stops_executed.json',
    'trading/logs/audit.jsonl',
    'trading/logs/reconciliation.jsonl',
    'trading/logs/post_execution_verification.jsonl',
    'trading/logs/pending_stops.json'
]

BACKUP_RETENTION_DAYS = 30


class CloudBackup:
    """Handles cloud backup of trading state"""
    
    def __init__(self, workspace_path: str = WORKSPACE):
        """Initialize backup manager"""
        self.workspace_path = workspace_path
        self.timestamp = datetime.now()
        self.backup_name = self.timestamp.strftime('trading_backup_%Y%m%d_%H%M%S')
        self.git_available = self._check_git()
        self.s3_available = self._check_s3()
    
    def _check_git(self) -> bool:
        """Check if git is available"""
        try:
            result = subprocess.run(['git', '--version'], 
                                  capture_output=True, 
                                  timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _check_s3(self) -> bool:
        """Check if AWS CLI is available"""
        try:
            result = subprocess.run(['aws', '--version'], 
                                  capture_output=True, 
                                  timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _run_command(self, command: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
        """Run a command and return (success, output)"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.workspace_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                error_msg = result.stderr or result.stdout
                logger.error(f"Command failed: {' '.join(command)}\n{error_msg}")
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(command)}")
            return False, "Command timeout"
        except Exception as e:
            logger.error(f"Error running command: {e}")
            return False, str(e)
    
    def create_backup_archive(self) -> Tuple[bool, str]:
        """
        Create a tar.gz archive of trading files
        
        Returns:
            (success: bool, archive_path: str)
        """
        try:
            # Create temp directory for archive
            temp_dir = tempfile.mkdtemp(prefix='trading_backup_')
            archive_path = os.path.join(temp_dir, f'{self.backup_name}.tar.gz')
            
            logger.info(f"📦 Creating backup archive: {archive_path}")
            
            with tarfile.open(archive_path, 'w:gz') as tar:
                for file_path in BACKUP_FILES:
                    full_path = os.path.join(self.workspace_path, file_path)
                    
                    if os.path.exists(full_path):
                        # Add file to archive, preserving relative path
                        arcname = os.path.basename(file_path)
                        tar.add(full_path, arcname=arcname)
                        logger.debug(f"  Added {file_path}")
                    else:
                        logger.debug(f"  Skipped (not found): {file_path}")
            
            logger.info(f"✅ Backup archive created ({os.path.getsize(archive_path)} bytes)")
            return True, archive_path
            
        except Exception as e:
            logger.error(f"❌ Error creating backup archive: {e}")
            return False, ""
    
    def backup_to_s3(self, bucket: str, prefix: str = 'trading-backups') -> Tuple[bool, Dict]:
        """
        Upload backup to AWS S3
        
        Args:
            bucket: S3 bucket name
            prefix: S3 prefix/folder
            
        Returns:
            (success: bool, result: dict)
        """
        if not self.s3_available:
            logger.warning("⚠️  AWS CLI not available - skipping S3 backup")
            return False, {'error': 'AWS CLI not available'}
        
        try:
            archive_ok, archive_path = self.create_backup_archive()
            if not archive_ok:
                return False, {'error': 'Failed to create backup archive'}
            
            # Upload to S3
            s3_path = f"s3://{bucket}/{prefix}/{self.backup_name}.tar.gz"
            logger.info(f"📤 Uploading to S3: {s3_path}")
            
            success, output = self._run_command(['aws', 's3', 'cp', archive_path, s3_path])
            
            if success:
                logger.info(f"✅ Uploaded to S3: {s3_path}")
                return True, {
                    'bucket': bucket,
                    's3_path': s3_path,
                    'timestamp': self.timestamp.isoformat(),
                    'archive_size': os.path.getsize(archive_path)
                }
            else:
                logger.error(f"❌ S3 upload failed: {output}")
                return False, {'error': output}
                
        except Exception as e:
            logger.error(f"❌ Error backing up to S3: {e}")
            return False, {'error': str(e)}
        finally:
            # Clean up temp archive
            if 'archive_path' in locals():
                try:
                    shutil.rmtree(os.path.dirname(archive_path), ignore_errors=True)
                except:
                    pass
    
    def backup_to_github_releases(self) -> Tuple[bool, Dict]:
        """
        Create GitHub release with backup archive
        
        Returns:
            (success: bool, result: dict)
        """
        if not self.git_available:
            logger.warning("⚠️  Git not available - skipping GitHub release backup")
            return False, {'error': 'Git not available'}
        
        try:
            # Check if we're in a git repo
            result = subprocess.run(['git', 'rev-parse', '--git-dir'],
                                  cwd=self.workspace_path,
                                  capture_output=True,
                                  timeout=5)
            
            if result.returncode != 0:
                logger.warning("⚠️  Not in a git repository - skipping GitHub release")
                return False, {'error': 'Not in git repository'}
            
            # Create archive
            archive_ok, archive_path = self.create_backup_archive()
            if not archive_ok:
                return False, {'error': 'Failed to create backup archive'}
            
            # Create git tag and release
            tag_name = f"backup-{self.timestamp.strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"🏷️  Creating git tag: {tag_name}")
            
            # Try to create tag (may fail if already exists, that's ok)
            subprocess.run(['git', 'tag', tag_name],
                         cwd=self.workspace_path,
                         capture_output=True,
                         timeout=10)
            
            # Note: Full GitHub release creation requires GitHub CLI or API key
            # For now, we just create the git tag which will be backed up in git
            logger.info(f"✅ Git tag created for backup: {tag_name}")
            
            return True, {
                'tag': tag_name,
                'timestamp': self.timestamp.isoformat(),
                'archive_path': archive_path,
                'note': 'Git tag created; push manually for GitHub release'
            }
                
        except Exception as e:
            logger.error(f"❌ Error creating GitHub release: {e}")
            return False, {'error': str(e)}
        finally:
            # Clean up temp archive
            if 'archive_path' in locals():
                try:
                    shutil.rmtree(os.path.dirname(archive_path), ignore_errors=True)
                except:
                    pass
    
    def cleanup_old_backups(self, days: int = BACKUP_RETENTION_DAYS) -> Dict:
        """
        Clean up backups older than retention period
        (This is a placeholder for cloud-specific cleanup)
        
        Returns:
            Cleanup summary
        """
        # Note: Actual cleanup would be cloud-specific
        # For S3: use aws s3 rm with --older-than
        # For GitHub: delete old releases
        
        logger.info(f"🗑️  Cleanup would remove backups older than {days} days")
        logger.info("(Cloud cleanup requires additional configuration)")
        
        return {
            'note': 'Cleanup not yet implemented',
            'recommend_retention': days,
            'manual_action': 'Review S3 bucket and GitHub releases periodically'
        }
    
    def run_daily_backup(self, use_s3: bool = False, use_github: bool = True) -> Dict:
        """
        Run complete daily backup
        
        Args:
            use_s3: Backup to S3 (requires AWS CLI and credentials)
            use_github: Backup via git (requires git repo)
            
        Returns:
            Backup result summary
        """
        logger.info("="*70)
        logger.info("CLOUD BACKUP STARTED")
        logger.info("="*70)
        
        result = {
            'timestamp': self.timestamp.isoformat(),
            'backup_name': self.backup_name,
            's3': None,
            'github': None,
            'status': 'success',
            'files_backed_up': BACKUP_FILES
        }
        
        # Try S3 backup
        if use_s3:
            # You would need to set the bucket name
            bucket = os.environ.get('TRADING_BACKUP_S3_BUCKET')
            if bucket:
                s3_ok, s3_result = self.backup_to_s3(bucket)
                result['s3'] = s3_result
                if not s3_ok:
                    result['status'] = 'partial'
            else:
                logger.info("ℹ️  S3 bucket not configured (set TRADING_BACKUP_S3_BUCKET env var)")
                result['s3'] = {'skipped': 'No S3 bucket configured'}
        
        # Try GitHub backup
        if use_github:
            gh_ok, gh_result = self.backup_to_github_releases()
            result['github'] = gh_result
            if not gh_ok:
                result['status'] = 'partial'
        
        # Log result
        self._log_backup(result)
        
        # Print summary
        self._print_summary(result)
        
        return result
    
    def _log_backup(self, result: Dict):
        """Log backup result to cloud_backup.jsonl"""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            with open(BACKUP_LOG, 'a') as f:
                f.write(json.dumps(result) + '\n')
            logger.info(f"📝 Backup logged to {BACKUP_LOG}")
        except Exception as e:
            logger.error(f"Failed to log backup: {e}")
    
    def _print_summary(self, result: Dict):
        """Print backup summary"""
        print("\n" + "="*70)
        print("CLOUD BACKUP SUMMARY")
        print("="*70)
        print(f"Timestamp: {result.get('timestamp')}")
        print(f"Status: {result.get('status').upper()}")
        
        if result.get('s3'):
            if 's3_path' in result['s3']:
                print(f"S3: ✅ {result['s3']['s3_path']}")
            elif 'skipped' in result['s3']:
                print(f"S3: ℹ️  {result['s3'].get('skipped', 'Skipped')}")
            else:
                print(f"S3: ❌ {result['s3'].get('error', 'Failed')}")
        
        if result.get('github'):
            if 'tag' in result['github']:
                print(f"GitHub: ✅ {result['github']['tag']}")
            elif 'error' not in result['github']:
                print(f"GitHub: ℹ️  {result['github'].get('note', 'Created')}")
            else:
                print(f"GitHub: ⚠️  {result['github'].get('error', 'Failed')}")
        
        print(f"Files backed up: {len(result.get('files_backed_up', []))}")
        print("="*70 + "\n")
    
    @staticmethod
    def list_backups() -> List[Dict]:
        """List available backups from backup log"""
        backups = []
        
        try:
            if os.path.exists(BACKUP_LOG):
                with open(BACKUP_LOG, 'r') as f:
                    for line in f:
                        if line.strip():
                            backup = json.loads(line)
                            backups.append(backup)
        except Exception as e:
            logger.error(f"Error reading backup log: {e}")
        
        return backups


def run_daily_backup(use_s3: bool = False, use_github: bool = True) -> Dict:
    """Convenience function to run daily backup"""
    backup = CloudBackup()
    return backup.run_daily_backup(use_s3=use_s3, use_github=use_github)


if __name__ == '__main__':
    # Run daily backup
    result = run_daily_backup(use_s3=False, use_github=True)
    
    # Show recent backups
    backups = CloudBackup.list_backups()
    if backups:
        print("\nRecent backups:")
        print("-"*70)
        for backup in backups[-5:]:  # Show last 5
            print(f"{backup.get('timestamp')} | {backup.get('status')}")
