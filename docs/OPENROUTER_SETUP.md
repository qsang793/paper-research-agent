# 🔑 OpenRouter Setup Guide

Quick guide to get an OpenRouter API key and configure it for the backend.

---

## 🚀 Get Free API Key (2 minutes)

### Step 1: Create Account
1. Go to: https://openrouter.ai/
2. Click **"Sign In"** (top right)
3. Sign up with Google/GitHub/Email

### Step 2: Generate API Key
1. Go to: https://openrouter.ai/keys
2. Click **"Create Key"**
3. Name it: `AI Research Agent`
4. Copy the key: `sk-or-v1-xxxxxxxxxxxxx`
5. **Save it securely** (you won't see it again!)

---

## 💰 Model Selection

OpenRouter model availability changes over time. Check the model explorer for
current free and paid model IDs, then set `OPENROUTER_MODEL` accordingly.

Examples that have been useful for this project:

| Model | Provider | Speed | Quality | Use Case |
|-------|----------|-------|---------|----------|
| `xiaomi/mimo-v2-flash:free` | Xiaomi | ⚡⚡⚡ Fast | 🟢 Good | **Recommended** - General chat |
| `google/gemini-2.0-flash-001:free` | Google | ⚡⚡ Medium | 🟢🟢 Better | Research, long answers |
| `meta-llama/llama-3-8b-instruct:free` | Meta | ⚡ Slow | 🟢 Good | General purpose |

Prefer a fast model for iterative local development and a stronger model for
longer synthesis answers.

---

## 🔧 Backend Configuration

Set these backend environment variables locally in `.env` or in your hosting
provider dashboard:

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
LLM_BACKEND=openrouter
OPENROUTER_MODEL=xiaomi/mimo-v2-flash:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TIMEOUT_SEC=60

# Optional
EMBED_MODEL=intfloat/e5-base-v2
CHROMA_PATH=./chroma
CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

---

## 📊 Rate Limits (Free Tier)

| Metric | Free Tier | Enough for? |
|--------|-----------|-------------|
| **Requests/minute** | ~20-60 | ✅ Yes (research project) |
| **Credits** | $0 (unlimited for free models) | ✅ Yes |
| **Rate limit** | Varies by model | ✅ Sufficient |

**Your usage estimate:** ~100-500 requests/day = well within limits

---

## 🧪 Test Your API Key

### Local Test (Before deploying)

```bash
# Test with curl
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "xiaomi/mimo-v2-flash:free",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**Expected response:**
```json
{
  "id": "gen-xxxxx",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      }
    }
  ]
}
```

### Test with Python

```python
import requests

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer YOUR_API_KEY",
        "Content-Type": "application/json"
    },
    json={
        "model": "xiaomi/mimo-v2-flash:free",
        "messages": [{"role": "user", "content": "Test"}]
    }
)

print(response.json())
```

---

## 🔄 Switch Models (Optional)

Want to try different models? Update backend environment variables:

**For better quality (slower):**
```bash
OPENROUTER_MODEL=google/gemini-2.0-flash-001:free
```

**For Meta Llama:**
```bash
OPENROUTER_MODEL=meta-llama/llama-3-8b-instruct:free
```

Restart or redeploy the backend after changing model variables.

---

## 💡 Tips & Best Practices

### 1. Monitor Usage
- Dashboard: https://openrouter.ai/activity
- Check credits and rate limits
- Free models don't consume credits ✅

### 2. Error Handling
If you get rate limit errors:
```json
{"error": "Rate limit exceeded"}
```

**Solution:** Switch to another free model or wait 1 minute.

### 3. Optimal Configuration

**For fast responses (research agent):**
```bash
OPENROUTER_MODEL=xiaomi/mimo-v2-flash:free  # ✅ Current
OPENROUTER_TIMEOUT_SEC=60
```

**For better quality (longer answers):**
```bash
OPENROUTER_MODEL=google/gemini-2.0-flash-001:free
OPENROUTER_TIMEOUT_SEC=90
```

---

## 🚨 Troubleshooting

### Issue 1: "Invalid API key"
**Cause:** Wrong key format or expired
**Solution:**
1. Go to https://openrouter.ai/keys
2. Revoke old key
3. Create new key
4. Update backend environment variables

### Issue 2: "Model not found"
**Cause:** Wrong model name
**Solution:** Use exact model ID with `:free` suffix:
```bash
xiaomi/mimo-v2-flash:free  # ✅ Correct
xiaomi/mimo-v2-flash       # ❌ Wrong (not free)
```

### Issue 3: "Rate limit exceeded"
**Cause:** Too many requests
**Solution:**
- Free models have generous limits (~20-60 req/min)
- Wait 1 minute or switch model

---

## 📈 Next Steps

After getting your API key:

1. **Add to your backend environment:**
   - Local: add `OPENROUTER_API_KEY=sk-or-v1-xxxxx` to `.env`.
   - Hosted backend: add the same variable in your hosting provider dashboard.

2. **Test the backend:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Deploy frontend:**
   - Configure `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_API_BASE_URL` to point at
     your backend or tunnel URL.

---

## 🔗 Resources

- **Get API Key:** https://openrouter.ai/keys
- **Model Explorer:** https://openrouter.ai/models
- **Documentation:** https://openrouter.ai/docs
- **Activity Dashboard:** https://openrouter.ai/activity

---

**Setup Status:** ✅ Ready to run with OpenRouter.
