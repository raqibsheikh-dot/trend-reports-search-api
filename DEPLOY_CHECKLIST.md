# 🚀 Deployment Checklist

## Pre-Deployment Verification ✅

### Local Files Ready
- [x] ChromaDB data exists: `backend/chroma_data.tar.gz` (69MB)
- [x] ChromaDB verified: 6,109 documents in `trend_reports` collection
- [x] Backend files: Dockerfile, requirements.txt, main.py ✓
- [x] Frontend files: package.json, vite.config.js ✓
- [x] Configuration: render.yaml ✓
- [x] Code pushed to GitHub: https://github.com/raqibsheikh-dot/trend-reports-search-api

---

## Step 1: Create Render.com Account

**Action Items:**
- [ ] Go to https://render.com
- [ ] Sign up with GitHub account
- [ ] Authorize Render to access repositories

**Time Estimate:** 5 minutes

---

## Step 2: Deploy from Blueprint

**Action Items:**
- [ ] Click **"New +"** → **"Blueprint"**
- [ ] Select repository: `raqibsheikh-dot/trend-reports-search-api`
- [ ] Render detects `render.yaml` - shows 3 services:
  - [ ] ✓ trend-reports-api (Web Service)
  - [ ] ✓ trend-reports-cache (Redis)
  - [ ] ✓ trend-reports-frontend (Static Site)
- [ ] Click **"Apply"** to create all services

**Time Estimate:** 2 minutes (build takes 5-10 minutes)

**Expected Result:**
- Backend status: "Building..."
- Frontend status: "Building..."
- Redis status: "Available"

---

## Step 3: Add Required Secrets ⚠️ CRITICAL

**Before services fully deploy, add LLM API keys:**

### Option A: Using Anthropic (Recommended)
- [ ] Go to https://console.anthropic.com/settings/keys
- [ ] Create new API key
- [ ] Copy the key
- [ ] In Render: **trend-reports-api → Environment → Add Environment Variable**
  - Key: `ANTHROPIC_API_KEY`
  - Value: `sk-ant-...` (paste your key)
- [ ] Click **"Save"**

### Option B: Using OpenAI
- [ ] Go to https://platform.openai.com/api-keys
- [ ] Create new API key
- [ ] Copy the key
- [ ] In Render: **trend-reports-api → Environment → Add Environment Variable**
  - Key: `OPENAI_API_KEY`
  - Value: `sk-...` (paste your key)
- [ ] Update `LLM_PROVIDER` to `openai`
- [ ] Click **"Save"**

**Time Estimate:** 5 minutes

⚠️ **Without this, synthesis and structured report features won't work!**

---

## Step 4: Wait for Initial Deployment

**Action Items:**
- [ ] Monitor deployment logs (Dashboard → Logs)
- [ ] Wait for services to reach "Live" status (5-10 minutes)
- [ ] Note any errors in logs

**Expected Logs:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000
```

**Time Estimate:** 10 minutes

---

## Step 5: Upload ChromaDB Data 🔑 CRITICAL

**This is the most important step!** Without this, you'll have 0 documents.

### Get SSH Credentials
- [ ] Go to **Dashboard → trend-reports-api → Shell**
- [ ] Click **"Connect"** to get SSH command
- [ ] Note the server ID (e.g., `srv-xxx`)

### Upload Data (Windows)

**Option A: Using Git Bash or WSL**
```bash
# Navigate to backend folder
cd "C:\Users\raqib\OneDrive\Desktop\AI Experiments\Trend Site\backend"

# Upload (replace srv-xxx with your actual server ID)
scp chroma_data.tar.gz srv-xxx@ssh.render.com:/var/data/

