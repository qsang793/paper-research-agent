# 🚀 Quick Tunnel Deployment - TL;DR

**100% FREE production flow cho học tập - Không cần mua domain**

---

## ⚡ 30-Second Setup

```bash
# 1. Start Backend
make run-api

# 2. Start Tunnel (auto-updates .env.local)
make tunnel

# 3. Start Frontend (new terminal)
cd web && npm run dev

# Done! API accessible via: https://random-123.trycloudflare.com
```

---

## 📋 Full Production Workflow

### Morning Routine
```bash
# Terminal 1: Backend
cd <repo-root>
source .venv/bin/activate
make run-api

# Terminal 2: Tunnel
make tunnel
# Copy URL: https://random-words-123.trycloudflare.com

# Terminal 3: Frontend
cd web
npm run dev
# Opens: http://localhost:3000 (uses tunnel URL automatically)
```

### Deploy to Vercel
```bash
cd web

# Set tunnel URL as env variable
vercel env add NEXT_PUBLIC_API_URL production
# Paste: https://random-words-123.trycloudflare.com

# Deploy
vercel --prod
```

**⚠️ Important:** Tunnel URL thay đổi mỗi restart. Cần update Vercel env variable nếu restart tunnel!

---

## 🔧 Makefile Commands

```bash
make tunnel       # Start Quick Tunnel (auto-updates web/.env.local)
make stop-tunnel  # Stop Quick Tunnel
make run-api      # Start Backend (port 8000)
make run-web      # Start Frontend (port 3000)
make dev          # Start Backend + Frontend (no tunnel)
```

---

## 🎯 Architecture

```
┌─────────────────────────────────────────────┐
│  Frontend (Vercel or localhost:3000)        │
│  - Next.js 16 + React 19                   │
│  - Env: NEXT_PUBLIC_API_URL = tunnel URL   │
└─────────────────────────────────────────────┘
                    ↓ HTTPS
┌─────────────────────────────────────────────┐
│  Cloudflare Quick Tunnel                    │
│  https://random-123.trycloudflare.com       │
│  - Free                                     │
│  - No domain needed                         │
│  - URL changes per restart                  │
└─────────────────────────────────────────────┘
                    ↓ HTTP
┌─────────────────────────────────────────────┐
│  Backend (localhost:8000)                   │
│  - FastAPI                                  │
│  - LlamaIndex + ChromaDB                    │
│  - OpenRouter API (free models)             │
└─────────────────────────────────────────────┘
```

**Total Cost:** $0/month (hoặc $2-5/month điện nếu chạy Mac 24/7)

---

## ✅ Advantages

- ✅ **100% FREE** - Không mất chi phí
- ✅ **No domain needed** - Không cần mua domain
- ✅ **Auto-setup** - Script tự động update .env.local
- ✅ **HTTPS** - SSL/TLS free từ Cloudflare
- ✅ **Global CDN** - Edge locations worldwide
- ✅ **Zero config** - Chạy 1 command là xong

---

## ⚠️ Limitations

- ⚠️ **URL thay đổi mỗi restart** - Cần update Frontend env
- ⚠️ **Không uptime guarantee** - Cloudflare có thể kill tunnel
- ⚠️ **Not for production** - Chỉ nên dùng cho learning/testing
- ⚠️ **Latency** - Thêm ~50-200ms qua tunnel

**Solution:** Dùng Quick Tunnel để học, upgrade lên Named Tunnel khi cần production thực sự.

---

## 📊 When to Upgrade

| Use Case | Quick Tunnel | Named Tunnel |
|----------|--------------|--------------|
| Learning | ✅ Perfect | ❌ Overkill |
| Testing/Demo | ✅ Great | ✅ Better |
| Production | ❌ Not recommended | ✅ Required |
| Cost | $0 | $10/year (domain) |

**Migration:** Khi project chuyển sang production, mua domain ($10/năm) và setup Named Tunnel (30 phút).

---

## 🧪 Verify Setup

```bash
# 1. Check backend
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# 2. Check tunnel
TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared-tunnel.log | head -n1)
curl "$TUNNEL_URL/health"
# Expected: {"status":"healthy"}

# 3. Check frontend .env
cat web/.env.local | grep NEXT_PUBLIC_API_URL
# Expected: NEXT_PUBLIC_API_URL=https://random-123.trycloudflare.com

# 4. Test from browser
open http://localhost:3000
# Try a search query, check Network tab for API calls to tunnel URL
```

---

## 🆘 Quick Troubleshooting

**Problem:** Tunnel URL not responding
```bash
make stop-tunnel && make tunnel  # Restart tunnel
```

**Problem:** Frontend uses old URL
```bash
cat web/.env.local  # Check NEXT_PUBLIC_API_URL
cd web && npm run dev  # Restart Next.js
```

**Problem:** CORS errors
```bash
# Check .env has wildcard CORS
cat .env | grep CORS_ORIGINS
# Expected: https://*.trycloudflare.com
```

---

## 📚 Full Documentation

- **Quick Tunnel Guide:** [docs/QUICK_TUNNEL_GUIDE.md](./QUICK_TUNNEL_GUIDE.md) (Đầy đủ chi tiết)
- **Named Tunnel Setup:** [docs/CLOUDFLARE_TUNNEL_SETUP.md](./CLOUDFLARE_TUNNEL_SETUP.md) (Khi cần upgrade)
- **Local Backend Deployment:** [docs/LOCAL_BACKEND_DEPLOYMENT.md](./LOCAL_BACKEND_DEPLOYMENT.md)

---

## 💡 Pro Tips

1. **Bookmark tunnel URL:** Mỗi lần restart, URL mới → Bookmark lại
2. **Use tmux:** Run tunnel in background với tmux (xem LOCAL_BACKEND_DEPLOYMENT.md)
3. **Monitor logs:** `tail -f /tmp/cloudflared-tunnel.log`
4. **Auto-restart:** Setup cron job để auto-restart nếu tunnel die

---

**Summary:** Quick Tunnel = Production workflow với $0 chi phí. Perfect cho learning! 🎓✨
