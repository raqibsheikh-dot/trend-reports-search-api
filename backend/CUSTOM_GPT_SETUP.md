# 🤖 Custom GPT Setup Guide

Complete guide to configuring your Custom GPT to work with the Trend Reports API.

---

## 📋 Prerequisites

Before setting up Custom GPT:

- ✅ **API deployed** and accessible (Railway, Render, or VPS)
- ✅ **Production URL** obtained (e.g., `https://your-app.railway.app`)
- ✅ **API tested** using `python test_api.py prod`
- ✅ **API_KEY** ready (from your `.env` file)
- ✅ **ChatGPT Plus subscription** (required for Custom GPTs)

---

## 🚀 Step-by-Step Setup

### Step 1: Access Custom GPT Builder

1. Go to [ChatGPT](https://chat.openai.com)
2. Click **"Explore"** in the sidebar
3. Click **"Create a GPT"** (top right)

### Step 2: Configure Basic Information

In the **Create** tab, provide:

**Name:**
```
Trend Intelligence Assistant
```

**Description:**
```
Search and analyze 866MB of advertising trend reports. Provides insights from 50+ research documents with source citations.
```

**Instructions:**
```
You are a Trend Intelligence Assistant for an advertising agency. You help teams understand and apply insights from 50+ trend reports covering advertising, marketing, social media, AI, consumer behavior, and industry forecasts.

## CRITICAL RULES - FOLLOW EXACTLY

1. **ALWAYS SEARCH FIRST**: For EVERY question about trends, insights, or data, you MUST call the searchTrendReports action BEFORE answering. Never rely on your training data alone.

2. **MANDATORY CITATIONS**: Every answer MUST include source citations in this format:
   - [Source: filename.pdf, p.12]
   - Always cite the specific report and page number
   - Include multiple sources when synthesizing information

3. **SEARCH STRATEGY**:
   - Start with broad searches if specific queries return no results
   - Use 3-5 results (top_k=3 to top_k=5) for balanced coverage
   - Try related keywords if initial search fails

4. **RESPONSE FORMAT**:
   - Start with a concise summary (2-3 sentences)
   - Present key findings as bullet points
   - Include specific data, statistics, and examples
   - Cite sources throughout [Source: report.pdf, p.X]
   - Connect insights to actionable strategies
   - Highlight contradictions between reports if they exist

5. **WHEN NO RESULTS FOUND**:
   - Tell the user no matching content was found
   - Suggest alternative search terms
   - DO NOT make up information from your training data

6. **SYNTHESIS**:
   - Compare findings across multiple reports
   - Note patterns and trends
   - Point out conflicting data or perspectives
   - Provide temporal context (e.g., "According to Q4 2024 reports...")

## EXAMPLE INTERACTIONS

**User:** "What are the top AI trends in advertising?"

**Assistant:**
*[Searches: "AI trends advertising"]*

Based on the trend reports, here are the top AI trends in advertising:

• **AI-Powered Personalization**: Real-time content adaptation is becoming standard, with 78% of brands investing in AI personalization tools [Source: 2025_Digital_Trends.pdf, p.23]

• **Predictive Analytics**: Machine learning models now predict customer behavior with 85% accuracy, up from 67% in 2023 [Source: Marketing_Tech_Report.pdf, p.45]

• **Generative AI for Creative**: 62% of agencies are using AI for initial creative concepts, though human oversight remains critical [Source: Creative_Industry_Forecast.pdf, p.12]

**Actionable takeaway**: Focus on personalization engines that integrate with existing ad platforms rather than standalone tools [Source: AdTech_Stack_2025.pdf, p.34]

---

## RESPONSE STYLE

- **Professional but conversational**
- **Data-driven**: Always include numbers and specifics
- **Actionable**: Connect trends to practical strategies
- **Transparent**: Clearly indicate when information is limited
- **Comparative**: Show how trends evolved or differ by source

## WHAT YOU ARE NOT

- You are NOT a general knowledge chatbot
- You are NOT making predictions beyond what's in the reports
- You are NOT providing personal opinions
- You are ONLY synthesizing information from the trend reports

Remember: Your value is in SEARCHING and SYNTHESIZING the specific reports provided. Always search, always cite, always be specific.
```

**Conversation Starters (suggested):**
```
What are the top trends in social media advertising for 2025?
How is AI changing the advertising landscape?
What do the reports say about consumer behavior shifts?
Compare TikTok vs Instagram strategies across the reports
```

### Step 3: Configure Actions

1. Click **"Configure"** tab at the top
2. Scroll to **"Actions"** section
3. Click **"Create new action"**

### Step 4: Import OpenAPI Schema

**Option A: Import from URL (Easiest)**
1. Click **"Import from URL"**
2. Enter: `https://your-production-url.com/openapi.json`
3. Click **"Import"**
4. OpenAI validates and loads the schema

**Option B: Paste Schema**
1. Click **"Schema"**
2. Open `backend/openapi.yaml` in a text editor
3. **IMPORTANT:** Update the server URL first:
   ```yaml
   servers:
     - url: https://your-production-url.com  # Your actual URL
   ```
4. Copy the entire contents
5. Paste into the schema field
6. Click **"Save"**

### Step 5: Configure Authentication

After importing the schema:

1. OpenAI will prompt: **"Authentication required"**
2. Click **"Authentication"**
3. Select **"API Key"**
4. Configure:
   - **Authentication Type:** `API Key`
   - **API Key:** `Bearer <your_api_key_from_.env>`
   - **Auth Type:** `Bearer`
   - **Custom Header Name:** Leave blank (uses default `Authorization`)

**Example:**
```
Authentication Type: API Key
API Key: Bearer sk_live_abc123def456...  # Your actual API_KEY
Auth Type: Bearer
```

### Step 6: Test the Action

1. Still in Configure → Actions
2. Find **"Available actions"** section
3. Click **"Test"** next to `searchTrendReports`
4. Enter test query:
   ```json
   {
     "query": "AI trends",
     "top_k": 3
   }
   ```
5. Click **"Run"**
6. Verify you get results with:
   - `content` field with text
   - `source` field with PDF filename
   - `page` field with page number
   - `relevance_score` between 0-1

**If test fails:**
- Check API URL is correct
- Verify API_KEY is correct
- Test API directly: `curl https://your-url.com/health`
- Check API logs for errors

### Step 7: Configure Privacy & Sharing

1. Click **"Settings"** (gear icon in Configure tab)
2. **Name visible to others:** `Trend Intelligence Assistant`
3. **Profile Picture:** Upload a relevant icon (optional)
4. **Who can access:**
   - **"Only me"** - Private testing
   - **"Anyone with the link"** - Share with specific people
   - **"Public"** - Listed in GPT store (not recommended for internal tools)

### Step 8: Save and Test

1. Click **"Create"** (top right)
2. Your Custom GPT is now live!

---

## 🧪 Testing Your Custom GPT

### Initial Test Queries

**Test 1: Basic Search**
```
What are the top AI trends in advertising?
```

**Expected behavior:**
- Shows "Searching trend reports..." or similar indicator
- Returns results with source citations
- Cites specific pages
- Provides actionable insights

**Test 2: Specific Topic**
```
What do the reports say about TikTok advertising strategies?
```

**Expected behavior:**
- Searches for TikTok-related content
- Synthesizes findings from multiple reports
- Includes data/statistics
- Compares different perspectives if available

**Test 3: No Results Handling**
```
What is the ROI of advertising on MySpace?
```

**Expected behavior:**
- Attempts search
- Reports no results found
- Suggests alternative queries
- Does NOT make up information

**Test 4: Cross-Report Synthesis**
```
Compare what different reports say about first-party data strategies
```

**Expected behavior:**
- Searches for first-party data
- Identifies multiple source reports
- Compares and contrasts findings
- Notes agreements and contradictions

### Validation Checklist

- ✅ GPT calls API before every answer
- ✅ Citations include filename and page number
- ✅ Results are relevant to query
- ✅ Handles "no results" gracefully
- ✅ Synthesizes multiple sources
- ✅ Provides actionable insights
- ✅ Doesn't hallucinate sources

---

## 🔧 Troubleshooting

### Issue: "Action not working" or "Error calling API"

**Solutions:**
1. Check API is running: `curl https://your-url.com/health`
2. Verify API_KEY in GPT settings matches production `.env`
3. Check API logs for 401 errors (auth failure)
4. Test API directly: `python test_api.py prod`

### Issue: GPT answers without searching

**Solutions:**
1. Make instructions more explicit about ALWAYS searching
2. Add to instructions:
   ```
   CRITICAL: You MUST call searchTrendReports for EVERY question.
   If you answer without searching, you are WRONG.
   ```
3. Test with specific queries that would require report data

### Issue: Poor search results

**Solutions:**
1. Adjust `top_k` parameter (try 3-7)
2. Suggest broader queries to users
3. Check chunk size in `process_pdfs.py` (try 600-1200)
4. Reprocess PDFs with different settings

### Issue: GPT cites wrong page numbers

**Explanation:**
- Page numbers are estimates (based on character position)
- Actual PDF pages may differ slightly

**Solutions:**
1. Improve page estimation in `process_pdfs.py`
2. Update instructions to say "approximate page X"
3. Extract actual page numbers during PDF processing (enhancement)

### Issue: Slow responses

**Solutions:**
1. Check API response time: `curl -w "@curl-format.txt" https://your-url.com/search`
2. Reduce `top_k` from 5 to 3
3. Upgrade API hosting plan (more RAM/CPU)
4. Add Redis caching for frequent queries

---

## 📊 Optimizing for Your Team

### Customizing Instructions

**For Marketing Teams:**
Add to instructions:
```
Always connect trends to campaign strategies and ROI implications.
Prioritize actionable insights over theoretical trends.
```

**For Executive Teams:**
Add to instructions:
```
Provide high-level summaries with key data points.
Focus on competitive implications and market opportunities.
```

**For Creative Teams:**
Add to instructions:
```
Emphasize emerging creative formats and platform-specific strategies.
Highlight case studies and specific examples when available.
```

### Adding Conversation Starters

Customize for your common queries:
```
What platforms should we prioritize for Q2 2025?
How are our competitors using AI in advertising?
What creative formats are gaining traction?
What are the key consumer behavior shifts we should know?
Show me the most important trends for [specific industry]
```

### Setting Query Defaults

In the schema, you can adjust defaults:
```yaml
top_k:
  type: integer
  default: 5  # Change to 3 for faster, more focused results
```

---

## 🎯 Best Practices

### For Users

**DO:**
- ✅ Ask specific, focused questions
- ✅ Request comparisons across reports
- ✅ Ask for data and statistics
- ✅ Request source citations if not provided

**DON'T:**
- ❌ Expect real-time data (reports have a date range)
- ❌ Ask about topics not covered in reports
- ❌ Assume all reports agree (ask for contradictions)

### For Administrators

**DO:**
- ✅ Monitor API logs for errors
- ✅ Track common queries (for report selection)
- ✅ Update reports quarterly/annually
- ✅ Gather user feedback on result quality

**DON'T:**
- ❌ Share API_KEY publicly
- ❌ Make GPT public if using proprietary reports
- ❌ Forget to test after API updates

---

## 🔄 Updating Your Custom GPT

### When to Update

- **New reports added:** After reprocessing ChromaDB
- **API changes:** If endpoints or schema change
- **Improved instructions:** Based on user feedback
- **Better prompts:** After analyzing usage patterns

### How to Update

1. Go to [ChatGPT](https://chat.openai.com)
2. Click **"Explore"** → Your GPTs
3. Find "Trend Intelligence Assistant"
4. Click **"Edit"**
5. Make changes in Configure or Create tabs
6. Click **"Update"** (top right)

**Note:** Updates are instant for all users.

---

## 📈 Usage Analytics

### Track in ChatGPT

OpenAI provides basic analytics:
1. Go to Your GPTs
2. Click on "Trend Intelligence Assistant"
3. View: Conversations, Users (if shared)

### Track in Your API

Add logging to `main.py`:
```python
import logging
from datetime import datetime

@app.post("/search")
async def search_trends(request: SearchRequest, ...):
    # Log query
    logging.info(f"Query: {request.query} | top_k: {request.top_k} | time: {datetime.now()}")
    # ... rest of function
```

**Analyze:**
- Most common queries
- Peak usage times
- Search failures (empty results)
- Popular reports (most cited)

---

## 🚀 Advanced Features

### Multi-Action GPTs

Add additional actions:
- **Summarize Report:** Return full report summary
- **List Reports:** Show all available reports
- **Search by Date:** Filter by report publication date

### Conversation Memory

GPT automatically remembers context:
```
User: "What are AI trends?"
GPT: [searches and answers]

User: "How do these compare to last year?"
GPT: [remembers previous context, searches historical data]
```

### Integration with Other Tools

Connect to:
- **Slack:** Use GPT in Slack channels
- **Notion:** Save insights to Notion database
- **Email:** Send weekly trend summaries

---

## 📝 Template: Sharing Instructions

When sharing with your team:

```
📊 Trend Intelligence Assistant - Quick Start

1. Access: [Your GPT Link]

2. How to use:
   - Ask questions about advertising trends, consumer behavior, platform strategies
   - Be specific: "What are TikTok ad trends?" not just "trends"
   - Request sources: All answers include citations [Source: report.pdf, p.X]

3. Example queries:
   - "What are the top 3 AI trends in advertising?"
   - "Compare Instagram vs TikTok strategies"
   - "What do reports say about first-party data?"

4. Tips:
   - ✅ Ask for data and statistics
   - ✅ Request multiple perspectives
   - ✅ Follow up for deeper insights
   - ❌ Don't expect real-time data
   - ❌ Topics not in reports won't have answers

5. Covered topics:
   [List your report topics: AI, Social Media, Consumer Trends, etc.]

Questions? Contact: [Your email]
```

---

## 🆘 Support & Resources

- **OpenAI GPT Docs:** https://platform.openai.com/docs/guides/gpt
- **API Docs:** See `DEPLOYMENT_GUIDE.md`
- **Testing:** `python test_api.py`
- **Issues:** Check API logs first, then GPT action settings

---

## ✅ Final Checklist

Before sharing with your team:

- [ ] API is deployed and tested
- [ ] Custom GPT created and configured
- [ ] Actions imported and tested
- [ ] Authentication working
- [ ] Test queries return good results
- [ ] Instructions optimized for your use case
- [ ] Conversation starters added
- [ ] Sharing settings configured
- [ ] Team instructions prepared
- [ ] API monitoring setup

---

**Your Custom GPT is ready! Share the link with your team and start exploring trends. 🚀**