# SSH in and extract
ssh srv-xxx@ssh.render.com
cd /var/data
tar -xzf chroma_data.tar.gz --strip-components=1
rm chroma_data.tar.gz
ls -lh chroma.sqlite3  # Verify it exists
exit
```

**Option B: Using Render Shell (if SCP doesn't work)**
- [ ] In Render Dashboard → trend-reports-api → Shell
- [ ] Upload file through web interface (if available)
- [ ] Or use alternative upload method via GitHub Release Assets

### Verify Upload
- [ ] SSH into Render: `ssh srv-xxx@ssh.render.com`
- [ ] Check file exists: `ls -lh /var/data/chroma.sqlite3`
- [ ] Should see ~91MB file
- [ ] Exit: `exit`

**Time Estimate:** 15-20 minutes (depending on upload speed)

---

## Step 6: Restart Backend Service

**Action Items:**
- [ ] Go to **Dashboard → trend-reports-api**
- [ ] Click **"Manual Deploy"**
- [ ] Select **"Deploy latest commit"**
- [ ] Wait for restart (2-3 minutes)

**Time Estimate:** 3 minutes

---

## Step 7: Verify Backend Health

**Action Items:**
- [ ] Copy backend URL from Render Dashboard
- [ ] Test health endpoint:

```bash
# Replace with your actual URL
curl https://trend-reports-api.onrender.com/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "documents": 6109,
  "chroma_connection": "connected",
  "model": "BAAI/bge-small-en-v1.5",
  "version": "1.0.1",
  "environment": "production"
}
```

**Critical Check:**
- [ ] `"documents": 6109` ✓ (not 0!)
- [ ] `"status": "healthy"` ✓
- [ ] `"chroma_connection": "connected"` ✓

**Time Estimate:** 2 minutes

---

## Step 8: Get and Save API Key

**Action Items:**
- [ ] Go to **Dashboard → trend-reports-api → Environment**
- [ ] Find `API_KEY` variable
- [ ] Click eye icon to reveal value
- [ ] Copy the full key (e.g., `10dafba9ff7c619de2029ed1044cafec4f282e812c51ef8627627480aeb0d89d`)
- [ ] **Save securely** - you'll need this for:
  - Custom GPT authentication
  - Frontend configuration
  - API testing

**⚠️ SECURITY:** Never commit this to GitHub!

**Time Estimate:** 2 minutes

---

## Step 9: Test Backend API

**Action Items:**
- [ ] Test search endpoint:

```bash
# Save your values
BACKEND_URL="https://trend-reports-api.onrender.com"
API_KEY="your_api_key_here"

# Test simple search
curl -X POST $BACKEND_URL/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"query": "AI trends in advertising", "top_k": 3}'
```

**Expected Response:**
```json
{
  "results": [
    {
      "source": "Some_Report_2025.pdf",
      "page": 42,
      "content": "AI is transforming...",
      "relevance_score": 0.85
    },
    ...
  ],
  "total_results": 3
}
```

**Checklist:**
- [ ] Returns 3 results
- [ ] Each result has source, page, content
- [ ] Relevance scores look reasonable (0.5-1.0)

**Time Estimate:** 5 minutes

---

## Step 10: Update Frontend CORS Settings

**Action Items:**
- [ ] Note your frontend URL from Render Dashboard
  - Example: `https://trend-reports-frontend.onrender.com`
- [ ] Go to **Dashboard → trend-reports-api → Environment**
- [ ] Find `ALLOWED_ORIGINS` variable
- [ ] Edit to include your frontend URL:
  ```
  https://trend-reports-frontend.onrender.com,https://chat.openai.com,https://chatgpt.com
  ```
- [ ] Click **"Save Changes"**
- [ ] Restart service

**Time Estimate:** 3 minutes

---

## Step 11: Verify Frontend Deployment

**Action Items:**
- [ ] Visit your frontend URL: `https://trend-reports-frontend.onrender.com`
- [ ] Check page loads correctly
- [ ] Check example queries are visible
- [ ] Click an example query (e.g., "AI trends in luxury automotive")
- [ ] Verify search returns results
- [ ] Check category filter dropdown appears
- [ ] Try switching search modes (Simple, Advanced, Synthesis)

**Expected Behavior:**
- Page loads in < 3 seconds
- Example queries populate search field when clicked
- Search returns results from backend
- UI is responsive and styled correctly

**Time Estimate:** 5 minutes

---

## Step 12: Production URLs Documentation

**Save these URLs:**

| Service | URL | Purpose |
|---------|-----|---------|
| Backend API | `https://trend-reports-api.onrender.com` | API endpoint |
| Frontend | `https://trend-reports-frontend.onrender.com` | Web interface |
| Redis Cache | Internal only | Performance |
| API Key | `your_key_here` | Authentication |

**Action Items:**
- [ ] Update `README.md` with production URLs
- [ ] Share frontend URL with team
- [ ] Document API key location (secure storage)

