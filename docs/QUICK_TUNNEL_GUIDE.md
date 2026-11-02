# 🌐 Quick Tunnel Guide - 100% Free Production Flow

> **Zero Cost Production Setup** - Learn production deployment workflow without paying for domains or hosting.

---

## 📋 Overview

**Quick Tunnel** là giải pháp **hoàn toàn miễn phí** để expose local backend ra internet, phù hợp cho:
- ✅ Học production flow (deployment, monitoring, CI/CD)
- ✅ Demo projects với client
- ✅ Testing API từ mobile devices
- ✅ Prototype và MVP development

**Chi phí:** $0/tháng (không cần domain, không cần VPS)

---

## 🆚 So sánh với Named Tunnel

| Tính năng | Quick Tunnel (Bạn dùng) | Named Tunnel |
|-----------|-------------------------|--------------|
| **Domain** | ❌ Không cần | ✅ Cần domain ($10/năm) |
| **URL** | Random mỗi lần (`*.trycloudflare.com`) | Cố định |
| **Setup** | 1 command | 5+ steps |
| **Uptime** | Không đảm bảo | Đảm bảo (99%+) |
| **Chi phí** | **$0** | $10-15/năm |
| **Production** | ⚠️ Learning/Testing only | ✅ Production-ready |

**Kết luận:** Quick Tunnel hoàn hảo cho học tập và testing. Khi cần production thực sự, nên chuyển sang Named Tunnel.

---

## 🚀 Quick Start (3 phút)

### Bước 1: Start Backend
```bash
cd /path/to/ai-research-agent
make run-api

# Or manual:
uvicorn api.main:app --reload --port 8000
```

**Verify:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

### Bước 2: Start Tunnel (Tự động cập nhật .env.local)
```bash
make tunnel
```

**Script này sẽ:**
1. ✅ Stop tunnel cũ (nếu có)
2. ✅ Start tunnel mới → Lấy URL
3. ✅ Auto-update `web/.env.local` với URL mới
4. ✅ Verify tunnel hoạt động
5. ✅ Hiển thị instructions

**Output mẫu:**
```
╔════════════════════════════════════════════════════════════╗
║     Cloudflare Quick Tunnel - Auto Starter                 ║
║     100% Free - No Domain Required                         ║
╚════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Checking Dependencies
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ cloudflared installed: cloudflared version 2026.1.2
✓ Backend is running on http://localhost:8000

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Starting Cloudflare Quick Tunnel
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ Starting tunnel to http://localhost:8000...
ℹ Tunnel started (PID: 12345)
ℹ Waiting for tunnel URL...
✓ Tunnel URL: https://random-words-abc123.trycloudflare.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Updating Frontend Environment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ Backup created: web/.env.local.backup.20260201_160000
✓ Updated NEXT_PUBLIC_API_URL
✓ Updated NEXT_PUBLIC_API_BASE_URL

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Next Steps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tunnel is running!

📋 Summary:
  • Backend:  http://localhost:8000
  • Tunnel:   https://random-words-abc123.trycloudflare.com
  • Process:  PID 12345

🚀 Start Frontend:
  cd /path/to/ai-research-agent/web
  npm run dev

🧪 Test API:
  curl https://random-words-abc123.trycloudflare.com/health
```

### Bước 3: Start Frontend
```bash
# New terminal
cd web
npm run dev

# Frontend will use: https://random-words-abc123.trycloudflare.com
```

### Bước 4: Test
```bash
# Test từ bên ngoài (smartphone, máy khác, etc.)
curl https://random-words-abc123.trycloudflare.com/health

# Test từ Frontend
# Mở browser: http://localhost:3000
# Thử search query → API call sẽ đi qua tunnel
```

---

## 📱 Full Production Flow

### Development → Staging → Production (100% Free)

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL DEVELOPMENT                         │
├─────────────────────────────────────────────────────────────┤
│  Backend:   http://localhost:8000                           │
│  Frontend:  http://localhost:3000                           │
│  Database:  ChromaDB local                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
                    make tunnel
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    STAGING (Quick Tunnel)                    │
├─────────────────────────────────────────────────────────────┤
│  Backend:   https://random-123.trycloudflare.com            │
│  Frontend:  http://localhost:3000 (uses tunnel)             │
│  Database:  ChromaDB local                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
              Deploy Frontend to Vercel
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    PRODUCTION (Vercel + Tunnel)              │
├─────────────────────────────────────────────────────────────┤
│  Backend:   https://random-123.trycloudflare.com            │
│  Frontend:  https://your-app.vercel.app                     │
│  Database:  ChromaDB local (Mac running 24/7)               │
└─────────────────────────────────────────────────────────────┘
```

**Total Cost:** $2-5/month (electricity for Mac)

---

## 🛠️ Daily Workflow

### Morning (Start work)
```bash
# Terminal 1: Backend
make run-api

