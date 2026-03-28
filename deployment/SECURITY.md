# VPS Security Hardening Guide

This guide covers all security measures for the production trading VPS.

## Overview

Security layers:
1. **SSH access control** - Key-based authentication only
2. **UFW firewall** - Restrict all ports to known IPs
3. **Fail2Ban** - Auto-ban brute force attempts
4. **API authentication** - Dashboard API key required
5. **IB Gateway isolation** - API port not exposed externally

---

## 1. SSH Key Authentication (Required)

### From your Mac:

```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy public key to VPS
ssh-copy-id ubuntu@YOUR_VPS_IP
```

### On VPS:

```bash
# Disable password authentication
sudo nano /etc/ssh/sshd_config
```

Set these values:
```
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

---

## 2. UFW Firewall Configuration (Required)

### Install and configure UFW:

```bash
# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH from your IP only
sudo ufw allow from YOUR_HOME_IP to any port 22 comment 'SSH from home'

# Allow API access from Vercel
sudo ufw allow from 76.76.21.0/24 to any port 8000 comment 'Vercel IP range 1'
sudo ufw allow from 76.76.19.0/24 to any port 8000 comment 'Vercel IP range 2'

# Allow VNC from your IP only (for IB Gateway 2FA setup)
sudo ufw allow from YOUR_HOME_IP to any port 5900 comment 'VNC from home'

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status numbered
```

### Port access matrix:

| Port | Service | Allowed From | Notes |
|------|---------|--------------|-------|
| 22 | SSH | Your IP only | Admin access |
| 8000 | Dashboard API | Vercel IPs only | Dashboard data |
| 5900 | VNC | Your IP only | IB Gateway 2FA setup |
| 4001 | IB Gateway | localhost only | Not exposed externally |

---

## 3. Fail2Ban (Recommended)

Automatically bans IPs after repeated failed SSH attempts.

```bash
# Install
sudo apt install -y fail2ban

# Enable and start
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Check status
sudo fail2ban-client status sshd
```

Default config:
- Max 5 failed attempts
- 10 minute ban
- Auto-unbans after timeout

---

## 4. Dashboard API Authentication (Required)

### Generate secure API key:

```bash
# Generate 32-character random key
openssl rand -hex 32
```

### Add to VPS .env:

```bash
nano ~/MissionControl/trading/.env
```

Add:
```
DASHBOARD_API_KEY=your_generated_key_here
```

### Add to Vercel:

1. Go to Vercel Dashboard → Project Settings → Environment Variables
2. Add for **Production**:
   - Key: `TRADING_API_KEY`
   - Value: (same key as above)
3. Redeploy to activate

### Test authentication:

```bash
# Should fail (no key)
curl http://localhost:8000/api/dashboard

# Should succeed (with key)
curl -H "x-api-key: YOUR_KEY" http://localhost:8000/api/dashboard
```

---

## 5. Kill Switch PIN (Required)

Prevents accidental kill switch activation via dashboard.

### Add to VPS .env:

```bash
nano ~/MissionControl/trading/.env
```

Add:
```
KILL_SWITCH_PIN=1234  # Choose a 4-digit PIN
```

The dashboard will prompt for this PIN before activating the kill switch.

---

## 6. SSL/TLS for API (Optional but Recommended)

Use Caddy as reverse proxy for automatic HTTPS.

### Install Caddy:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### Configure subdomain:

Set DNS A record:
```
api.winzinvest.com → YOUR_VPS_IP
```

### Create Caddyfile:

```bash
sudo nano /etc/caddy/Caddyfile
```

```
api.winzinvest.com {
  reverse_proxy localhost:8000
  
  # Rate limiting
  rate_limit {
    zone dynamic {
      key {remote_host}
      events 100
      window 1m
    }
  }
}
```

### Restart Caddy:

```bash
sudo systemctl restart caddy
```

Now access via: `https://api.winzinvest.com`

