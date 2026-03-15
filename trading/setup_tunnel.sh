#!/usr/bin/env bash
#
# Setup Cloudflare Tunnel for remote Mission Control access
# =========================================================
#
# Gives you secure HTTPS access to the dashboard from any device (phone, tablet,
# laptop) without opening ports or exposing your IP. Free Cloudflare tier.
#
# What this does:
#   1. Installs cloudflared (if not already installed)
#   2. Authenticates with your Cloudflare account
#   3. Creates a named tunnel "mission-control"
#   4. Writes config to ~/.cloudflared/config.yml
#   5. Creates a DNS route (e.g. mc.yourdomain.com)
#
# Prerequisites:
#   - A Cloudflare account (free): https://dash.cloudflare.com/sign-up
#   - A domain added to Cloudflare (even a cheap $1 domain works)
#
# Usage:
#   ./setup_tunnel.sh                    # interactive setup
#   ./setup_tunnel.sh --domain mc.example.com   # specify domain
#
# After setup, add to start.sh or run:
#   cloudflared tunnel run mission-control
#

set -euo pipefail

TUNNEL_NAME="mission-control"
DASHBOARD_PORT="${DASHBOARD_PORT:-3001}"
CONFIG_DIR="$HOME/.cloudflared"
CONFIG_FILE="$CONFIG_DIR/config.yml"

echo ""
echo "  MISSION CONTROL — Remote Access Setup"
echo "  ======================================"
echo ""

# ── Step 1: Install cloudflared ──────────────────────────────────────────

if command -v cloudflared &>/dev/null; then
    echo "  [OK] cloudflared already installed: $(cloudflared --version 2>&1 | head -1)"
else
    echo "  [INSTALL] Installing cloudflared..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &>/dev/null; then
            brew install cloudflared
        else
            echo "  [INSTALL] Downloading cloudflared binary for macOS..."
            _arch="$(uname -m)"
            if [[ "$_arch" == "arm64" ]]; then
                _url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz"
            else
                _url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
            fi
            curl -fsSL "$_url" -o /tmp/cloudflared.tgz
            tar -xzf /tmp/cloudflared.tgz -C /tmp
            sudo mv /tmp/cloudflared /usr/local/bin/cloudflared
            sudo chmod +x /usr/local/bin/cloudflared
            rm -f /tmp/cloudflared.tgz
            echo "  [OK] cloudflared installed to /usr/local/bin/cloudflared"
        fi
    elif [[ "$OSTYPE" == "linux"* ]]; then
        if command -v apt-get &>/dev/null; then
            curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
            echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
            sudo apt-get update && sudo apt-get install -y cloudflared
        else
            echo "  [ERROR] Unsupported Linux distro. Install manually:"
            echo "         https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
            exit 1
        fi
    else
        echo "  [ERROR] Unsupported OS: $OSTYPE"
        exit 1
    fi
    echo "  [OK] cloudflared installed"
fi

# ── Step 2: Authenticate ────────────────────────────────────────────────

if [ ! -f "$CONFIG_DIR/cert.pem" ]; then
    echo ""
    echo "  [AUTH] Opening browser to authenticate with Cloudflare..."
    echo "         Select the domain you want to use for Mission Control."
    echo ""
    cloudflared tunnel login
    echo "  [OK] Authenticated"
else
    echo "  [OK] Already authenticated with Cloudflare"
fi

# ── Step 3: Create tunnel ───────────────────────────────────────────────

EXISTING_TUNNEL=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" || true)
if [ -n "$EXISTING_TUNNEL" ]; then
    echo "  [OK] Tunnel '$TUNNEL_NAME' already exists"
    TUNNEL_ID=$(echo "$EXISTING_TUNNEL" | awk '{print $1}')
else
    echo "  [CREATE] Creating tunnel '$TUNNEL_NAME'..."
    cloudflared tunnel create "$TUNNEL_NAME"
    TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
    echo "  [OK] Tunnel created: $TUNNEL_ID"
fi

# ── Step 4: Configure ───────────────────────────────────────────────────

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
    echo ""
    echo "  Enter the hostname for Mission Control (e.g. mc.yourdomain.com):"
    read -r DOMAIN
fi

if [ -z "$DOMAIN" ]; then
    echo "  [ERROR] Domain is required"
    exit 1
fi

mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_FILE" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $CONFIG_DIR/${TUNNEL_ID}.json

ingress:
  # Mission Control dashboard (Next.js)
  - hostname: $DOMAIN
    service: http://localhost:$DASHBOARD_PORT
  # Kill switch API
  - hostname: $DOMAIN
    path: /api/kill-switch
    service: http://localhost:$DASHBOARD_PORT
  # Catch-all (required by cloudflared)
  - service: http_status:404
EOF

echo "  [OK] Config written to $CONFIG_FILE"

# ── Step 5: DNS route ───────────────────────────────────────────────────

echo "  [DNS] Creating DNS route: $DOMAIN → tunnel $TUNNEL_NAME..."
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" 2>/dev/null || {
    echo "  [WARN] DNS route may already exist — check Cloudflare dashboard"
}

# ── Done ────────────────────────────────────────────────────────────────

echo ""
echo "  ✅ Setup complete!"
echo ""
echo "  To start the tunnel:"
echo "    cloudflared tunnel run $TUNNEL_NAME"
echo ""
echo "  Your dashboard will be at:"
echo "    https://$DOMAIN"
echo ""
echo "  This has been integrated into start.sh."
echo "  Run './start.sh restart' to enable."
echo ""
echo "  SECURITY: Add Cloudflare Access policy for authentication:"
echo "  https://one.dash.cloudflare.com → Access → Applications → Add"
echo "    - Name: Mission Control"
echo "    - Domain: $DOMAIN"
echo "    - Policy: Email — your@email.com"
echo ""

# Save domain for start.sh
echo "$DOMAIN" > "$CONFIG_DIR/mission-control-domain.txt"
