# 🌐 Cloudflare Tunnel Setup Guide

Deploy Frontend to Vercel, run Backend locally, expose via Cloudflare Tunnel.

---

## 📋 Prerequisites

- [ ] Vercel account (for frontend)
- [ ] Cloudflare account (free) - [Sign up](https://dash.cloudflare.com/sign-up)
- [ ] Backend running locally on your Mac

---

## 🚀 Setup (10 minutes)

### Step 1: Install Cloudflare Tunnel CLI

**On macOS:**
```bash
brew install cloudflared

# Verify installation
cloudflared --version
```

**Alternative (direct download):**
```bash
# Download
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64 -o cloudflared

# Make executable
chmod +x cloudflared

# Move to PATH
sudo mv cloudflared /usr/local/bin/
```

---

### Step 2: Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

**What happens:**
1. Opens browser
2. Login to Cloudflare
3. Select a domain (or use free *.trycloudflare.com)
4. Cert file saved to `~/.cloudflared/cert.pem`

---

### Step 3: Create Tunnel

```bash
# Create tunnel named "ai-agent-backend"
cloudflared tunnel create ai-agent-backend
```

**Output:**
```
Created tunnel ai-agent-backend with id: 12345678-abcd-1234-abcd-123456789abc
```

**Save tunnel ID!** You'll need it later.

---

### Step 4: Create Config File

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: ai-agent-backend
credentials-file: /Users/YOUR_USERNAME/.cloudflared/12345678-abcd-1234-abcd-123456789abc.json

ingress:
  - hostname: ai-agent-backend.trycloudflare.com
    service: http://localhost:8000
  - service: http_status:404
```

**Replace:**
- `YOUR_USERNAME` with your Mac username
- `12345678-abcd-1234-abcd-123456789abc` with your tunnel ID
- `ai-agent-backend.trycloudflare.com` with your desired subdomain

**Get Mac username:**
```bash
echo $USER
```

---

### Step 5: Route DNS

```bash
cloudflared tunnel route dns ai-agent-backend ai-agent-backend.trycloudflare.com
```

**Or use auto-assigned URL (easier):**

Skip this step and Cloudflare will auto-assign: `https://random-words.trycloudflare.com`

---

### Step 6: Start Backend Locally

```bash
# Terminal 1: Start FastAPI backend
cd ~/Documents/Study/ai_agent
make run-api

# Or manually:
uvicorn api.main:app --reload --port 8000
```

**Verify:**
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

---

### Step 7: Start Tunnel

```bash
# Terminal 2: Start Cloudflare tunnel
cloudflared tunnel run ai-agent-backend
```

**Output:**
```
2026-01-30 10:00:00 INF Starting tunnel ai-agent-backend
2026-01-30 10:00:01 INF Registered tunnel connection
2026-01-30 10:00:01 INF +----------------------------+
2026-01-30 10:00:01 INF |  Your quick tunnel URL:    |
2026-01-30 10:00:01 INF |  https://random-words.trycloudflare.com  |
2026-01-30 10:00:01 INF +----------------------------+
```

**Copy the URL!** Example: `https://random-words.trycloudflare.com`

---

### Step 8: Test Tunnel

```bash
# Test from another terminal
curl https://random-words.trycloudflare.com/health
```

**Expected:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-30T..."
}
```

---

### Step 9: Update Frontend Environment Variables

Update [web/.env.local](../web/.env.local):

```bash
NEXT_PUBLIC_API_BASE_URL=https://random-words.trycloudflare.com
NEXT_PUBLIC_API_URL=https://random-words.trycloudflare.com
```

---

### Step 10: Deploy Frontend to Vercel

```bash
cd web
npm run build  # Test build locally first

# Deploy to Vercel
vercel

# Or via Vercel Dashboard:
# 1. Go to https://vercel.com
# 2. Import GitHub repository
# 3. Add environment variables:
#    NEXT_PUBLIC_API_BASE_URL=https://random-words.trycloudflare.com
# 4. Deploy!
```

---

## 🔧 Production Setup (Keep Tunnel Running)

### Option A: Run as Background Service (macOS)

Create `~/Library/LaunchAgents/com.cloudflare.tunnel.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>ai-agent-backend</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/cloudflared.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/cloudflared.out</string>
</dict>
</plist>
```

**Load service:**
```bash
launchctl load ~/Library/LaunchAgents/com.cloudflare.tunnel.plist

