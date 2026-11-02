# 🏠 Local Backend + Vercel Frontend Deployment

> **Development/private demo only.** The canonical production path is
> [DEPLOYMENT.md](./DEPLOYMENT.md). A personal Mac and temporary tunnel do not
> satisfy production availability, identity, persistence, or rollback gates.

Complete guide to run backend locally and expose via Cloudflare Tunnel to Vercel frontend.

Set the same development-only `BACKEND_INTERNAL_TOKEN` in the backend and
Next.js server environments before starting them.

---

## 🎯 Why This Approach?

**Problems with Railway Free Tier:**
- ❌ Build timeout (~15 mins, need 25-30 mins)
- ❌ Large dependencies: sentence-transformers (2GB), torch, llama-index
- ❌ 512MB RAM limit (models need ~1.5GB)

**Solution: Run Backend Locally**
- ✅ No build timeout
- ✅ Unlimited RAM (use your Mac's 8-16GB)
- ✅ Fast development cycle
- ✅ FREE (just electricity ~$2-5/month)

---

## 📊 Architecture

```
┌──────────────┐
│    Users     │
└──────┬───────┘
       │
       ▼
┌─────────────────────┐
│  Vercel (Frontend)  │  ← Deploy here ($0/month)
│  Next.js + React    │
└─────────┬───────────┘
          │
          ▼
┌────────────────────────────┐
│  Cloudflare Tunnel (FREE)  │  ← Proxy to local
│  HTTPS + Auto-reconnect    │
└────────────┬───────────────┘
             │
             ▼
┌───────────────────────────┐
│  Your Mac (Backend)       │  ← Run locally
│  FastAPI + Models         │
│  http://localhost:8000    │
└───────────────────────────┘
```

---

## 🚀 Quick Start (15 minutes)

### Step 1: Setup Cloudflare Tunnel (5 mins)

```bash
# Run automated setup
./scripts/setup_cloudflare_tunnel.sh
```

**What it does:**
1. Installs `cloudflared` (if not installed)
2. Authenticates with Cloudflare
3. Creates tunnel named `ai-agent-backend`
4. Generates config file at `~/.cloudflared/config.yml`

**Manual setup:** See [CLOUDFLARE_TUNNEL_SETUP.md](./CLOUDFLARE_TUNNEL_SETUP.md)

---

### Step 2: Start Local Backend + Tunnel (2 mins)

```bash
# Start both backend and tunnel in tmux
./scripts/start_local_production.sh
```

**What it does:**
1. Starts FastAPI backend on port 8000
2. Starts Cloudflare tunnel
3. Runs both in tmux sessions (background)

**Get tunnel URL:**
```bash
# In tunnel window, copy the URL:
# https://random-words.trycloudflare.com
```

---

### Step 3: Deploy Frontend to Vercel (5 mins)

**Update environment variables:**

Edit `web/.env.local`:
```bash
NEXT_PUBLIC_API_BASE_URL=https://random-words.trycloudflare.com
NEXT_PUBLIC_API_URL=https://random-words.trycloudflare.com
```

**Deploy:**

```bash
cd web

# Option A: Vercel CLI
npm i -g vercel
vercel

# Option B: Vercel Dashboard
# 1. Go to https://vercel.com
# 2. Import GitHub repo
# 3. Root directory: web
# 4. Add environment variables:
#    NEXT_PUBLIC_API_BASE_URL=https://random-words.trycloudflare.com
#    NEXTAUTH_SECRET=your-secret (generate: openssl rand -base64 32)
#    NEXTAUTH_URL=https://your-app.vercel.app
# 5. Deploy!
```

---

### Step 4: Update Backend CORS (1 min)

Update `.env`:
```bash
CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

Restart backend:
```bash
# In tmux, switch to backend window (Ctrl+B then 0)
# Press Ctrl+C to stop
# Re-run: make run-api
```

---

## 🛠️ Daily Usage

### Start Everything

```bash
./scripts/start_local_production.sh
```

**tmux Commands:**
- **Attach:** `tmux attach -t ai-agent`
- **Detach:** `Ctrl+B` then `D`
- **Switch windows:** `Ctrl+B` then `0` (backend) or `1` (tunnel)
- **Kill session:** `tmux kill-session -t ai-agent`

---

### Stop Everything

```bash
tmux kill-session -t ai-agent
```

Or attach and manually stop:
```bash
tmux attach -t ai-agent
# Ctrl+C in each window
```

---

### View Logs

**Backend logs:**
```bash
tmux attach -t ai-agent
# Switch to window 0 (Ctrl+B then 0)
```

**Tunnel logs:**
```bash
tmux attach -t ai-agent
# Switch to window 1 (Ctrl+B then 1)
```

---

### Update Tunnel URL

Cloudflare free tunnel URLs (`*.trycloudflare.com`) **change on restart**.

**When tunnel restarts:**
1. Get new URL from tunnel logs
2. Update Vercel environment variables:
   - Vercel Dashboard → Settings → Environment Variables
   - Update `NEXT_PUBLIC_API_BASE_URL`
3. Redeploy Vercel

**Get permanent URL (optional):**
- Buy domain ($10/year)
- Route to Cloudflare
- Use custom subdomain

---

## 💰 Cost Comparison

| Approach | Monthly Cost | Pros | Cons |
|----------|--------------|------|------|
| **Local + Tunnel** | $2-5 (electricity) | ✅ No limits, ✅ Fast dev | ❌ Mac must run 24/7 |
| **Railway Free** | $0-5 (credit) | ✅ Auto-scaling | ❌ Build timeout, ❌ RAM limit |
| **Render Free** | $0 | ✅ 45min build | ❌ Spin down after 15 mins |
| **Railway Pro** | $20/month | ✅ No limits | ❌ Expensive |

**Recommendation:** Local + Tunnel for MVP, Railway Pro when scaling.

---

## 🔧 Troubleshooting

### Issue 1: Tunnel URL keeps changing

**Cause:** Free `*.trycloudflare.com` URLs are temporary

**Solutions:**
- **Quick fix:** Update Vercel env vars when URL changes
- **Permanent:** Buy domain + route to Cloudflare

---

### Issue 2: CORS errors

**Symptom:**
```
Access to fetch at 'https://tunnel-url...' has been blocked by CORS
```

**Solution:**

Update backend `.env`:
```bash
CORS_ORIGINS=https://your-app.vercel.app,https://tunnel-url.trycloudflare.com,http://localhost:3000
```

Restart backend.

---

### Issue 3: Tunnel disconnects

**Cause:** Mac sleeps or network issues

**Solutions:**
- **Prevent sleep:** System Settings → Energy Saver → Prevent sleep
- **Auto-reconnect:** Cloudflare tunnel auto-reconnects
- **Run as service:** See [CLOUDFLARE_TUNNEL_SETUP.md](./CLOUDFLARE_TUNNEL_SETUP.md) Step "Run as Background Service"

---

### Issue 4: "Tunnel not found"

**Solution:**
```bash
# Recreate tunnel
cloudflared tunnel delete ai-agent-backend
./scripts/setup_cloudflare_tunnel.sh
```

---

## 🎯 Alternative: ngrok (Simpler but Limited)

**If you want simpler setup (no Cloudflare account):**

```bash
# Install ngrok
brew install ngrok

# Start backend
make run-api

# Start ngrok
ngrok http 8000
```

**Copy ngrok URL:** `https://xxxx.ngrok.io`

**Limitations:**
- ❌ URL changes on every restart
- ❌ 2-hour session limit (free tier)
- ❌ Slower than Cloudflare

**Use ngrok for:** Quick testing only
**Use Cloudflare for:** Production/demo

---

## ✅ Production Checklist

- [ ] Cloudflare tunnel setup complete
- [ ] Backend running locally (test: `curl http://localhost:8000/health`)
- [ ] Tunnel running (test: `curl https://tunnel-url/health`)
- [ ] Frontend deployed to Vercel
- [ ] CORS configured in backend
- [ ] Environment variables updated in Vercel
- [ ] Mac set to prevent sleep
- [ ] Tunnel running as service (optional)
- [ ] Bookmark tunnel URL (it will change!)

---

## 📚 Documentation

- **Full Cloudflare Guide:** [CLOUDFLARE_TUNNEL_SETUP.md](./CLOUDFLARE_TUNNEL_SETUP.md)
- **Frontend deployment:** configure `web/` on Vercel with `NEXT_PUBLIC_API_URL`
  and `NEXT_PUBLIC_API_BASE_URL` pointing at the tunnel URL.
- **OpenRouter Setup:** [OPENROUTER_SETUP.md](./OPENROUTER_SETUP.md)

---

## 🚀 Next Steps

After everything is running:

1. **Test full flow:**
   - Visit `https://your-app.vercel.app`
   - Try a chat query
   - Verify backend logs in tmux

2. **Setup monitoring:**
   - Check tunnel uptime
   - Monitor Mac CPU/RAM usage
   - Set up alerts (optional)

3. **Plan scaling:**
   - When ready for 24/7 production → Upgrade to Railway Pro
   - Or keep local + use cloud GPU for models

---

**Cost:** $2-5/month (electricity)
**Performance:** No limits!
**Reliability:** 99% (if Mac stays on)

🎉 **Happy coding!**
