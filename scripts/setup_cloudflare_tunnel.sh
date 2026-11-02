#!/bin/bash

# Cloudflare Tunnel Quick Setup Script
# Usage: ./scripts/setup_cloudflare_tunnel.sh

set -e

echo "🌐 Cloudflare Tunnel Quick Setup"
echo "=================================="
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "❌ cloudflared not found"
    echo "📦 Installing cloudflared..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install cloudflared
        else
            echo "Installing via direct download..."
            curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64 -o cloudflared
            chmod +x cloudflared
            sudo mv cloudflared /usr/local/bin/
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
        chmod +x cloudflared
        sudo mv cloudflared /usr/local/bin/
    else
        echo "❌ Unsupported OS. Please install manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        exit 1
    fi

    echo "✅ cloudflared installed"
fi

echo ""
echo "📋 Current cloudflared version:"
cloudflared --version

echo ""
echo "🔐 Step 1: Authenticate with Cloudflare"
echo "This will open your browser. Please login to Cloudflare."
echo ""
read -p "Press Enter to continue..."

cloudflared tunnel login

echo ""
echo "✅ Authentication complete"
echo ""

# Check if tunnel already exists
TUNNEL_NAME="ai-agent-backend"
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo "⚠️  Tunnel '$TUNNEL_NAME' already exists"
    read -p "Delete and recreate? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cloudflared tunnel delete "$TUNNEL_NAME"
        echo "✅ Deleted existing tunnel"
    else
        echo "Using existing tunnel"
    fi
fi

# Create tunnel if it doesn't exist
if ! cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo "🚇 Step 2: Creating tunnel..."
    cloudflared tunnel create "$TUNNEL_NAME"
    echo "✅ Tunnel created"
fi

# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo ""
echo "📝 Tunnel ID: $TUNNEL_ID"

# Create config file
CONFIG_DIR="$HOME/.cloudflared"
CONFIG_FILE="$CONFIG_DIR/config.yml"
CREDS_FILE="$CONFIG_DIR/$TUNNEL_ID.json"

echo ""
echo "📄 Step 3: Creating config file..."

mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_FILE" << EOF
tunnel: $TUNNEL_NAME
credentials-file: $CREDS_FILE

ingress:
  - service: http://localhost:8000
EOF

echo "✅ Config file created at: $CONFIG_FILE"

echo ""
echo "🚀 Setup Complete!"
echo "==================="
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Start your backend:"
echo "   cd $(pwd)"
echo "   make run-api"
echo ""
echo "2. In a new terminal, start the tunnel:"
echo "   cloudflared tunnel run $TUNNEL_NAME"
echo ""
echo "3. Copy the tunnel URL from the output (https://xxx.trycloudflare.com)"
echo ""
echo "4. Update web/.env.local:"
echo "   NEXT_PUBLIC_API_BASE_URL=https://your-tunnel-url.trycloudflare.com"
echo ""
echo "5. Deploy frontend to Vercel with the tunnel URL"
echo ""
echo "📚 Full documentation: docs/CLOUDFLARE_TUNNEL_SETUP.md"
echo ""
