# 🚀 Quick Deployment Guide

Deploy your AI Research Agent to production in 15 minutes.

## 📋 Stack Overview

```
┌─────────────────────────────────────────────────────┐
│                    PRODUCTION                        │
├─────────────────────────────────────────────────────┤
│  Frontend (Vercel)    │  Backend (Local Mac)        │
│  - Next.js 16         │  - FastAPI                  │
│  - React 19           │  - LlamaIndex               │
│  - Tailwind CSS v4    │  - ChromaDB                 │
│  - Auth (Supabase)    │  - OpenRouter API           │
└─────────────────────────────────────────────────────┘
                          ↕
              Cloudflare Tunnel (FREE)
              Expose local to internet
```

**Cost:** $2-5/month (electricity for Mac running 24/7)

---

## ⚡ Quick Start (15 minutes)

### Step 1: Backend (Local + Cloudflare Tunnel) - 5 mins

1. **Setup Cloudflare Tunnel:**

   ```bash
   ./scripts/setup_cloudflare_tunnel.sh
   ```

   This will:
   - Install `cloudflared` (if not installed)
   - Authenticate with Cloudflare
   - Create tunnel named `ai-agent-backend`

2. **Start Backend + Tunnel:**

   ```bash
   ./scripts/start_local_production.sh
   ```

   This will:
   - Start FastAPI backend on port 8000
   - Start Cloudflare tunnel
   - Run both in tmux sessions (background)

3. **Copy Tunnel URL:**
   - Attach to tmux: `tmux attach -t ai-agent`
   - Switch to tunnel window: `Ctrl+B` then `1`
   - Copy URL like: `https://random-words.trycloudflare.com`

**Verify:**
```bash
curl https://random-words.trycloudflare.com/health
# Should return: {"status": "healthy"}
```

📖 **Detailed guide:** [docs/LOCAL_BACKEND_DEPLOYMENT.md](./LOCAL_BACKEND_DEPLOYMENT.md)

---

### Step 2: Frontend (Vercel) - 5 mins

