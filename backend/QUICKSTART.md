# 🚀 Quick Start Guide - Trend Reports API

Your API is ready to use! Follow these steps to start using it locally and deploy to production.

---

## 📊 Current Status

- ✅ **51 PDF files** processed (888MB)
- ✅ **ChromaDB** created with embeddings
- ✅ **API** ready to start
- ✅ **API Key:** `s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk`

---

## 🎯 Step 1: Start the API Locally

### Windows:
```bash
cd backend
start_api.bat
```

### Mac/Linux:
```bash
cd backend
./start_api.sh
```

### Manual Start:
```bash
cd backend
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
Documents in database: 3500+
Starting FastAPI server...
API will be available at: http://localhost:8000
API docs at: http://localhost:8000/docs
```

---

## 🧪 Step 2: Test the API

### Open API Documentation
Visit: http://localhost:8000/docs

Interactive Swagger UI with all endpoints.

### Test Health Check
```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "documents": 3842,
  "model": "all-MiniLM-L6-v2",
  "version": "1.0.0"
}
```

### Test Search Endpoint
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk" \
  -d '{
    "query": "AI trends in advertising",
    "top_k": 3
  }'
```

**Expected Response:**
```json
[
  {
    "content": "AI-powered personalization is becoming...",
    "source": "TRENDHUNTER - 2025 Trend Report_CAIG.pdf",
    "page": 12,
    "relevance_score": 0.847
  },
  ...
]
```

### Run Automated Tests
```bash
cd backend
venv\Scripts\activate
python test_api.py local
```

---

## 🌐 Step 3: Deploy to Production

Choose your deployment platform:

### Option A: Railway (Easiest)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
cd backend
railway login
railway init
railway up

# Set environment variables
railway variables set API_KEY=s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk

# Get production URL
railway domain
# Returns: https://trend-reports-api-production.up.railway.app
```

**Cost:** $5-10/month

### Option B: Render

1. Push code to GitHub
2. Go to [render.com](https://render.com)
3. Create Web Service from GitHub repo
4. Render auto-detects Dockerfile
5. Set environment variable: `API_KEY=s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk`
6. Deploy!

**Cost:** $7/month

### Option C: Docker + VPS

See `DEPLOYMENT_GUIDE.md` for detailed instructions.

**Cost:** $12-20/month

---

## 🤖 Step 4: Configure Custom GPT

### 1. Create Custom GPT
- Go to [ChatGPT](https://chat.openai.com) → Explore → Create
- Name: "Trend Intelligence Assistant"
- Description: "Search 888MB of advertising trend reports"

### 2. Configure Instructions
Copy from `CUSTOM_GPT_SETUP.md` or use this condensed version:

```
You are a Trend Intelligence Assistant. You help teams understand insights from 50+ advertising trend reports.

CRITICAL RULES:
1. ALWAYS call searchTrendReports action for EVERY question
2. ALWAYS cite sources: [Source: filename.pdf, p.X]
3. Synthesize insights across multiple reports
4. If no results, suggest rephrasing

RESPONSE FORMAT:
- Start with key findings
- Cite sources throughout
- Connect to actionable strategies
- Highlight contradictions between reports
```

### 3. Add Actions
1. Configure → Actions → Import from URL
2. URL: `https://your-production-url.com/openapi.json`
3. Or paste contents of `backend/openapi.yaml`
4. Update server URL to your production URL

### 4. Configure Authentication
- Type: API Key
- Auth Type: Bearer
- API Key: `s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk`

### 5. Test & Publish
Test query: "What are the top AI trends in advertising for 2025?"

Verify it:
- Calls your API
- Returns results with sources
- Cites page numbers

Then click **Publish** and share with your team!

---

## 📝 Common Commands

### Check Processing Status
```bash
# View last 20 lines of processing log
tail -20 backend/processing.log

# Count processed PDFs
grep "Created.*chunks" backend/processing.log | wc -l
```

### Check ChromaDB Status
```bash
cd backend
venv\Scripts\activate
python -c "import chromadb; c = chromadb.PersistentClient('./chroma_data'); print(c.get_collection('trend_reports').count())"
```

### Restart API
```bash
# Stop: Ctrl+C in the terminal
# Start: Run start_api.bat or start_api.sh again
```

### Test Production API
```bash
# Update .env with production URL
echo "PROD_URL=https://your-app.railway.app" >> backend/.env

# Run tests
cd backend
python test_api.py prod
```

---

## 🐛 Troubleshooting

### "ModuleNotFoundError"
```bash
# Reinstall dependencies
cd backend
venv\Scripts\activate
pip install -r requirements.txt
```

### "ChromaDB not found"
```bash
# Check if processing completed
ls -la backend/chroma_data

# If missing, rerun processing
cd backend
python process_pdfs.py
```

### "API Key invalid"
```bash
# Check .env file
cat backend/.env | grep API_KEY

# Update in Custom GPT to match
```

### "Empty search results"
```bash
# Verify ChromaDB has documents
cd backend
python -c "import chromadb; print(chromadb.PersistentClient('./chroma_data').get_collection('trend_reports').count())"

# Try broader queries
# ❌ "What is the exact ROI of TikTok ads in Q3 2025?"
# ✅ "TikTok advertising trends"
```

---

## 🎯 Next Steps

### Immediate (Today):
1. ✅ Start API locally
2. ✅ Test search endpoint
3. ✅ Run automated tests

### This Week:
1. 🚀 Deploy to Railway/Render
2. 🤖 Configure Custom GPT
3. 👥 Share with team

### Ongoing:
1. 📊 Monitor API usage
2. 🔄 Update reports quarterly
3. 📈 Track popular queries
4. ⚙️ Optimize chunk size if needed

---

## 📚 Resources

- **Main Docs:** `README.md`
- **Deployment:** `DEPLOYMENT_GUIDE.md`
- **Custom GPT:** `CUSTOM_GPT_SETUP.md`
- **API Reference:** http://localhost:8000/docs

---

## 💡 Usage Examples

### Search for AI Trends
```bash
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk" \
  -H "Content-Type: application/json" \
  -d '{"query": "artificial intelligence in marketing", "top_k": 5}'
```

### Search for Social Media
```bash
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk" \
  -H "Content-Type: application/json" \
  -d '{"query": "TikTok and short-form video strategies", "top_k": 3}'
```

### Search for Consumer Behavior
```bash
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk" \
  -H "Content-Type: application/json" \
  -d '{"query": "consumer trends 2025", "top_k": 5}'
```

---

## 🎉 You're Ready!

Your Trend Reports API is fully set up and ready to use. Start the API, run some test queries, and when you're satisfied, deploy to production and configure your Custom GPT.

**Questions?** Check the detailed guides in the `backend/` folder or the troubleshooting section above.

---

**Happy Searching! 🚀**
