# 🚀 Deployment Guide - Trend Reports API

This guide covers deploying your Trend Reports API to production using Railway, Render, or Docker on any VPS.

---

## 📋 Pre-Deployment Checklist

Before deploying, ensure you have:

- ✅ **Processed PDFs locally** - Run `python process_pdfs.py` to create `chroma_data/`
- ✅ **Tested API locally** - Run `python test_api.py local` to verify everything works
- ✅ **Secure API key** - Generated in `.env` file (NOT the default example key)
- ✅ **Git repository** - Code pushed to GitHub/GitLab (for Railway/Render)
- ✅ **Production URL planned** - Know where you'll deploy (e.g., Railway, Render)

---

## 🚂 Option 1: Railway (Recommended - Easiest)

**Why Railway?**
- Auto-detects Dockerfile
- Built-in persistent storage
- Simple CLI deployment
- ~$5-10/month

### Step 1: Install Railway CLI

```bash
# Install via npm
npm install -g @railway/cli

# Verify installation
railway --version
```

### Step 2: Login and Initialize

```bash
# Login to Railway
railway login

# Navigate to backend folder
cd backend

# Initialize new project
railway init

# Follow prompts:
# - Project name: trend-reports-api
# - Select: Empty Project
```

### Step 3: Configure Environment Variables

```bash
# Set your API key
railway variables set API_KEY=$(grep API_KEY .env | cut -d'=' -f2)

# Set other variables
railway variables set CHROMA_DB_PATH=/app/chroma_data
railway variables set REPORTS_FOLDER="2025 Trend Reports"
railway variables set CHUNK_SIZE=800
railway variables set OVERLAP=150
```

### Step 4: Add Persistent Volume

```bash
# Create volume for ChromaDB
railway volume create chroma-data

# Mount it to /app/chroma_data
railway volume attach chroma-data /app/chroma_data
```

### Step 5: Deploy

```bash
# Deploy to Railway
railway up

# Watch build logs
railway logs
```

### Step 6: Get Production URL

```bash
# Generate public domain
railway domain

# Example output: https://trend-reports-api-production.up.railway.app
```

### Step 7: Upload ChromaDB Data

**Option A: Process PDFs on Railway**
```bash
# SSH into Railway container
railway shell

# Upload PDFs and process
# (Upload via Railway dashboard → Files)
python process_pdfs.py
exit
```

**Option B: Upload Processed Data**
```bash
# Zip your local chroma_data
tar -czf chroma_data.tar.gz chroma_data/

# Upload via Railway dashboard
# 1. Go to your project
# 2. Click "Files" tab
# 3. Upload chroma_data.tar.gz
# 4. SSH in and extract:
railway shell
tar -xzf chroma_data.tar.gz -C /app/
exit
```

### Step 8: Test Deployment

```bash
# Add production URL to .env
echo "PROD_URL=https://your-app.railway.app" >> .env

# Run tests
python test_api.py prod
```

---

## 🎨 Option 2: Render

**Why Render?**
- GitHub integration
- Auto-deploy on push
- Free SSL certificates
- $7/month starter plan

### Step 1: Push to GitHub

```bash
# Initialize git (if not already)
cd backend
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - Trend Reports API"

# Push to GitHub
git remote add origin https://github.com/yourusername/trend-reports-api.git
git push -u origin main
```

### Step 2: Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with GitHub account
3. Authorize Render to access your repo

### Step 3: Create New Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repo: `trend-reports-api`
3. Render auto-detects:
   - **Build Command:** Dockerfile detected
   - **Start Command:** Auto from Dockerfile

### Step 4: Configure Service

**Basic Settings:**
- **Name:** `trend-reports-api`
- **Region:** Choose closest to your users
- **Branch:** `main`
- **Plan:** Starter ($7/mo)

**Environment Variables:**
Click "Advanced" → Add environment variables:
```
API_KEY=<your_secure_key>
CHROMA_DB_PATH=/app/chroma_data
REPORTS_FOLDER=2025 Trend Reports
CHUNK_SIZE=800
OVERLAP=150
```

### Step 5: Add Persistent Disk

1. Scroll to **"Disk"** section
2. Click **"Add Disk"**
3. **Name:** `chroma-data`
4. **Mount Path:** `/app/chroma_data`
5. **Size:** 10 GB

