# Trend Reports API - Custom GPT Backend

A FastAPI-based backend that processes large PDF collections (866MB+) and provides semantic search via Custom GPT. This system uses ChromaDB for vector storage and sentence-transformers for embeddings.

## 🎯 Architecture Overview

```
Custom GPT (OpenAI) ←→ FastAPI Backend ←→ ChromaDB Vector Database
                              ↓
                        PDF Processing Pipeline
                        (pdfplumber + OCR)
```

**Key Features:**
- ✅ Handles 866MB of PDF files (no file size limits)
- ✅ Semantic search with sentence embeddings
- ✅ OCR fallback for scanned documents
- ✅ Smart text chunking with overlap
- ✅ API authentication for security
- ✅ Ready for deployment (Docker + cloud platforms)

---

## 📋 Prerequisites

- **Python 3.10+**
- **Tesseract OCR** (for scanned PDFs)
  - Windows: Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
  - Mac: `brew install tesseract`
  - Linux: `apt-get install tesseract-ocr`
- **Poppler** (for PDF to image conversion)
  - Windows: Download from [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
  - Mac: `brew install poppler`
  - Linux: `apt-get install poppler-utils`

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Navigate to backend folder
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env and set your API key
# API_KEY=your_secure_random_key_here
```

### 3. Add Your PDF Files

```bash
# Create folder for your trend reports
mkdir "2025 Trend Reports"

# Copy your 866MB of PDFs into this folder
# (Or update REPORTS_FOLDER in .env to point to your existing folder)
```

### 4. Process PDFs (One-Time Setup)

```bash
# This will:
# - Extract text from all PDFs (with OCR fallback)
# - Create semantic chunks
# - Generate embeddings
# - Store in ChromaDB

python process_pdfs.py
```

**Expected Output:**
```
============================================================
Starting PDF Processing Pipeline
============================================================
Loading embedding model (all-MiniLM-L6-v2)...
Found 50 PDF files (866.3 MB)
Processing PDFs: 100%|████████████| 50/50
Creating embeddings and storing in ChromaDB...
Embedding batches: 100%|████████████| 38/38

✅ Processing Complete!
  • Processed 50 PDF files
  • Created 3,842 text chunks
  • Stored in ChromaDB at: ./chroma_data
============================================================
```

### 5. Start API Server

```bash
# Run locally
uvicorn main:app --reload

# API will be available at:
# - http://localhost:8000
# - Docs: http://localhost:8000/docs
# - OpenAPI: http://localhost:8000/openapi.json
```

### 6. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Test search (replace YOUR_API_KEY)
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "What are the top AI trends in advertising?",
    "top_k": 3
  }'
```

---

## 🌐 Deploy to Production

### Option A: Deploy to Railway (Recommended - Easiest)

1. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   ```

2. **Initialize and Deploy**
   ```bash
   railway login
   railway init
   railway up
   ```

3. **Set Environment Variables**
   ```bash
   railway variables set API_KEY=your_secure_key_here
   ```

4. **Get Your URL**
   ```bash
   railway domain
   # Returns: https://your-app.railway.app
   ```

**Cost:** ~$5-10/month

### Option B: Deploy to Render

1. **Create `render.yaml`** (already configured in this repo)

2. **Connect to Render**
   - Go to [render.com](https://render.com)
   - Create new Web Service
   - Connect your GitHub repo
   - Render auto-detects Dockerfile

3. **Set Environment Variables** in Render Dashboard:
   - `API_KEY`: your secure key
   - `CHROMA_DB_PATH`: `/app/chroma_data`

4. **Deploy**
   - Render builds and deploys automatically
   - Get URL: `https://your-app.onrender.com`

**Cost:** $7/month (Starter plan)

### Option C: Docker + Any VPS

```bash
# Build image
docker build -t trend-reports-api .

# Run container
docker run -d \
  -p 8000:8000 \
  -e API_KEY=your_secure_key \
  -v $(pwd)/chroma_data:/app/chroma_data \
  --name trend-api \
  trend-reports-api

# Check logs
docker logs -f trend-api
```

**Note:** You'll need to manually copy `chroma_data` folder to your VPS after processing PDFs locally.

---

## 🤖 Connect to Custom GPT

### 1. Create Custom GPT

1. Go to [ChatGPT](https://chat.openai.com) → Explore GPTs → Create
2. **Name:** "Trend Intelligence Assistant"
3. **Description:** "Search and analyze advertising trend reports"

### 2. Configure Instructions

Paste this into the Instructions field:

```
You are a Trend Intelligence Assistant for an advertising agency. You help teams
understand and apply insights from 50+ trend reports (866MB of research).

CRITICAL RULES:
1. For EVERY question, you MUST call searchTrendReports action first
2. ALWAYS cite specific reports and pages: [Source: filename.pdf, p.X]
3. Synthesize insights across multiple reports when relevant
4. If no results found, suggest rephrasing the query

RESPONSE FORMAT:
- Start with key findings from the search results
- Cite sources clearly throughout your answer
- Connect trends to actionable advertising strategies
- Highlight contradictions between reports if they exist
- Be specific with data, statistics, and examples

Never answer from your training data alone - always search the reports first.
```

### 3. Add Actions

1. Go to **Configure → Actions**
2. Click **Import from URL** or paste the OpenAPI schema
3. **Schema:** Copy from `backend/openapi.yaml`
4. Update `servers.url` to your deployed API URL:
   ```yaml
   servers:
     - url: https://your-app.railway.app  # Your actual URL
   ```

### 4. Configure Authentication

1. Choose **Authentication Type:** API Key
2. **Auth Type:** Bearer
3. **API Key:** Your `API_KEY` from `.env`
4. **Header Name:** `Authorization`

### 5. Test & Publish

1. Test in the preview panel:
   ```
   What are the top AI trends in advertising for 2025?
   ```

2. Verify it:
   - Calls the API
   - Returns results with sources
   - Cites page numbers

3. Click **Publish** → Share with team

---

## 📊 Project Structure

```
backend/
├── main.py                 # FastAPI app with /search endpoint
├── process_pdfs.py         # One-time PDF processing script
├── openapi.yaml            # OpenAPI schema for Custom GPT
├── requirements.txt        # Python dependencies
├── Dockerfile              # Production container
├── .env.example            # Environment variables template
├── .env                    # Your actual config (git-ignored)
├── README.md               # This file
│
├── 2025 Trend Reports/     # Your PDF files (create this)
│   ├── report1.pdf
│   ├── report2.pdf
│   └── ...
│
└── chroma_data/            # Vector database (auto-created)
    └── [embeddings stored here]
```

---

## 🔧 Configuration Options

### Environment Variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Secure key for Custom GPT auth | `your_secure_api_key_here` |
| `CHROMA_DB_PATH` | Path to vector database | `./chroma_data` |
| `REPORTS_FOLDER` | Folder containing PDFs | `2025 Trend Reports` |
| `CHUNK_SIZE` | Characters per text chunk | `800` |
| `OVERLAP` | Overlapping characters | `150` |

### Chunk Size Tuning

- **Smaller chunks (400-600):** More precise, but may miss context
- **Larger chunks (1000-1500):** More context, but less precise
- **Overlap (100-200):** Prevents information loss at boundaries

**Recommended:** Start with defaults (800/150), adjust based on results.

---

## 🧪 API Endpoints

### `POST /search`

Search trend reports with semantic similarity.

**Request:**
```json
{
  "query": "AI trends in advertising",
  "top_k": 5
}
```

**Response:**
```json
[
  {
    "content": "AI-powered personalization is becoming the standard...",
    "source": "2025_Advertising_Trends.pdf",
    "page": 12,
    "relevance_score": 0.847
  }
]
```

### `GET /health`

Check API health and document count.

**Response:**
```json
{
  "status": "healthy",
  "documents": 3842,
  "model": "all-MiniLM-L6-v2",
  "version": "1.0.0"
}
```

---

## 🐛 Troubleshooting

### Issue: "Tesseract not found"

**Windows:**
```bash
# Download and install from: https://github.com/UB-Mannheim/tesseract/wiki
# Add to PATH: C:\Program Files\Tesseract-OCR
```

**Mac/Linux:**
```bash
brew install tesseract   # Mac
apt install tesseract-ocr  # Linux
```

### Issue: "No PDF files found"

Check that:
1. Folder name matches `REPORTS_FOLDER` in `.env`
2. PDFs are directly in the folder (not in subfolders)
3. Files have `.pdf` extension

### Issue: "Empty search results"

1. Verify PDFs processed correctly:
   ```bash
   python -c "import chromadb; print(chromadb.PersistentClient('./chroma_data').get_collection('trend_reports').count())"
   ```

2. Try more general queries:
   - ❌ "What is the exact ROI of TikTok ads in Q3 2025?"
   - ✅ "TikTok advertising trends"

### Issue: "API authentication failed"

1. Check `API_KEY` in `.env` matches Custom GPT config
2. Verify Authorization header format: `Bearer YOUR_KEY`
3. Check API logs: `docker logs trend-api`

---

## 💰 Cost Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| API Hosting (Railway/Render) | $7-20/mo | Includes compute + storage |
| ChromaDB Storage | Free | Included in hosting |
| Embedding Model | Free | Runs locally (sentence-transformers) |
| Custom GPT | Free | No per-user cost after setup |
| **Total** | **$7-20/mo** | Unlimited team usage |

**Compare to Alternatives:**
- Pinecone: $70/mo minimum
- OpenAI Assistants: $20/user/month
- AWS SageMaker: $50+/mo

---

## 🚢 Production Checklist

- [ ] Change `API_KEY` to secure random value
- [ ] Update `openapi.yaml` servers URL
- [ ] Process all PDFs locally first
- [ ] Deploy API to cloud platform
- [ ] Copy `chroma_data` to production (or reprocess)
- [ ] Test `/health` endpoint
- [ ] Test `/search` endpoint with curl
- [ ] Configure Custom GPT with production URL
- [ ] Test Custom GPT end-to-end
- [ ] Share with team

---

## 📚 Next Steps

### Enhancements

1. **Add Filters:**
   ```python
   # Filter by report name or date
   collection.query(
       query_embeddings=[...],
       where={"filename": {"$contains": "2025"}}
   )
   ```

2. **Hybrid Search:**
   Combine semantic + keyword search for better results

3. **Caching:**
   Add Redis for faster repeated queries

4. **Analytics:**
   Track popular queries and search quality

5. **Multi-language:**
   Add language detection and translation

### Monitoring

- **Logs:** Check Railway/Render logs for errors
- **Metrics:** Track search latency and result quality
- **Alerts:** Set up uptime monitoring (e.g., UptimeRobot)

---

## 🤝 Support

### Resources
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [ChromaDB Docs](https://docs.trychroma.com)
- [Custom GPT Guide](https://platform.openai.com/docs/guides/gpt)

### Common Questions

**Q: Can I update PDFs after deployment?**
A: Yes, rerun `process_pdfs.py` and redeploy. Or add incremental update logic.

**Q: How many users can use this?**
A: Unlimited! Custom GPT shares one API backend.

**Q: Can I use GPT-4 for search?**
A: Current setup uses local embeddings (free). You can integrate GPT for reranking.

**Q: How accurate is the search?**
A: Depends on chunk size and query quality. Test and tune for your use case.

---

## 📝 License

MIT License - Feel free to modify and use for your team.

---

**Built with ❤️ for advertising teams who need instant access to trend intelligence.**
