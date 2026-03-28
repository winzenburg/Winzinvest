#!/bin/bash
# ============================================================================
# Trading Data Backup Script
# ============================================================================
# Backs up all trading logs, config, and watchlists daily.
# Retains last 7 days locally, optionally syncs to S3.
#
# Installation:
#   1. Copy to VPS: ~/backup-trading-data.sh
#   2. Make executable: chmod +x ~/backup-trading-data.sh
#   3. Add to crontab: crontab -e
#      0 3 * * * ~/backup-trading-data.sh >> ~/backup.log 2>&1
#
# With S3 sync:
#   1. Install AWS CLI: sudo apt install -y awscli
#   2. Configure: aws configure
#   3. Uncomment the S3 sync line below
# ============================================================================

set -euo pipefail

DATE=$(date +%Y%m%d)
BACKUP_DIR=~/backups
TRADING_DIR=~/MissionControl/trading
S3_BUCKET="s3://winzinvest-trading-backups"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# Create compressed archive
tar -czf "$BACKUP_DIR/trading-$DATE.tar.gz" \
  -C "$TRADING_DIR" \
  logs \
  config \
  *.json \
  watchlists \
  || echo "Warning: Some files may be missing"

# Verify backup was created
if [ -f "$BACKUP_DIR/trading-$DATE.tar.gz" ]; then
  SIZE=$(du -h "$BACKUP_DIR/trading-$DATE.tar.gz" | cut -f1)
  echo "[$(date)] Backup created: trading-$DATE.tar.gz ($SIZE)"
else
  echo "[$(date)] ERROR: Backup failed!"
  exit 1
fi

# Delete backups older than 7 days
find "$BACKUP_DIR" -name "trading-*.tar.gz" -mtime +7 -delete
echo "[$(date)] Cleaned up old backups (>7 days)"

# Optional: Sync to S3 (uncomment to enable)
# echo "[$(date)] Syncing to S3..."
# aws s3 sync "$BACKUP_DIR" "$S3_BUCKET/backups/" --exclude "*" --include "trading-*.tar.gz"
# aws s3 sync "$TRADING_DIR/logs/" "$S3_BUCKET/logs/" --exclude "*.pyc" --exclude "__pycache__"
# echo "[$(date)] S3 sync complete"

echo "[$(date)] Backup complete"