### Step 6: Deploy

1. Click **"Create Web Service"**
2. Render builds and deploys automatically
3. Watch build logs in dashboard

### Step 7: Upload ChromaDB Data

**Using Render Shell:**
```bash
# From Render dashboard, click "Shell"
# Then upload your tar.gz file via dashboard

# Or use Render CLI:
render ssh trend-reports-api

# Extract uploaded data
cd /app
tar -xzf chroma_data.tar.gz
exit
```

### Step 8: Configure Auto-Deploy

Render automatically deploys on git push if you use `render.yaml` (already included in this repo).

---

## 🐳 Option 3: Docker + VPS (DigitalOcean, Linode, etc.)

**Why VPS?**
- Full control
- Potentially cheaper at scale
- Can host multiple services
- $12-20/month

### Step 1: Create VPS

**DigitalOcean Example:**
1. Create Droplet
2. Choose Ubuntu 22.04 LTS
3. Size: 2GB RAM minimum ($12/mo)
4. Add SSH key
5. Create Droplet

### Step 2: Connect and Setup Server

```bash
# SSH into server
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Verify
docker --version
```

### Step 3: Upload Code and Data

**From your local machine:**
```bash
# Create deployment package
cd backend
tar -czf deploy.tar.gz .

# Upload to server
scp deploy.tar.gz root@your-server-ip:/root/

# Upload ChromaDB data
scp -r chroma_data root@your-server-ip:/root/
```

### Step 4: Build and Run Docker Container

**On your VPS:**
```bash
# Extract code
cd /root
tar -xzf deploy.tar.gz -C /app
cd /app

# Create .env file on server
cat > .env << EOF
API_KEY=your_secure_production_key
CHROMA_DB_PATH=/app/chroma_data
REPORTS_FOLDER=2025 Trend Reports
EOF

# Build Docker image
docker build -t trend-reports-api .

# Run container
docker run -d \
  --name trend-api \
  -p 80:8000 \
  --env-file .env \
  -v /root/chroma_data:/app/chroma_data \
  --restart unless-stopped \
  trend-reports-api

# Check logs
docker logs -f trend-api
```

### Step 5: Setup Nginx (Optional - for HTTPS)

```bash
# Install Nginx
apt install nginx certbot python3-certbot-nginx -y

# Create Nginx config
cat > /etc/nginx/sites-available/trend-api << EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/trend-api /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# Get SSL certificate (free via Let's Encrypt)
certbot --nginx -d your-domain.com
```

### Step 6: Setup Auto-Restart

```bash
# Docker will auto-restart container on failure
# For server reboots, Docker handles this with --restart unless-stopped

# Optional: Create systemd service for extra reliability
cat > /etc/systemd/system/trend-api.service << EOF
[Unit]
Description=Trend Reports API
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStart=/usr/bin/docker start -a trend-api
ExecStop=/usr/bin/docker stop -t 2 trend-api

[Install]
WantedBy=multi-user.target
EOF

systemctl enable trend-api
```

---

## 🧪 Post-Deployment Testing

### Test All Endpoints

```bash
# From your local machine
export PROD_URL="https://your-production-url.com"

# Run test suite
python test_api.py prod
```

### Manual Testing

```bash
# Health check
curl https://your-production-url.com/health

# Search test
curl -X POST https://your-production-url.com/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "AI trends in advertising",
    "top_k": 3
  }'
```

### Expected Results

✅ **Health endpoint** returns:
```json
{
  "status": "healthy",
  "documents": 3842,
  "model": "all-MiniLM-L6-v2",
  "version": "1.0.0"
}
```

✅ **Search endpoint** returns:
```json
[
  {
    "content": "AI-powered personalization...",
    "source": "2025_Trends.pdf",
    "page": 12,
    "relevance_score": 0.847
  }
]
```

---

## 📊 Monitoring & Maintenance

### Setup Uptime Monitoring

**Free Option: UptimeRobot**
1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Create monitor
3. **Monitor Type:** HTTP(s)
4. **URL:** `https://your-api.com/health`
5. **Interval:** 5 minutes
6. **Alert:** Email when down

### Check Logs

