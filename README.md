# 🔍 Trend Reports Search API

AI-powered semantic search engine for 2025 advertising and marketing trend reports. Built with FastAPI, ChromaDB, and FastEmbed.

## 🌟 Features

- **Semantic Search**: Query 51+ trend reports using natural language
- **Vector Database**: ChromaDB with BAAI/bge-small-en-v1.5 embeddings
- **6,109 Documents**: Chunked and indexed for optimal retrieval
- **Secure API**: API key authentication with rate limiting
- **Production Ready**: Docker support, health checks, comprehensive logging
- **Request Tracing**: Unique request IDs for debugging

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/trend-site.git
cd trend-site

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your API key
```

### Generate API Key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Process PDF Reports

```bash
# Place PDF files in "2025 Trend Reports" folder
python process_pdfs.py
```

### Run Server

```bash
uvicorn main:app --reload
```

API will be available at http://localhost:8000

## 📚 API Documentation

### Interactive Docs

Visit http://localhost:8000/docs for Swagger UI

### Endpoints

#### `GET /health`
Check API health and database status

**Response:**
```json
{
  "status": "healthy",
  "documents": 6109,
  "chroma_connection": "connected",
  "model": "BAAI/bge-small-en-v1.5",
  "version": "1.0.1",
  "environment": "development",
  "timestamp": "2025-10-25T19:00:00.000Z"
}
```

#### `POST /search`
Search trend reports

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

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
    "content": "AI is transforming digital advertising...",
    "source": "ZENDESK - CX Trends 2025_CAIG.pdf",
    "page": 4,
    "relevance_score": 0.892
  }
]
```

## 🧪 Testing

```bash
# Run test suite
python test_api.py local

# Test with curl
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"query": "marketing automation", "top_k": 3}'
```

## 🐳 Docker Deployment

```bash
# Build image
docker build -t trend-reports-api ./backend

# Run container
docker run -p 8000:8000 \
  -e API_KEY=your_key_here \
  -v $(pwd)/backend/chroma_data:/app/chroma_data \
  trend-reports-api
```

## 📦 Project Structure

```
trend-site/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── process_pdfs.py         # PDF processing pipeline
│   ├── test_api.py            # API test suite
│   ├── chromadb_mcp_server.py # ChromaDB inspector MCP
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile            # Docker configuration
│   └── .env.example          # Environment template
├── 2025 Trend Reports/        # PDF files (not in git)
├── render.yaml               # Render.com deployment config
└── README.md
```

## 🔧 Configuration

Edit `backend/.env`:

```env
# API Authentication
API_KEY=your_64_character_hex_key

# Database
CHROMA_DB_PATH=./chroma_data

# PDF Processing
REPORTS_FOLDER=../2025 Trend Reports
CHUNK_SIZE=800
OVERLAP=150

# Security
ENVIRONMENT=development
RATE_LIMIT=10/minute
ALLOWED_ORIGINS=https://chat.openai.com,https://chatgpt.com
```

## 🚀 Deployment

### Render.com (Recommended)

1. Push to GitHub
2. Connect repository to Render
3. Render auto-detects `render.yaml`
4. Deploy with one click

### Manual Deployment

```bash
# Start server
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

## 📊 Architecture

- **FastAPI**: High-performance async web framework
- **ChromaDB**: Vector database for semantic search
- **FastEmbed**: BAAI/bge-small-en-v1.5 embedding model
- **SlowAPI**: Rate limiting
- **Pydantic**: Data validation

## 🔒 Security Features

- API key authentication with constant-time comparison
- Rate limiting (10 requests/minute default)
- Request ID tracking
- Security headers (X-Frame-Options, CSP, etc.)
- Path traversal protection
- Input validation with Pydantic

## 📈 Performance

- **Query Speed**: < 500ms average
- **Embedding Dimensions**: 384
- **Database Size**: ~6,100 documents
- **Chunk Size**: 800 characters with 150 overlap

## 🛠️ Development

### MCP Servers

This project includes MCP (Model Context Protocol) servers:

- **ChromaDB Inspector**: Query and debug ChromaDB collections
- **PostgreSQL**: For future user management
- **Memory**: Caching for expensive operations
- **Sequential Thinking**: Complex problem-solving

See `.mcp.json` for configuration.

### Running Tests

```bash
# Local tests
python test_api.py local

# Production tests (set PROD_URL in .env)
python test_api.py prod

# Both
python test_api.py both
```

## 🐛 Troubleshooting

### ChromaDB Errors

```bash
# Clear and rebuild database
rm -rf backend/chroma_data
python process_pdfs.py
```

### Port Already in Use

```bash
# Find process using port 8000
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000

# Kill process
kill -9 <PID>
```

## 📝 License

Proprietary

## 👥 Contributors

- Raqib

## 🙏 Acknowledgments

- ChromaDB for vector database
- FastEmbed for embedding models
- FastAPI for the web framework