**Time Estimate:** 3 minutes

---

## Step 13: Configure Custom GPT (Optional)

**Action Items:**
- [ ] Go to https://chat.openai.com
- [ ] Click profile → **My GPTs** → **Create a GPT**
- [ ] Name: "2025 Trend Intelligence"
- [ ] Add instructions from `DEPLOYMENT.md`
- [ ] Configure Actions:
  - Import schema: `https://trend-reports-api.onrender.com/openapi.json`
  - Authentication: Bearer token (use API_KEY from Step 8)
- [ ] Test with query: "What are the top AI trends for 2025?"

**Time Estimate:** 15 minutes

**Prerequisites:** ChatGPT Plus subscription required

---

## Step 14: Final Verification Tests

**Run these tests to ensure everything works:**

### Test 1: Simple Search ✓
```bash
curl -X POST $BACKEND_URL/search \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "social media trends", "top_k": 5}'
```

### Test 2: Advanced Search ✓
```bash
curl -X POST $BACKEND_URL/search/advanced \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AI marketing",
    "query_type": "multi_dimensional",
    "dimensions": ["AI", "personalization", "automation"],
    "top_k": 5
  }'
```

### Test 3: Synthesis ✓
```bash
curl -X POST $BACKEND_URL/search/synthesized \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "customer experience 2025", "top_k": 10}'
```

### Test 4: Structured Report ✓
```bash
curl -X POST $BACKEND_URL/search/structured \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Gen Z shopping behaviors for retail pitch", "top_k": 10}'
```

### Test 5: Categories ✓
```bash
curl $BACKEND_URL/categories
```

**Expected Results:**
- [ ] All endpoints return 200 status
- [ ] All return valid JSON
- [ ] Results contain relevant content
- [ ] No error messages in responses

**Time Estimate:** 10 minutes

---

## Troubleshooting Common Issues

### Issue: "documents": 0 in health check
**Solution:** ChromaDB data wasn't uploaded. Go back to Step 5.

### Issue: Frontend shows "Connection refused"
**Solution:**
1. Check CORS settings (Step 10)
2. Verify API_KEY in frontend environment variables
3. Check backend is running (Dashboard → Logs)

### Issue: Search returns no results
**Solution:**
1. Verify documents loaded: Check `/health` endpoint
2. Try simpler queries first
3. Check backend logs for errors

### Issue: Custom GPT authentication fails
**Solution:**
1. Verify API key is correct (copy from Render Dashboard)
2. Check Bearer token format in GPT Actions
3. Test API key with curl first

### Issue: Out of memory errors
**Solution:**
1. Using free tier? Upgrade to Starter ($7/month)
2. Or reduce workers in render.yaml to 1
3. Monitor memory usage in Dashboard

---

## Post-Deployment Checklist

**Essential:**
- [ ] Backend health check shows 6,109 documents
- [ ] Backend API responds to search queries
- [ ] Frontend loads and searches work
- [ ] API key saved securely
- [ ] Production URLs documented

**Optional:**
- [ ] Custom GPT created and tested
- [ ] Team members have access
- [ ] Monitoring alerts configured
- [ ] Backup strategy implemented

---

## Success Criteria ✅

**You've successfully deployed when:**

1. ✅ Backend API health check shows:
   - Status: "healthy"
   - Documents: 6109
   - ChromaDB: "connected"

2. ✅ Frontend loads and shows:
   - Example queries visible
   - Search functionality works
   - Category filter appears
   - Results display correctly

3. ✅ API endpoints respond:
   - `/search` returns results
   - `/search/advanced` works
   - `/search/synthesized` works
   - `/search/structured` works
   - `/categories` lists categories

4. ✅ Security configured:
   - API key required for access
   - CORS limited to specific domains
   - Rate limiting active

---

## Total Deployment Time Estimate

**Active work:** 60-75 minutes
**Waiting time:** 15-20 minutes (builds, uploads)
**Total:** ~1.5 hours

---

## Need Help?

- **Render Docs:** https://render.com/docs
- **Render Status:** https://status.render.com
- **Project README:** See README.md
- **Deployment Guide:** See DEPLOYMENT.md

---

**Last Updated:** 2025-10-26
**Version:** 2.0
**Status:** Ready for deployment ✅
