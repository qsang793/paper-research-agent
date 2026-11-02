#!/bin/bash

# Start Backend + Cloudflare Tunnel
# Usage: ./scripts/start_local_production.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Local Production Environment${NC}"
echo "==========================================="
echo ""

# Check if backend is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${YELLOW}⚠️  Port 8000 is already in use${NC}"
    echo "Killing existing process..."
    kill $(lsof -t -i:8000) 2>/dev/null || true
    sleep 2
fi

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}❌ cloudflared not found${NC}"
    echo "Run: ./scripts/setup_cloudflare_tunnel.sh"
    exit 1
fi

# Check if tunnel exists
TUNNEL_NAME="ai-agent-backend"
if ! cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo -e "${RED}❌ Tunnel '$TUNNEL_NAME' not found${NC}"
    echo "Run: ./scripts/setup_cloudflare_tunnel.sh"
    exit 1
fi

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${YELLOW}⚠️  tmux not found. Installing...${NC}"
    brew install tmux
fi

# Check if session already exists
if tmux has-session -t ai-agent 2>/dev/null; then
    echo -e "${YELLOW}⚠️  tmux session 'ai-agent' already exists${NC}"
    echo ""
    echo "Options:"
    echo "  1. Kill existing session and restart"
    echo "  2. Attach to existing session"
    echo "  3. Exit"
    echo ""
    read -p "Choose (1/2/3): " -n 1 -r
    echo ""

    if [[ $REPLY == "1" ]]; then
        tmux kill-session -t ai-agent
        echo -e "${GREEN}✅ Killed existing session${NC}"
    elif [[ $REPLY == "2" ]]; then
        echo -e "${GREEN}📎 Attaching to session...${NC}"
        echo "To detach: Ctrl+B then D"
        sleep 2
        tmux attach -t ai-agent
        exit 0
    else
        echo "Exiting..."
        exit 0
    fi
fi

# Create new tmux session
echo ""
echo -e "${GREEN}🎬 Starting tmux session...${NC}"
echo ""

# Start backend in window 0
tmux new-session -d -s ai-agent -n backend
tmux send-keys -t ai-agent:0 "cd $(pwd)" C-m
tmux send-keys -t ai-agent:0 "echo '🔧 Starting FastAPI backend...'" C-m
tmux send-keys -t ai-agent:0 "make run-api" C-m

# Wait for backend to start
sleep 5

# Create window 1 for tunnel
tmux new-window -t ai-agent:1 -n tunnel
tmux send-keys -t ai-agent:1 "cd $(pwd)" C-m
tmux send-keys -t ai-agent:1 "echo '🌐 Starting Cloudflare tunnel...'" C-m
tmux send-keys -t ai-agent:1 "cloudflared tunnel run $TUNNEL_NAME" C-m

# Wait for tunnel to start
sleep 3

echo ""
echo -e "${GREEN}✅ Environment Started!${NC}"
echo "======================="
echo ""
echo "📊 Services Running:"
echo "  - Backend:  http://localhost:8000"
echo "  - Tunnel:   Check tunnel window for URL"
echo ""
echo "🎮 tmux Commands:"
echo "  - Attach:   tmux attach -t ai-agent"
echo "  - Detach:   Ctrl+B then D"
echo "  - Switch:   Ctrl+B then 0 (backend) or 1 (tunnel)"
echo "  - Kill:     tmux kill-session -t ai-agent"
echo ""
echo "📋 Quick Actions:"
echo "  - View logs:      ./scripts/view_logs.sh"
echo "  - Stop services:  ./scripts/stop_local_production.sh"
echo "  - Check health:   curl http://localhost:8000/health"
echo ""
echo -e "${YELLOW}Attaching to tmux session in 3 seconds...${NC}"
echo "Press Ctrl+C to cancel"
sleep 3

tmux attach -t ai-agent
