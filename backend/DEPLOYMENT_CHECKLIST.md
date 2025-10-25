# ✅ Deployment Checklist - Trend Reports API

Use this checklist to ensure smooth deployment to production.

---

## 📋 Pre-Deployment Checklist

### Local Setup ✅
- [x] Virtual environment created (`venv/`)
- [x] Dependencies installed (`pip install -r requirements.txt`)
- [x] `.env` file configured with API key
- [x] PDFs in correct folder (51 files, 888MB)
- [x] Tesseract OCR installed (v5.5.0)
- [x] PDF processing completed
- [x] ChromaDB created with embeddings

### Local Testing
- [ ] API starts successfully (`./start_api.bat` or `./start_api.sh`)
- [ ] Health endpoint works (`/health`)
- [ ] Search endpoint works (`/search`)
- [ ] Authentication is enforced (401 with wrong key)
- [ ] Test suite passes (`python test_api.py local`)
- [ ] Sample queries return good results

---

## 🚀 Deployment Steps

### Step 1: Choose Platform
- [ ] Railway (easiest, ~$5-10/mo)
- [ ] Render (GitHub integration, $7/mo)
- [ ] Docker + VPS (full control, $12-20/mo)

### Step 2: Prepare Code for Deployment

#### For Railway/Render:
- [ ] Push code to GitHub
  ```bash
  git init
  git add .
  git commit -m "Initial deployment"
  git remote add origin https://github.com/yourusername/trend-reports-api.git
  git push -u origin main
  ```

#### For all platforms:
- [ ] Update `openapi.yaml` with production URL
- [ ] Generate new production API key (if needed)
- [ ] Document API key securely

### Step 3: Deploy API

#### Railway:
- [ ] Install CLI: `npm install -g @railway/cli`
- [ ] Login: `railway login`
- [ ] Initialize: `railway init`
- [ ] Deploy: `railway up`
- [ ] Set variables:
  ```bash
  railway variables set API_KEY=your_production_key
  railway variables set CHROMA_DB_PATH=/app/chroma_data
  ```
- [ ] Create volume: `railway volume create chroma-data`
- [ ] Mount volume: `railway volume attach chroma-data /app/chroma_data`
- [ ] Get domain: `railway domain`

#### Render:
- [ ] Connect GitHub repo
- [ ] Configure build settings (Dockerfile detected)
- [ ] Set environment variables in dashboard:
  - `API_KEY=your_production_key`
  - `CHROMA_DB_PATH=/app/chroma_data`
- [ ] Add persistent disk (10GB, mount at `/app/chroma_data`)
- [ ] Deploy