# Terminal 2: Tunnel (auto-updates .env.local)
make tunnel

# Terminal 3: Frontend
cd web && npm run dev
```

### During Development
- Code changes → Hot reload works normally
- API calls → Go through tunnel URL
- Database → Local ChromaDB

### Evening (Stop work)
```bash
# Stop tunnel
make stop-tunnel

# Stop backend (Ctrl+C)
# Stop frontend (Ctrl+C)
```

### Next Morning
```bash
# Restart everything
make tunnel  # URL sẽ khác, nhưng script tự động update .env.local

# Frontend tự động reload và dùng URL mới
```

---

## 🔧 Advanced Usage

### 1. Check Tunnel Status
```bash
# Show tunnel logs
tail -f /tmp/cloudflared-tunnel.log

# Get tunnel URL
grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared-tunnel.log | head -n1

# Check process
ps aux | grep cloudflared
```

### 2. Manual Tunnel (Without automation)
```bash
# If you want to start tunnel without auto-updating .env
cloudflared tunnel --url http://localhost:8000

# Then manually update web/.env.local:
NEXT_PUBLIC_API_URL=https://your-url.trycloudflare.com
```

### 3. Deploy to Vercel
```bash
cd web

# Update Vercel environment variable
vercel env add NEXT_PUBLIC_API_URL
# Enter: https://random-123.trycloudflare.com

# Deploy
vercel --prod
```

**⚠️ Important:** Mỗi khi restart tunnel, phải update Vercel env variable mới!

### 4. Permanent URL (Free alternatives)

Nếu bạn muốn URL cố định mà không mua domain:

**Option A: FreeDNS (Free subdomain)**
```bash
# 1. Register at freedns.afraid.org
# 2. Get free subdomain: myapp.mooo.com
# 3. Use with Named Tunnel (cần setup DNS)
```

**Option B: DuckDNS (Free dynamic DNS)**
```bash
# 1. Register at duckdns.org
# 2. Get free subdomain: myapp.duckdns.org
# 3. Use with Named Tunnel
```

**Option C: No-IP (Free hostname)**
```bash
# Similar to DuckDNS, free tier available
```

**Trade-off:**
- Quick Tunnel: 0 setup, URL thay đổi mỗi restart
- Free domain + Named Tunnel: 1x setup, URL cố định

---

## ⚠️ Limitations & Workarounds

### 1. URL Changes Every Restart

**Problem:** Mỗi lần restart tunnel, URL mới → Phải update Frontend

**Solution:** Script tự động update .env.local (đã có sẵn)

**For Vercel Production:**
```bash
# Create update script
cat > scripts/update_vercel_env.sh <<'EOF'
#!/bin/bash
TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared-tunnel.log | head -n1)
vercel env rm NEXT_PUBLIC_API_URL production -y
vercel env add NEXT_PUBLIC_API_URL production <<< "$TUNNEL_URL"
vercel --prod
EOF

chmod +x scripts/update_vercel_env.sh
```

### 2. No Uptime Guarantee

**Problem:** Cloudflare có thể kill tunnel bất cứ lúc nào

**Solution:** Monitor và auto-restart
```bash
# Add to crontab (check every 5 minutes)
*/5 * * * * /path/to/ai-research-agent/scripts/healthcheck_tunnel.sh
```

**Create healthcheck script:**
```bash
cat > scripts/healthcheck_tunnel.sh <<'EOF'
#!/bin/bash
TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared-tunnel.log | head -n1)
if ! curl -sf "$TUNNEL_URL/health" > /dev/null; then
    echo "Tunnel down, restarting..."
    make stop-tunnel
    make tunnel &
fi
EOF

chmod +x scripts/healthcheck_tunnel.sh
```

### 3. Performance

**Problem:** Tunnel adds latency (~50-200ms)

**Measurement:**
```bash
# Without tunnel (local)
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health

# With tunnel
curl -w "@curl-format.txt" -o /dev/null -s https://random.trycloudflare.com/health

