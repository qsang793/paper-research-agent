#!/bin/bash

# =============================================================================
# Quick Tunnel Starter with Auto URL Update
# =============================================================================
# Starts Cloudflare Quick Tunnel and automatically updates Frontend .env.local
# with the new tunnel URL. No domain required, 100% free.
#
# Usage: ./scripts/start_quick_tunnel.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT=8000
ENV_FILE="$PROJECT_ROOT/web/.env.local"
TUNNEL_LOG="/tmp/cloudflared-tunnel.log"
TUNNEL_PID_FILE="/tmp/cloudflared-tunnel.pid"

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

check_dependencies() {
    print_header "Checking Dependencies"

    # Check cloudflared
    if ! command -v cloudflared &> /dev/null; then
        print_error "cloudflared is not installed"
        echo ""
        echo "Install with:"
        echo "  brew install cloudflared"
        exit 1
    fi
    print_success "cloudflared installed: $(cloudflared --version | head -n1)"

    # Check if backend is running
    if ! curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
        print_warning "Backend is not running on port $BACKEND_PORT"
        echo ""
        echo "Start backend first:"
        echo "  cd $PROJECT_ROOT"
        echo "  make run-api"
        echo ""
        read -p "Do you want to continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "Backend is running on http://localhost:$BACKEND_PORT"
    fi

    echo ""
}

# =============================================================================
# Stop Existing Tunnel
# =============================================================================

stop_existing_tunnel() {
    print_header "Stopping Existing Tunnel"

    if [ -f "$TUNNEL_PID_FILE" ]; then
        OLD_PID=$(cat "$TUNNEL_PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            print_info "Stopping tunnel process (PID: $OLD_PID)..."
            kill "$OLD_PID" 2>/dev/null || true
            sleep 2
            print_success "Old tunnel stopped"
        fi
        rm -f "$TUNNEL_PID_FILE"
    fi

    # Kill any remaining cloudflared processes
    pkill -f "cloudflared tunnel" 2>/dev/null || true
    sleep 1

    echo ""
}

# =============================================================================
# Start Tunnel and Extract URL
# =============================================================================

start_tunnel() {
    print_header "Starting Cloudflare Quick Tunnel"

    # Clear old log
    rm -f "$TUNNEL_LOG"

    # Start tunnel in background
    print_info "Starting tunnel to http://localhost:$BACKEND_PORT..."
    cloudflared tunnel --url "http://localhost:$BACKEND_PORT" > "$TUNNEL_LOG" 2>&1 &
    TUNNEL_PID=$!
    echo $TUNNEL_PID > "$TUNNEL_PID_FILE"

    print_info "Tunnel started (PID: $TUNNEL_PID)"
    print_info "Waiting for tunnel URL (this may take 5-10 seconds)..."

    # Wait for URL to appear in log (max 30 seconds)
    for i in {1..30}; do
        if [ -f "$TUNNEL_LOG" ]; then
            TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -n1)
            if [ -n "$TUNNEL_URL" ]; then
                break
            fi
        fi
        sleep 1
        echo -n "."
    done
    echo ""

    if [ -z "$TUNNEL_URL" ]; then
        print_error "Failed to extract tunnel URL"
        echo ""
        echo "Log contents:"
        cat "$TUNNEL_LOG"
        kill $TUNNEL_PID 2>/dev/null || true
        rm -f "$TUNNEL_PID_FILE"
        exit 1
    fi

    print_success "Tunnel URL: $TUNNEL_URL"
    echo ""
}

# =============================================================================
# Update Frontend Environment
# =============================================================================