#### Docker + VPS:
- [ ] Build image: `docker build -t trend-reports-api .`
- [ ] Upload to VPS
- [ ] Run container with volume mount
- [ ] Configure nginx/reverse proxy
- [ ] Set up SSL (Let's Encrypt)

### Step 4: Upload ChromaDB Data

- [ ] Option A: Process PDFs on production
  ```bash
  railway shell  # or ssh to VPS
  python process_pdfs.py
  ```

- [ ] Option B: Upload processed ChromaDB
  ```bash
  tar -czf chroma_data.tar.gz chroma_data/
  # Upload via platform dashboard or scp
  ```

### Step 5: Production Testing
- [ ] Health check works: `curl https://your-app.com/health`
- [ ] Document count is correct (~6000+ documents expected)
- [ ] Search endpoint works with API key
- [ ] Returns relevant results
- [ ] Run test suite: `python test_api.py prod`
- [ ] Check API logs for errors

---

## 🤖 Custom GPT Configuration

### Step 1: Create GPT
- [ ] Go to ChatGPT → Explore → Create
- [ ] Set name: "Trend Intelligence Assistant"
- [ ] Set description: "Search 888MB of advertising trend reports"

### Step 2: Configure Instructions
- [ ] Copy instructions from `CUSTOM_GPT_SETUP.md`
- [ ] Customize for your team's needs
- [ ] Add conversation starters

### Step 3: Add Actions
- [ ] Configure → Actions → Import from URL
- [ ] URL: `https://your-production-url.com/openapi.json`
- [ ] Or paste `openapi.yaml` contents
- [ ] Update server URL to production

### Step 4: Authentication
- [ ] Type: API Key
- [ ] Auth Type: Bearer
- [ ] API Key: Your production API key
- [ ] Header: `Authorization`

### Step 5: Test GPT
- [ ] Test query: "What are the top AI trends in advertising?"
- [ ] Verify API is called
- [ ] Check results include sources and page numbers
- [ ] Try multiple queries
- [ ] Test with different team members

### Step 6: Publish & Share
- [ ] Set privacy settings (Anyone with link / Only me / Public)
- [ ] Click Publish
- [ ] Share link with team
- [ ] Provide usage instructions

---

## 📊 Post-Deployment Monitoring

### Week 1: Daily Checks
- [ ] API uptime (set up UptimeRobot monitoring)
- [ ] Error rate in logs
- [ ] Response times (<500ms ideal)
- [ ] Team feedback

### Week 2-4: Optimization
- [ ] Review popular queries
- [ ] Analyze search quality
- [ ] Adjust chunk size if needed (currently 800)
- [ ] Monitor costs
- [ ] Add caching if needed (Redis)

### Ongoing: Maintenance
- [ ] Update reports quarterly
- [ ] Reprocess PDFs when updated
- [ ] Monitor disk usage
- [ ] Backup ChromaDB monthly
- [ ] Update dependencies quarterly

---

## 🐛 Troubleshooting Checklist

### API Won't Start
- [ ] Check environment variables are set
- [ ] Verify ChromaDB path exists
- [ ] Check logs for errors
- [ ] Ensure port 8000 is available
- [ ] Verify Python version (3.10+)

### Empty Search Results
- [ ] Verify ChromaDB has documents
  ```bash
  python -c "import chromadb; print(chromadb.PersistentClient('./chroma_data').get_collection('trend_reports').count())"
  ```
- [ ] Check API logs for errors
- [ ] Try broader search queries
- [ ] Verify embeddings were created

### Authentication Failing
- [ ] API key matches in .env and Custom GPT
- [ ] Bearer token format correct
- [ ] Check Authorization header
- [ ] Test with curl first

### Slow Performance
- [ ] Check server resources (RAM/CPU)
- [ ] Reduce top_k parameter
- [ ] Add Redis caching
- [ ] Upgrade hosting plan
- [ ] Check database size

---

## 💰 Cost Optimization

### Current Costs
- [ ] API Hosting: $____/month
- [ ] Storage: $____/month
- [ ] Total: $____/month

### Optimization Opportunities
- [ ] Right-size instance (start small, scale up)
- [ ] Monitor usage patterns
- [ ] Cache frequent queries
- [ ] Optimize chunk size (larger = fewer chunks)
- [ ] Clean up unused embeddings

---

## 📈 Success Metrics

### Technical Metrics
- [ ] API uptime: _____% (target: >99%)
- [ ] Average response time: _____ms (target: <500ms)
- [ ] Search relevance: _____/10 (user feedback)
- [ ] Documents indexed: _____ (expected: 6000+)

### Usage Metrics
- [ ] Daily active users: _____
- [ ] Average queries per user: _____
- [ ] Most popular topics: _____
- [ ] User satisfaction: _____/10

### Business Metrics
- [ ] Time saved per week: _____ hours
- [ ] ROI vs alternatives: _____x
- [ ] Team adoption rate: _____%

---

## 🎯 Launch Plan

### Pre-Launch (Day -1)
- [ ] Complete all deployment steps
- [ ] Run full test suite
- [ ] Prepare team documentation
- [ ] Schedule team training

### Launch Day (Day 0)
- [ ] Send announcement email
- [ ] Share Custom GPT link
- [ ] Provide quick-start guide
- [ ] Be available for support
- [ ] Monitor usage closely

### Post-Launch (Days 1-7)
- [ ] Daily check-ins with team
- [ ] Gather feedback
- [ ] Fix any issues
- [ ] Document common questions
- [ ] Optimize based on usage

### Week 2+
- [ ] Weekly usage reports
- [ ] Quarterly report updates
- [ ] Feature requests review
- [ ] Continuous improvement

---

## 📝 Final Pre-Launch Checklist

- [ ] All environment variables set
- [ ] ChromaDB uploaded and verified
- [ ] API tested in production
- [ ] Custom GPT configured and tested
- [ ] Team documentation ready
- [ ] Monitoring setup (UptimeRobot)
- [ ] Backup strategy in place
- [ ] Support process defined
- [ ] Launch communication sent

---

## 🚀 Ready to Launch!

Once all items are checked, you're ready to go live!

**Production URL:** _____________________
**Custom GPT Link:** _____________________
**Launch Date:** _____________________

---

## 📞 Support Resources

- **API Docs:** `/docs` endpoint
- **Main README:** `README.md`
- **Deployment Guide:** `DEPLOYMENT_GUIDE.md`
- **Custom GPT Guide:** `CUSTOM_GPT_SETUP.md`
- **Quick Start:** `QUICKSTART.md`

---

**Good luck with your deployment! 🎉**