# Create curl-format.txt:
echo "time_total: %{time_total}s\n" > curl-format.txt
```

**Optimization:**
- Use Cloudflare edge location gần Việt Nam (Singapore)
- Enable compression
- Cache static responses

---

## 📊 Monitoring

### 1. Tunnel Health
```bash
# Check tunnel is running
ps aux | grep cloudflared

# Check tunnel URL responds
TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared-tunnel.log | head -n1)
curl -I "$TUNNEL_URL/health"
```

### 2. Backend Performance
```bash
# Check backend logs
tail -f /tmp/backend.log

# Monitor requests
watch -n 1 'curl -s http://localhost:8000/health'
```

### 3. Frontend API Calls
```bash
# Browser DevTools → Network tab
# Filter: XHR/Fetch
# Check if API calls go to tunnel URL
```

---

## 🚀 Production Checklist

Trước khi "go live" với Quick Tunnel:

- [ ] Backend health endpoint responds
- [ ] Tunnel URL is accessible from internet
- [ ] Frontend .env.local has correct tunnel URL
- [ ] CORS configured for tunnel domain
- [ ] API rate limiting enabled
- [ ] Error logging setup (Sentry)
- [ ] Database backup automated
- [ ] Monitor tunnel uptime (healthcheck script)
- [ ] Document tunnel URL for team
- [ ] Setup auto-restart on tunnel failure

---

## 💡 Tips & Best Practices

### 1. Development
```bash
# Use different tunnels for different features
make tunnel  # Main backend
cloudflared tunnel --url http://localhost:8001  # Experimental API
```

### 2. Team Collaboration
```bash
# Share tunnel URL via Slack/Discord
echo "Backend API: $TUNNEL_URL" | pbcopy

# Team members can test immediately (no VPN needed)
curl https://your-tunnel.trycloudflare.com/health
```

### 3. Mobile Testing
```bash
# Scan QR code for easy access
qrencode -t UTF8 "https://your-tunnel.trycloudflare.com"

# Or use ngrok-style dashboard (coming soon)
```

### 4. CI/CD Integration
```yaml
# .github/workflows/test.yml
- name: Start tunnel for E2E tests
  run: |
    make tunnel &
    sleep 10
    TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared-tunnel.log | head -n1)
    export NEXT_PUBLIC_API_URL=$TUNNEL_URL
    npm run test:e2e
```

---

## 🆘 Troubleshooting

### Problem: Tunnel starts but URL not found

```bash
# Check logs
cat /tmp/cloudflared-tunnel.log

# Common causes:
# 1. Tunnel still initializing (wait 10-15 seconds)
# 2. Network issues (check internet connection)
# 3. Cloudflare API down (rare)

# Solution: Restart tunnel
make stop-tunnel && make tunnel
```

### Problem: Frontend still uses old URL

```bash
# Check .env.local
cat web/.env.local | grep NEXT_PUBLIC_API_URL

# Manually update if needed
vim web/.env.local

# Restart Next.js dev server
cd web && npm run dev
```

### Problem: Tunnel disconnects frequently

```bash
# Check for port conflicts
lsof -i :8000

# Check backend is stable
curl http://localhost:8000/health

# Enable auto-restart (cron job)
crontab -e
# Add: */5 * * * * /path/to/healthcheck_tunnel.sh
```

### Problem: CORS errors from tunnel URL

```bash
# Update backend CORS config
# api/main.py:

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.trycloudflare.com",  # Allow all Quick Tunnel URLs
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📚 Learn More

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Quick Tunnel Limitations](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/do-more-with-tunnels/quick-tunnels/)
- [Named Tunnel Setup](./CLOUDFLARE_TUNNEL_SETUP.md) (khi cần upgrade)

---

## 🎯 Summary

**Quick Tunnel = Production flow với $0 chi phí**

| Aspect | Quick Tunnel |
|--------|--------------|
| **Cost** | $0/month |
| **Setup Time** | 30 seconds |
| **URL Stability** | Changes per restart |
| **Uptime** | No guarantee |
| **Best For** | Learning, testing, demos |
| **Migration Path** | → Named Tunnel khi cần production |

**Commands:**
```bash
make tunnel        # Start tunnel + auto-update .env
make stop-tunnel   # Stop tunnel
make run-api       # Start backend
```

**Next step khi cần production thực:**
1. Mua domain ($10/năm) hoặc dùng free subdomain
2. Setup Named Tunnel (URL cố định)
3. Deploy frontend lên Vercel
4. Profit!

---

**Chi phí học production flow:** $0
**Kiến thức thu được:** Priceless ✨