update_env_file() {
    print_header "Updating Frontend Environment"

    if [ ! -f "$ENV_FILE" ]; then
        print_error "Frontend .env.local not found: $ENV_FILE"
        exit 1
    fi

    # Backup current .env.local
    BACKUP_FILE="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$ENV_FILE" "$BACKUP_FILE"
    print_info "Backup created: $BACKUP_FILE"

    # Update or add NEXT_PUBLIC_API_URL
    if grep -q "^NEXT_PUBLIC_API_URL=" "$ENV_FILE"; then
        # Update existing
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=$TUNNEL_URL|" "$ENV_FILE"
        else
            sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=$TUNNEL_URL|" "$ENV_FILE"
        fi
        print_success "Updated NEXT_PUBLIC_API_URL"
    else
        # Add new
        echo "NEXT_PUBLIC_API_URL=$TUNNEL_URL" >> "$ENV_FILE"
        print_success "Added NEXT_PUBLIC_API_URL"
    fi

    # Also update NEXT_PUBLIC_API_BASE_URL if exists
    if grep -q "^NEXT_PUBLIC_API_BASE_URL=" "$ENV_FILE"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=$TUNNEL_URL|" "$ENV_FILE"
        else
            sed -i "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=$TUNNEL_URL|" "$ENV_FILE"
        fi
        print_success "Updated NEXT_PUBLIC_API_BASE_URL"
    fi

    echo ""
    print_info "Frontend environment updated:"
    echo "  NEXT_PUBLIC_API_URL=$TUNNEL_URL"
    echo ""
}

# =============================================================================
# Verify Connection
# =============================================================================

verify_tunnel() {
    print_header "Verifying Tunnel Connection"

    print_info "Testing tunnel URL: $TUNNEL_URL/health"

    sleep 3  # Wait for tunnel to stabilize

    if curl -sf "$TUNNEL_URL/health" > /dev/null; then
        print_success "Tunnel is working! Backend is accessible via public URL"
        echo ""
        RESPONSE=$(curl -s "$TUNNEL_URL/health")
        echo "Response: $RESPONSE"
    else
        print_warning "Tunnel URL is not responding yet (this is normal, may take a minute)"
        print_info "Check manually: curl $TUNNEL_URL/health"
    fi

    echo ""
}

# =============================================================================
# Print Instructions
# =============================================================================

print_instructions() {
    print_header "Next Steps"

    echo -e "${GREEN}Tunnel is running!${NC}"
    echo ""
    echo "📋 Summary:"
    echo "  • Backend:  http://localhost:$BACKEND_PORT"
    echo "  • Tunnel:   $TUNNEL_URL"
    echo "  • Process:  PID $TUNNEL_PID"
    echo ""
    echo "🚀 Start Frontend:"
    echo "  cd $PROJECT_ROOT/web"
    echo "  npm run dev"
    echo ""
    echo "  Frontend will automatically use tunnel URL from .env.local"
    echo ""
    echo "🧪 Test API:"
    echo "  curl $TUNNEL_URL/health"
    echo ""
    echo "🛑 Stop Tunnel:"
    echo "  kill $TUNNEL_PID"
    echo "  # or run this script again (auto-stops old tunnel)"
    echo ""
    echo "⚠️  Important:"
    echo "  • Tunnel URL changes every restart"
    echo "  • This script auto-updates .env.local each time"
    echo "  • Not suitable for production (use only for learning/testing)"
    echo ""
    echo "📝 Logs:"
    echo "  tail -f $TUNNEL_LOG"
    echo ""

    print_header "Tunnel Running - Press Ctrl+C to stop"

    # Wait for user interrupt
    tail -f "$TUNNEL_LOG"
}

# =============================================================================
# Main
# =============================================================================

main() {
    clear

    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║     Cloudflare Quick Tunnel - Auto Starter                 ║"
    echo "║     100% Free - No Domain Required                         ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""

    check_dependencies
    stop_existing_tunnel
    start_tunnel
    update_env_file
    verify_tunnel
    print_instructions
}

# Handle Ctrl+C
trap 'echo ""; print_info "Stopping tunnel..."; kill $TUNNEL_PID 2>/dev/null || true; rm -f "$TUNNEL_PID_FILE"; exit 0' INT TERM

main
