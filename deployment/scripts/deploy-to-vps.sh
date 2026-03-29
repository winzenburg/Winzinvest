#!/bin/bash
# ============================================================================
# VPS Deployment Script - Run from your Mac
# ============================================================================
# Syncs all trading scripts, config, and dependencies to AWS Lightsail VPS.
#
# Usage:
#   ./deploy-to-vps.sh VPS_IP_ADDRESS
#
# First-time setup:
#   1. Provision AWS Lightsail instance
#   2. Set up SSH keys: ssh-copy-id ubuntu@VPS_IP
#   3. Run this script
#   4. SSH to VPS and complete IB Gateway 2FA setup
# ============================================================================

set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: $0 VPS_IP_ADDRESS"
  exit 1
fi

VPS_IP=$1
VPS_USER=ubuntu
LOCAL_DIR="$HOME/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control"
REMOTE_DIR="/home/$VPS_USER/MissionControl"

echo "=== Deploying Mission Control to $VPS_IP ==="

# Test SSH connection
if ! ssh -q -o BatchMode=yes -o ConnectTimeout=5 "$VPS_USER@$VPS_IP" exit; then
  echo "ERROR: Cannot connect to $VPS_IP"
  echo "Have you set up SSH keys? Run: ssh-copy-id $VPS_USER@$VPS_IP"
  exit 1
fi

# Sync trading directory
echo "Syncing trading scripts..."
rsync -avz --delete \
  --exclude=".git" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  --exclude=".DS_Store" \
  --exclude="venv" \
  --exclude="trading-env" \
  --exclude=".next" \
  --exclude="node_modules" \
  "$LOCAL_DIR/trading/" \
  "$VPS_USER@$VPS_IP:$REMOTE_DIR/trading/"

# Sync deployment files
echo "Syncing deployment configs..."
rsync -avz \
  "$LOCAL_DIR/deployment/" \
  "$VPS_USER@$VPS_IP:$REMOTE_DIR/deployment/"

# Create .env if it doesn't exist (user must edit manually)
ssh "$VPS_USER@$VPS_IP" << 'ENDSSH'
  if [ ! -f ~/MissionControl/trading/.env ]; then
    cat > ~/MissionControl/trading/.env << 'EOF'
# IB Gateway Connection
IB_HOST=127.0.0.1
IB_PORT=4001
TRADING_MODE=live

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Email (Resend)
RESEND_API_KEY=your_key_here

# Dashboard API Security
DASHBOARD_API_KEY=your_random_key_here
KILL_SWITCH_PIN=1234

# Optional: AWS S3 Backup
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
EOF
    echo "Created .env template - EDIT IT with actual credentials!"
  fi
ENDSSH

echo ""
echo "=== Deployment complete! ==="
echo ""
echo "Next steps:"
echo "  1. SSH to VPS: ssh $VPS_USER@$VPS_IP"
echo "  2. Edit .env: nano ~/MissionControl/trading/.env"
echo "  3. Install Docker: sudo apt install -y docker.io docker-compose"
echo "  4. Set up IB Gateway: cd ~/MissionControl/deployment && docker-compose up -d"
echo "  5. Connect via VNC for 2FA: open vnc://$VPS_IP:5900"
echo "  6. Install Python: sudo apt install -y python3.11 python3.11-venv"
echo "  7. Create venv: python3.11 -m venv ~/trading-env"
echo "  8. Install deps: ~/trading-env/bin/pip install -r ~/MissionControl/trading/requirements.txt"
echo "  9. Copy systemd services: sudo cp ~/MissionControl/deployment/systemd/*.service /etc/systemd/system/"
echo " 10. Enable services: sudo systemctl enable ib-gateway trading-scheduler trading-api"
echo " 11. Start services: sudo systemctl start ib-gateway && sleep 60 && sudo systemctl start trading-scheduler trading-api"
echo " 12. Check status: sudo systemctl status ib-gateway trading-scheduler trading-api"
echo ""