# Check status
launchctl list | grep cloudflare
```

**Unload service:**
```bash
launchctl unload ~/Library/LaunchAgents/com.cloudflare.tunnel.plist
```

---

### Option B: Run with tmux (Simple)

```bash
# Install tmux
brew install tmux

# Start tmux session
tmux new -s backend

# Inside tmux:
# Terminal 1 (Backend)
make run-api

# Split window (Ctrl+B then ")
# Terminal 2 (Tunnel)
cloudflared tunnel run ai-agent-backend

# Detach from tmux: Ctrl+B then D
# Reattach: tmux attach -t backend
```

---

## 💰 Cost Comparison

| Service | Cost | Note |
|---------|------|------|
| **Cloudflare Tunnel** | $0/month | ✅ FREE, unlimited |
| **Vercel (Frontend)** | $0/month | FREE tier |
| **Electricity** | ~$2-5/month | Mac running 24/7 |
| **TOTAL** | ~$2-5/month | 🎉 |

vs **Railway ($5/month)** + electricity ($0) = $5/month

---

## 🐛 Troubleshooting

### Issue 1: "Tunnel not found"
**Solution:**
```bash
# List tunnels
cloudflared tunnel list

# Delete and recreate
cloudflared tunnel delete ai-agent-backend
cloudflared tunnel create ai-agent-backend
```

### Issue 2: "Connection refused"
**Solution:**
- Check backend is running: `curl http://localhost:8000/health`
- Check port in config.yml matches backend port

### Issue 3: "CORS errors"
**Solution:**

Update backend `.env`:
```bash
CORS_ORIGINS=https://your-app.vercel.app,https://random-words.trycloudflare.com,http://localhost:3000
```

Restart backend.

---

## 📊 Monitoring

**Check tunnel status:**
```bash
cloudflared tunnel info ai-agent-backend
```

**View logs:**
```bash
# If running as service
tail -f /tmp/cloudflared.out
tail -f /tmp/cloudflared.err

# If running in terminal
# Logs appear in terminal
```

---

## 🔄 Update Tunnel URL

When tunnel URL changes (trycloudflare.com URLs are temporary):

1. **Get new URL** from tunnel logs
2. **Update Vercel environment variables:**
   - Vercel Dashboard → Your Project → Settings → Environment Variables
   - Update `NEXT_PUBLIC_API_BASE_URL`
   - Redeploy: Deployments → Click "..." → Redeploy

---

## 🎯 Permanent URL (Optional)

Want a fixed URL instead of random `*.trycloudflare.com`?

**Option 1: Buy a domain ($10/year)**
```bash
# Add domain to Cloudflare
# Then route tunnel:
cloudflared tunnel route dns ai-agent-backend api.yourdomain.com
```

**Option 2: Use Cloudflare Workers subdomain (FREE)**
- Go to Cloudflare Dashboard
- Workers → Create subdomain
- Route tunnel to subdomain

---

## ✅ Final Checklist

- [ ] Cloudflared installed
- [ ] Tunnel created and authenticated
- [ ] Config file created at `~/.cloudflared/config.yml`
- [ ] Backend running locally (port 8000)
- [ ] Tunnel running (`cloudflared tunnel run`)
- [ ] Tunnel URL accessible from internet
- [ ] Frontend env vars updated with tunnel URL
- [ ] Frontend deployed to Vercel
- [ ] CORS configured in backend
- [ ] Tunnel running as service (optional)

---

## 📚 Resources

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Cloudflared GitHub](https://github.com/cloudflare/cloudflared)
- [Vercel Deployment](https://vercel.com/docs)

---

**Setup complete!** 🎉

**Your stack:**
- Frontend: `https://your-app.vercel.app`
- Backend (via tunnel): `https://random-words.trycloudflare.com`
- Backend (local): `http://localhost:8000`