**Railway:**
```bash
railway logs --tail 100
```

**Render:**
```bash
# View in dashboard: Logs tab
# Or use Render CLI
render logs trend-reports-api
```

**Docker/VPS:**
```bash
docker logs -f trend-api --tail 100
```

### Monitor Disk Usage

```bash
# Railway
railway shell
df -h /app/chroma_data

# Docker
docker exec trend-api df -h /app/chroma_data
```

### Backup ChromaDB

**Automated Backup (recommended):**
```bash
# Create backup script on server
cat > /root/backup-chroma.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec trend-api tar -czf /tmp/chroma_backup_$DATE.tar.gz /app/chroma_data
docker cp trend-api:/tmp/chroma_backup_$DATE.tar.gz /root/backups/
# Upload to S3/Google Cloud/Dropbox
EOF

chmod +x /root/backup-chroma.sh

# Add to crontab (daily at 2am)
crontab -e
# Add: 0 2 * * * /root/backup-chroma.sh
```

---

## 🔄 Updating the API

### Update Code

**Railway/Render (Git-based):**
```bash
# Make changes locally
git add .
git commit -m "Update API endpoints"
git push

# Auto-deploys on push
```

**Docker/VPS:**
```bash
# Rebuild and redeploy
docker stop trend-api
docker rm trend-api
docker build -t trend-reports-api .
docker run -d \
  --name trend-api \
  -p 80:8000 \
  --env-file .env \
  -v /root/chroma_data:/app/chroma_data \
  --restart unless-stopped \
  trend-reports-api
```

### Update PDFs/ChromaDB

**Option 1: Reprocess in Production**
```bash
# SSH/shell into production
railway shell  # or docker exec -it trend-api bash

# Upload new PDFs
# Run processing
python process_pdfs.py
```

**Option 2: Process Locally, Upload**
```bash
# Process locally
python process_pdfs.py

# Upload to production
scp -r chroma_data root@your-server-ip:/root/
# Or use Railway/Render file upload
```

---

## 💰 Cost Optimization

### Monitor Usage

**Check request volume:**
- Railway: Dashboard → Metrics
- Render: Dashboard → Metrics tab
- Docker: Use nginx access logs

### Reduce Costs

1. **Right-size your instance:**
   - Start with smallest plan
   - Scale up if needed based on usage

2. **Enable caching:**
   - Add Redis for frequent queries
   - Reduces compute costs

3. **Optimize embeddings:**
   - Use smaller model if accuracy is acceptable
   - Consider batch processing

---

## 🐛 Troubleshooting

### "Container keeps restarting"

**Check logs:**
```bash
railway logs  # or docker logs trend-api
```

**Common issues:**
- Missing environment variables
- ChromaDB path not mounted
- Insufficient memory (need 2GB minimum)

### "Search returns empty results"

**Verify ChromaDB:**
```bash
railway shell
python -c "import chromadb; print(chromadb.PersistentClient('./chroma_data').get_collection('trend_reports').count())"
```

**If count is 0:**
- ChromaDB data not uploaded
- Data lost due to missing volume mount

### "API is slow"

**Optimize:**
1. Check instance size (upgrade if <2GB RAM)
2. Reduce `top_k` default from 5 to 3
3. Add Redis caching
4. Use smaller embedding model

### "Out of disk space"

**Check usage:**
```bash
df -h /app/chroma_data
```

**Solutions:**
- Increase disk size in platform settings
- Clean up old embeddings
- Optimize chunk size (larger chunks = fewer total)

---

## 📚 Next Steps

After successful deployment:

1. ✅ **Test thoroughly** - Run `python test_api.py prod`
2. ✅ **Setup monitoring** - UptimeRobot or similar
3. ✅ **Configure Custom GPT** - See `CUSTOM_GPT_SETUP.md`
4. ✅ **Share with team** - Distribute Custom GPT link
5. ✅ **Document queries** - Track common questions for improvement

---

## 🆘 Support Resources

- **Railway Docs:** https://docs.railway.app
- **Render Docs:** https://render.com/docs
- **Docker Docs:** https://docs.docker.com
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **ChromaDB Docs:** https://docs.trychroma.com

---

**Happy Deploying! 🚀**