Update Vercel env var:
```
TRADING_API_URL=https://api.winzinvest.com
```

---

## 7. Docker Security (IB Gateway)

### Container isolation:

The IB Gateway Docker container is already isolated:
- Runs as non-root user
- Limited port exposure (4001, 4002, 5900)
- Data volume mounted read/write only for `/root/Jts`

### Verify:

```bash
docker inspect ib-gateway | grep -A5 User
```

Should show: `"User": "1000:1000"` (ubuntu user)

---

## 8. Monitoring and Alerts

### Set up UptimeRobot:

1. Go to https://uptimerobot.com (free tier)
2. Add HTTP monitor:
   - URL: `http://YOUR_VPS_IP:8000/health`
   - Interval: 5 minutes
3. Add alert email

### Telegram alerts:

Already configured via `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`.

Test:
```bash
cd ~/MissionControl/trading/scripts
python3 test_telegram.py
```

---

## 9. Log Monitoring

### View service logs:

```bash
# Scheduler logs
sudo journalctl -u trading-scheduler -f

# API logs
sudo journalctl -u trading-api -f

# IB Gateway logs
docker logs -f ib-gateway
```

### Failed SSH attempts:

```bash
sudo journalctl -u sshd | grep "Failed password"
```

### Firewall logs:

```bash
sudo tail -f /var/log/ufw.log
```

---

## 10. Backup Encryption (Optional)

Encrypt backups before uploading to S3.

### Install GPG:

```bash
sudo apt install -y gnupg
```

### Generate key:

```bash
gpg --full-generate-key
# Choose RSA and RSA (default)
# Key size: 4096
# Expiration: 0 (does not expire)
# Name: Winzinvest Backups
# Email: your_email@example.com
```

### Encrypt backup script:

Edit `~/backup-trading-data.sh`:

```bash
# After creating tar.gz, encrypt it
gpg --encrypt --recipient "Winzinvest Backups" "$BACKUP_DIR/trading-$DATE.tar.gz"

# Upload encrypted version to S3
aws s3 cp "$BACKUP_DIR/trading-$DATE.tar.gz.gpg" "$S3_BUCKET/backups/"
```

### Decrypt when needed:

```bash
gpg --decrypt trading-20260328.tar.gz.gpg > trading-20260328.tar.gz
```

---

## Security Checklist

Before going live, verify:

- [ ] SSH password authentication disabled
- [ ] UFW firewall enabled and configured
- [ ] Fail2Ban installed and running
- [ ] Dashboard API key set in VPS `.env` and Vercel
- [ ] Kill switch PIN configured
- [ ] Port 4001 (IB Gateway) not exposed externally
- [ ] VNC port 5900 restricted to your IP only
- [ ] UptimeRobot monitoring configured
- [ ] Telegram alerts working
- [ ] Daily backups cron job active
- [ ] All systemd services running without errors

---

## Emergency Procedures

### If VPS is compromised:

1. **Immediately activate kill switch:**
   ```bash
   ssh ubuntu@VPS_IP
   cd ~/MissionControl/trading
   echo '{"active": true, "reason": "Security incident"}' > kill_switch.json
   ```

2. **Stop all trading services:**
   ```bash
   sudo systemctl stop trading-scheduler trading-api ib-gateway
   ```

3. **Rotate API keys:**
   - Generate new `DASHBOARD_API_KEY`
   - Update VPS `.env` and Vercel
   - Restart services

4. **Check for unauthorized access:**
   ```bash
   sudo last -a | head -20
   sudo journalctl -u sshd --since "24 hours ago"
   ```

5. **Review all recent trades:**
   ```bash
   cd ~/MissionControl/trading/logs
   tail -100 executions.json
   ```

---

## Questions?

If you encounter any security issues:
1. Check logs: `sudo journalctl -xe`
2. Verify firewall: `sudo ufw status verbose`
3. Test API auth: `curl -H "x-api-key: YOUR_KEY" http://localhost:8000/health`
