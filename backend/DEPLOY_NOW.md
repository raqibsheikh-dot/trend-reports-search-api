# 🚀 Deploy to Railway - Step by Step

Railway CLI is installed! Follow these steps to deploy.

---

## 📋 Prerequisites Complete ✅

- ✅ Railway CLI installed (v4.10.0)
- ✅ API tested locally (all tests passed)
- ✅ ChromaDB ready (6,104 documents)
- ✅ API Key: `s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk`

---

## 🎯 Deployment Steps (10 minutes)

### Step 1: Login to Railway

**Open a new terminal/command prompt and run:**

```bash
cd backend
railway login
```

**What happens:**
- Your browser will open
- Click "Login with GitHub" or "Login with Email"
- Authorize Railway
- Return to terminal - you'll see "Logged in as [your account]"

**Don't have a Railway account?**
- Go to https://railway.app
- Sign up (free)
- Then run `railway login`

---

### Step 2: Initialize Project

**In the same terminal:**

```bash
railway init
```

**When prompted:**
- Project name: `trend-reports-api`
- Select: "Empty Project" (or create new)

**You'll see:**
```
✓ Created project trend-reports-api
```

---

### Step 3: Deploy Your Code

```bash
railway up
```

**What happens:**
- Uploads your code to Railway
- Detects Dockerfile
- Builds your container
- This takes 3-5 minutes

**You'll see:**
```
Building...
Deploying...
✓ Deployment successful
```

---

### Step 4: Set Environment Variables

```bash
railway variables set API_KEY=s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk
railway variables set CHROMA_DB_PATH=/app/chroma_data
```

**Expected output:**
```
✓ Set API_KEY
✓ Set CHROMA_DB_PATH
```

---

### Step 5: Add Persistent Storage

Railway needs a volume for ChromaDB:

```bash
railway volume create chroma-data --mount /app/chroma_data
```

**This creates:**
- A 10GB volume
- Mounted at `/app/chroma_data`
- Persists your database across deployments

---

### Step 6: Upload ChromaDB Data

**Option A: Process PDFs on Railway (Recommended)**

```bash
# SSH into Railway
railway shell

# Run processing
cd /app
python process_pdfs.py

# Exit when done (takes ~10 minutes)
exit
```

**Option B: Upload Local ChromaDB**

```bash
# Zip your local database
tar -czf chroma_data.tar.gz chroma_data/

# Upload via Railway dashboard:
# 1. Go to railway.app
# 2. Open your project
# 3. Click "Files" tab
# 4. Upload chroma_data.tar.gz
# 5. SSH in and extract:
railway shell
cd /app
tar -xzf chroma_data.tar.gz
exit
```

---

### Step 7: Get Your Production URL

```bash
railway domain
```

**Creates a public URL like:**
```
https://trend-reports-api-production.up.railway.app
```

**Save this URL!** You'll need it for Custom GPT.

---

### Step 8: Test Production Deployment

**Update your .env file:**

```bash
# Add this line to backend/.env
echo "PROD_URL=https://your-app.railway.app" >> .env
```

**Run tests:**

```bash
cd backend
venv\Scripts\activate
python test_api.py prod
```

**You should see:**
```
✓ All tests passed for Production!
```

---

## ✅ Deployment Complete Checklist

- [ ] Logged into Railway
- [ ] Initialized project
- [ ] Deployed code (`railway up`)
- [ ] Set environment variables
- [ ] Created volume for ChromaDB
- [ ] Uploaded/processed ChromaDB data
- [ ] Got production URL
- [ ] Tested production API

---

## 🐛 Troubleshooting

### "railway: command not found"
```bash
npm install -g @railway/cli
```

### "Not logged in"
```bash
railway login
# Browser will open for authentication
```

### "Build failed"
Check logs:
```bash
railway logs
```

### "API returns 500 error"
Check if ChromaDB is mounted:
```bash
railway shell
ls -la /app/chroma_data
```

---

## 💰 Cost Estimate

**Railway Pricing:**
- **Hobby Plan:** $5/month for small projects
- **Pro Plan:** $20/month for production use
- **Free Trial:** 500 hours/month (about $5 credit)

**Your API will use:**
- ~$7-10/month on Pro plan
- Includes: compute, storage, bandwidth

---

## 🎯 After Deployment

### Update OpenAPI Schema

Edit `backend/openapi.yaml` line 12:

```yaml
servers:
  - url: https://your-actual-railway-url.up.railway.app
```

### Configure Custom GPT

See `CUSTOM_GPT_SETUP.md` - you're ready to:
1. Create Custom GPT in ChatGPT
2. Import your OpenAPI schema
3. Add authentication
4. Test and publish!

---

## 📞 Next Steps

1. ✅ Deploy to Railway (follow steps above)
2. 🤖 Configure Custom GPT
3. 👥 Share with your team
4. 📊 Monitor usage and costs

---

**Ready to deploy? Run the commands above in your terminal!** 🚀

**Questions or issues?** Check the troubleshooting section or see `DEPLOYMENT_GUIDE.md`.
