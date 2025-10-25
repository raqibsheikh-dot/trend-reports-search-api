# 🚀 Deployment Guide to Render.com

## Prerequisites

- GitHub repository: https://github.com/raqibsheikh-dot/trend-reports-search-api
- Render.com account (free tier available)
- ChromaDB data directory with 6,109 indexed documents

## ⚠️ Critical: ChromaDB Data Upload

Since PDF files are not in the repository (too large for GitHub), you must upload the pre-processed ChromaDB data to Render's persistent disk.

### Option 1: Upload ChromaDB via SCP (Recommended)

After deployment, Render provides SSH access to your persistent disk:

```bash
# 1. Compress ChromaDB data locally
cd "C:\Users\raqib\OneDrive\Desktop\AI Experiments\Trend Site\backend"
tar -czf chroma_data.tar.gz chroma_data/

# 2. Get Render disk SSH credentials from dashboard
# Dashboard → Your Service → Disks → chroma-data → Connect

# 3. Upload via SCP
scp chroma_data.tar.gz srv-xxx@ssh.render.com:/app/chroma_data/

# 4. SSH into Render and extract
ssh srv-xxx@ssh.render.com
cd /app/chroma_data
tar -xzf chroma_data.tar.gz
rm chroma_data.tar.gz
```

### Option 2: Rebuild in Production (Slower)

If you have the PDFs available, you can upload them and rebuild:

```bash
# 1. Upload PDFs to Render disk via SCP
# 2. SSH into Render
# 3. Run process_pdfs.py
python process_pdfs.py
```

## 📋 Step-by-Step Deployment

### 1. Create Render Account

1. Go to https://render.com
2. Sign up with GitHub account
3. Authorize Render to access your repositories

### 2. Create New Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository: `raqibsheikh-dot/trend-reports-search-api`
3. Render will auto-detect `render.yaml` configuration

### 3. Configure Service

Render should auto-configure from `render.yaml`, but verify:

- **Name:** trend-reports-api
- **Runtime:** Docker
- **Dockerfile Path:** `./backend/Dockerfile`
- **Docker Context:** `./backend`
- **Instance Type:** Free (512MB RAM) or Starter ($7/month, 512MB RAM)

### 4. Environment Variables

Render will auto-generate these from `render.yaml`:

| Variable | Value | Notes |
|----------|-------|-------|
| `API_KEY` | Auto-generated | **Copy this for Custom GPT!** |
| `ENVIRONMENT` | production | Enables HSTS security |
| `CHROMA_DB_PATH` | /app/chroma_data | Mounted disk |
| `REPORTS_FOLDER` | /app/2025 Trend Reports | Not used in production |
| `CHUNK_SIZE` | 800 | Already configured |
| `OVERLAP` | 150 | Already configured |
| `RATE_LIMIT` | 20/minute | Increased for production |
| `ALLOWED_ORIGINS` | https://chat.openai.com,https://chatgpt.com | CORS for Custom GPT |

**⚠️ Important:** After deployment, go to **Environment** → **API_KEY** and copy the generated value. You'll need this for Custom GPT.

### 5. Persistent Disk Configuration

Verify disk settings:

- **Name:** chroma-data
- **Mount Path:** /app/chroma_data
- **Size:** 10 GB
- **Auto-mounted:** Yes

### 6. Deploy

1. Click **"Create Web Service"**
2. Render will:
   - Clone your repository
   - Build Docker image (takes 5-10 minutes first time)
   - Start the service
   - Run health checks

### 7. Upload ChromaDB Data

**This step is critical!** The service will start but have 0 documents until you upload the data.