1. **Create Vercel account** → [vercel.com](https://vercel.com)

2. **Import project:**
   - Click "Add New Project"
   - Import from GitHub
   - Select repository: `ai_agent`
   - Root directory: `web`

3. **Configure environment variables:**

   ```bash
   NEXT_PUBLIC_API_URL=https://random-words.trycloudflare.com
   NEXT_PUBLIC_API_BASE_URL=https://random-words.trycloudflare.com
   NEXTAUTH_SECRET=generate-with-openssl-rand-base64-32
   NEXTAUTH_URL=https://your-app.vercel.app
   NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-key
   ```

   Replace `random-words.trycloudflare.com` with your actual tunnel URL from Step 1.

4. **Deploy:**
   - Vercel auto-builds
   - Get URL: `https://your-app.vercel.app`

**Verify:**
Open `https://your-app.vercel.app` in browser

📖 **Detailed guide:** [docs/VERCEL_DEPLOYMENT.md](./VERCEL_DEPLOYMENT.md)

---

### Step 3: Authentication (Supabase) - 5 mins

1. **Create Supabase project** → [supabase.com](https://supabase.com)

2. **Enable authentication:**
   - Dashboard → Authentication → Providers
   - Enable Email/Password
   - Optional: Enable Google OAuth

3. **Get credentials:**
   - Settings → API
   - Copy `URL` and `anon key`

4. **Update Vercel environment:**
   - Add `NEXT_PUBLIC_SUPABASE_URL`
   - Add `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - Redeploy

📖 **Detailed guide:** [docs/SUPABASE_SETUP.md](./SUPABASE_SETUP.md)

---

### Step 4: Update CORS (Backend) - 1 min

Now that you have Vercel URL, update backend CORS:

1. **Update `.env` file:**

   ```bash
   CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000
   ```

2. **Restart backend:**

   ```bash
   # In tmux, switch to backend window (Ctrl+B then 0)
   # Press Ctrl+C to stop
   # Re-run: make run-api
   ```

---

## ✅ Verification Checklist

After deployment, verify everything works:

- [ ] Backend health check: `curl https://your-tunnel-url.trycloudflare.com/health`
- [ ] API docs accessible: `https://your-tunnel-url.trycloudflare.com/docs`
- [ ] Frontend loads: `https://your-app.vercel.app`
- [ ] User can sign up/login (Supabase)
- [ ] Chat functionality works
- [ ] CORS allows frontend to call backend
- [ ] Mac is set to prevent sleep (System Settings → Energy Saver)
- [ ] tmux session is running: `tmux ls`

---

## 🔧 Environment Variables Reference

### Backend (Local)

**Required:**

```bash
OPENROUTER_API_KEY=your-openrouter-key    # Get free at: https://openrouter.ai/keys
LLM_BACKEND=openrouter
OPENROUTER_MODEL=xiaomi/mimo-v2-flash:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EMBED_MODEL=intfloat/e5-base-v2
CHROMA_PATH=./chroma
CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

**Optional (Recommended):**

```bash
PRELOAD_MODELS=true
ENABLE_RERANKING=true
RERANK_MODEL=BAAI/bge-reranker-base
LOG_LEVEL=INFO
```

**Full list:** [.env.example](.env.example)

### Frontend (Vercel)

**Required:**

```bash
NEXT_PUBLIC_API_URL=https://random-words.trycloudflare.com
NEXT_PUBLIC_API_BASE_URL=https://random-words.trycloudflare.com
NEXTAUTH_SECRET=your-secret-32-chars
NEXTAUTH_URL=https://your-app.vercel.app
NEXT_PUBLIC_SUPABASE_URL=https://xyz.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-key
```

**Full list:** [web/.env.example](../web/.env.example)

---

## 💰 Cost Breakdown

| Service | Plan | Cost | Usage |
|---------|------|------|-------|
| **Cloudflare Tunnel** | Free | $0/month | Backend proxy |
| **Vercel** | Hobby (Free) | $0/month | Frontend |
| **Supabase** | Free tier | $0/month | Auth + DB |
| **OpenRouter** | Free tier | $0/month | LLM calls |
| **Electricity** | Mac 24/7 | $2-5/month | Backend hosting |
| **Total** | | **$2-5/month** | Full stack |

**Free tier limits:**
- Cloudflare Tunnel: Unlimited bandwidth, no time limits
- Vercel: 100GB bandwidth, unlimited deployments
- Supabase: 50,000 monthly active users
- OpenRouter: Free models available (with rate limits)

---

## 🛠️ Troubleshooting

### Common Issues

**1. CORS Error**

```
Access to fetch at 'https://tunnel-url...' from origin 'https://vercel-url...' has been blocked by CORS
```

**Fix:** Update `CORS_ORIGINS` in `.env` to include Vercel URL, then restart backend

**2. Tunnel URL keeps changing**

**Cause:** Free `*.trycloudflare.com` URLs are temporary

**Fix:** Update Vercel environment variables with new tunnel URL when it changes

**3. Tunnel disconnects**

**Cause:** Mac sleeps or network issues

**Fix:**
- Prevent Mac sleep: System Settings → Energy Saver → Prevent sleep
- Cloudflare tunnel auto-reconnects
- Run as service (see [CLOUDFLARE_TUNNEL_SETUP.md](./CLOUDFLARE_TUNNEL_SETUP.md))

**4. Backend not responding**

```
Connection refused
```

**Fix:** Check if backend is running: `curl http://localhost:8000/health`

### Debug Tools

**Check tmux sessions:**

```bash
tmux ls
tmux attach -t ai-agent
```

**View backend logs:**

```bash
# In tmux, switch to backend window (Ctrl+B then 0)
```

**View tunnel logs:**

```bash
# In tmux, switch to tunnel window (Ctrl+B then 1)
```

**Test backend locally:**

```bash
make run-api
curl http://localhost:8000/health
```

**Test frontend locally:**

```bash
cd web
npm run dev
```

---

## 📚 Additional Resources

- [Local Backend Deployment Guide](./LOCAL_BACKEND_DEPLOYMENT.md) - Detailed backend + tunnel setup
- [Cloudflare Tunnel Setup](./CLOUDFLARE_TUNNEL_SETUP.md) - Complete tunnel guide
- [OpenRouter Setup](./OPENROUTER_SETUP.md) - Free LLM API setup
- [Vercel Deployment Guide](./VERCEL_DEPLOYMENT.md) - Frontend deployment
- [Supabase Setup Guide](./SUPABASE_SETUP.md) - Authentication setup
- [Environment Variables](../.env.example) - Complete env vars list

---

## 🚀 Next Steps

After successful deployment:

1. **Permanent Tunnel URL (Optional):**
   - Buy domain ($10/year)
   - Route to Cloudflare
   - Use custom subdomain instead of `*.trycloudflare.com`

2. **Custom Domain:**
   - Vercel: Add custom domain in settings

3. **Monitoring:**
   - Setup Sentry for error tracking
   - Monitor Mac CPU/RAM usage
   - Check tunnel uptime

4. **Performance:**
   - Enable caching
   - Optimize model loading
   - Add CDN for static assets

5. **Security:**
   - Setup rate limiting
   - Enable HTTPS only (already enforced by Cloudflare)
   - Rotate API keys regularly

6. **Reliability:**
   - Run tunnel as background service (launchd on macOS)
   - Set Mac to prevent sleep
   - Setup alerts for downtime

---

**Cost:** $2-5/month (electricity)
**Performance:** No limits!
**Reliability:** 99% (if Mac stays on)

**Need help?** Open an issue on GitHub or check the troubleshooting guides.