```bash
# Compress locally
cd "C:\Users\raqib\OneDrive\Desktop\AI Experiments\Trend Site\backend"
tar -czf chroma_data.tar.gz chroma_data/

# Get SSH credentials from Render dashboard
# Dashboard → trend-reports-api → Disks → chroma-data → Connect

# Upload (replace srv-xxx with your actual server ID)
scp chroma_data.tar.gz srv-xxx@ssh.render.com:/app/chroma_data/

# Extract via SSH
ssh srv-xxx@ssh.render.com
cd /app/chroma_data
tar -xzf chroma_data.tar.gz --strip-components=1
rm chroma_data.tar.gz
exit

# Restart service to load data
# Dashboard → trend-reports-api → Manual Deploy → Deploy latest commit
```

### 8. Verify Deployment

Once deployed, test your endpoints:

```bash
# Get your production URL (e.g., https://trend-reports-api.onrender.com)
PROD_URL="https://trend-reports-api.onrender.com"
API_KEY="your_generated_api_key_from_render_dashboard"

# Test health check
curl $PROD_URL/health

# Expected response:
# {
#   "status": "healthy",
#   "documents": 6109,
#   "chroma_connection": "connected",
#   "model": "BAAI/bge-small-en-v1.5",
#   "version": "1.0.1",
#   "environment": "production",
#   "timestamp": "2025-10-25T..."
# }

# Test search
curl -X POST $PROD_URL/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"query": "AI trends in advertising", "top_k": 3}'
```

### 9. Monitor Deployment

- **Logs:** Dashboard → Logs (real-time streaming)
- **Metrics:** Dashboard → Metrics (CPU, memory, requests)
- **Health:** Dashboard → Health Checks (30s interval)

## 🎯 Custom GPT Configuration

Once deployed, configure your Custom GPT:

### 1. Create Custom GPT

1. Go to https://chat.openai.com
2. Click your profile → **My GPTs** → **Create a GPT**

### 2. Configure Instructions

```
You are a trend research assistant with access to 51 advertising and marketing trend reports from 2025.

When users ask about trends in advertising, marketing, AI, social media, customer experience, e-commerce, or digital marketing, use the search_trends action to find relevant information.

Always cite the source document and page number when providing information.

The reports cover:
- AI & Marketing Automation
- Social Media Trends
- Customer Experience (CX)
- E-commerce & Retail
- Digital Advertising
- Consumer Behavior
- Brand Strategy
```

### 3. Configure Actions

1. Click **"Create new action"**
2. **Import from URL:** `https://trend-reports-api.onrender.com/openapi.json`
3. Render will auto-import the schema

### 4. Configure Authentication

1. **Authentication Type:** Bearer
2. **Token:** `your_api_key_from_render_dashboard`
3. Test the connection

### 5. Test Your GPT

Ask test questions:
- "What are the top AI trends in advertising for 2025?"
- "Show me insights about social media marketing"
- "What are consumers expecting from brands?"

## 🔒 Security Considerations

### Production Security Checklist

- ✅ API key authentication enabled
- ✅ Rate limiting (20 requests/minute)
- ✅ CORS restricted to ChatGPT domains only
- ✅ HTTPS enforced by Render
- ✅ Security headers (X-Frame-Options, CSP, etc.)
- ✅ Non-root Docker user
- ✅ Health checks enabled
- ⚠️ **To Do:** Rotate API key if exposed

### API Key Security

**Never expose your API key publicly!**

- ❌ Don't commit to GitHub
- ❌ Don't share in screenshots
- ❌ Don't post in forums
- ✅ Use environment variables only
- ✅ Rotate if compromised

To rotate API key:
```bash
# Generate new key
python -c "import secrets; print(secrets.token_hex(32))"

# Update in Render dashboard
# Environment → API_KEY → Edit → Save → Restart service

# Update Custom GPT authentication
# GPT Actions → Authentication → Update token
```

## 📊 Performance Optimization

### Free Tier Limitations

- **Spins down after 15 minutes of inactivity**
- **Cold start: 30-60 seconds**
- **512 MB RAM** (sufficient for this app)
- **100 GB bandwidth/month**

### Upgrade to Starter ($7/month)

- Always running (no spin down)
- Instant responses
- Same RAM but guaranteed uptime

### Monitoring Performance

```bash
# Check response time
time curl $PROD_URL/health

# Load test (use responsibly)
ab -n 100 -c 10 -H "Authorization: Bearer $API_KEY" \
  -p search.json -T application/json \
  $PROD_URL/search
```

## 🐛 Troubleshooting

### Service Won't Start

1. Check logs: Dashboard → Logs
2. Common issues:
   - Docker build failed (check Dockerfile)
   - Port binding error (ensure using $PORT)
   - Missing dependencies (check requirements.txt)

### Health Check Failing

```bash
# SSH into Render
ssh srv-xxx@ssh.render.com

# Test health endpoint internally
curl localhost:8000/health

# Check ChromaDB connection
python -c "import chromadb; client = chromadb.PersistentClient(path='/app/chroma_data'); print(client.list_collections())"
```

### 0 Documents in Database

**This means ChromaDB data wasn't uploaded!** Follow Step 7 above.

### Search Returns No Results

1. Verify documents loaded: `curl $PROD_URL/health` → check `"documents": 6109`
2. Check query syntax
3. Review logs for errors

### Out of Memory

If using free tier and seeing OOM errors:
1. Reduce `--workers` to 1 (already set)
2. Set environment variables:
   ```
   OMP_NUM_THREADS=1
   MKL_NUM_THREADS=1
   ```
3. Consider upgrading to Starter plan

## 📈 Scaling for Production

### Horizontal Scaling

Render supports multiple instances:
1. Dashboard → Scaling → Instances: 2+
2. Load balanced automatically
3. Shared disk for ChromaDB

### Caching Layer

Add Redis for frequent queries:
```python
import redis
r = redis.Redis(host='your-redis-url')

@app.post("/search")
async def search_trends(...):
    cache_key = f"search:{query}:{top_k}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)
    # ... perform search
    r.setex(cache_key, 3600, json.dumps(results))
    return results
```

### Database Optimization

For high traffic:
1. Use Qdrant or Pinecone instead of ChromaDB
2. Offload embeddings to separate service
3. Add CDN for static assets

## 💰 Cost Estimation

### Free Tier
- **Cost:** $0/month
- **Limitations:** Spins down after 15 min
- **Best for:** Testing, low traffic

### Starter Plan
- **Cost:** $7/month
- **Always on**
- **Best for:** Production Custom GPT with moderate usage

### Professional Plan
- **Cost:** $25/month
- **More RAM and CPU**
- **Best for:** High traffic APIs

## 🔄 Continuous Deployment

Auto-deploy is enabled in `render.yaml`:

```bash
# Any push to master auto-deploys
git add .
git commit -m "Update feature"
git push origin master

# Render automatically:
# 1. Detects push
# 2. Rebuilds Docker image
# 3. Runs health checks
# 4. Switches traffic to new version
# 5. Zero-downtime deployment
```

## 📞 Support

- **Render Docs:** https://render.com/docs
- **Render Community:** https://community.render.com
- **Status:** https://status.render.com
- **Support:** support@render.com

## 🎉 Success Checklist

Before considering deployment complete:

- [ ] Service deployed and running
- [ ] Health check returns "healthy"
- [ ] Documents count = 6,109
- [ ] Search endpoint returns results
- [ ] API key copied and secured
- [ ] Custom GPT configured and tested
- [ ] CORS allows ChatGPT domains
- [ ] Rate limiting tested
- [ ] Logs reviewed for errors
- [ ] Production URL documented
- [ ] API key rotation process documented

## 📝 Production URL

After deployment, your API will be available at:

```
https://trend-reports-api.onrender.com
```

Save this URL for Custom GPT configuration!

## 🔑 API Key

**⚠️ CRITICAL:** Copy your API key from Render dashboard immediately after deployment. You'll need it for Custom GPT authentication.

Location: **Dashboard → Environment → API_KEY → Value (click eye icon)**
