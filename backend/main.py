from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from typing import List, Optional, Annotated
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import chromadb
from chromadb.config import Settings as ChromaSettings
from fastembed import TextEmbedding
import os
import secrets
import logging
import time
import uuid
from contextvars import ContextVar
from dotenv import load_dotenv
from datetime import datetime, timezone

# Suppress ChromaDB telemetry to prevent posthog errors
os.environ["ANONYMIZED_TELEMETRY"] = "False"

load_dotenv()

# Context variable for request ID tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pydantic Settings for configuration validation
class Settings(BaseSettings):
    """Application settings with validation"""
    api_key: str = Field(..., min_length=32, description="API key for authentication (min 32 characters)")
    chroma_db_path: str = Field(default="./chroma_data", description="Path to ChromaDB data")
    reports_folder: str = Field(default="2025 Trend Reports", description="Folder containing PDF reports")
    chunk_size: int = Field(default=800, ge=100, le=2000, description="Text chunk size")
    overlap: int = Field(default=150, ge=0, le=500, description="Chunk overlap size")
    allowed_origins: str = Field(
        default="https://chat.openai.com,https://chatgpt.com",
        description="CORS allowed origins (comma-separated)"
    )
    environment: str = Field(default="development", description="Environment: development or production")
    rate_limit: str = Field(default="10/minute", description="Rate limit for API requests")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Ensure API key is changed from default"""
        if v == "your_secure_api_key_here":
            raise ValueError(
                "API_KEY must be changed from default value. "
                "Generate a secure key with: openssl rand -hex 32"
            )
        return v

    def get_allowed_origins_list(self) -> list[str]:
        """Convert comma-separated origins to list"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Initialize settings (will raise error if invalid)
try:
    settings = Settings()
    logger.info("✓ Settings loaded and validated successfully")
except Exception as e:
    logger.error(f"❌ Configuration error: {e}")
    raise


app = FastAPI(
    title="Trend Reports API",
    description="Search advertising trend reports for Custom GPT",
    version="1.0.1"
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS for OpenAI
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for tracing"""
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing information and request ID"""
    start_time = time.time()
    request_id = request_id_var.get()

    logger.info(
        f"[{request_id}] {request.method} {request.url.path} - Started"
    )

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} "
        f"completed in {process_time:.3f}s with status {response.status_code}"
    )
    return response


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Dependency injection for embedder and ChromaDB (replaces global state)
def get_embedder() -> TextEmbedding:
    """Dependency: Get or create embedder instance (thread-safe)"""
    if not hasattr(get_embedder, "_instance"):
        logger.info("Loading FastEmbed model (BAAI/bge-small-en-v1.5)...")
        get_embedder._instance = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        logger.info("✓ FastEmbed model loaded")
    return get_embedder._instance


def get_collection() -> chromadb.Collection:
    """Dependency: Get or create ChromaDB collection (thread-safe)"""
    if not hasattr(get_collection, "_instance"):
        logger.info(f"Connecting to ChromaDB at {settings.chroma_db_path}...")

        # Configure ChromaDB with telemetry disabled
        chroma_settings = ChromaSettings(
            anonymized_telemetry=False,
            allow_reset=True
        )

        chroma = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=chroma_settings
        )
        get_collection._instance = chroma.get_or_create_collection(name="trend_reports")
        doc_count = get_collection._instance.count()
        logger.info(f"✓ Connected to ChromaDB ({doc_count} documents)")
    return get_collection._instance


class SearchRequest(BaseModel):
    """Search request with comprehensive validation"""
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return (1-20)"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Ensure query is not just whitespace"""
        if not v.strip():
            raise ValueError("Query cannot be empty or only whitespace")
        return v.strip()


class SearchResult(BaseModel):
    content: str
    source: str
    page: int
    relevance_score: float


def verify_api_key(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify API key from Custom GPT using constant-time comparison.

    Uses secrets.compare_digest() to prevent timing attacks where an
    attacker could infer parts of the correct key by measuring response times.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Support both "Bearer <key>" and raw key formats
    token = authorization.replace("Bearer ", "").strip()

    # Use constant-time comparison to prevent timing attacks
    is_valid = secrets.compare_digest(
        token.encode("utf-8"),
        settings.api_key.encode("utf-8")
    )

    if not is_valid:
        logger.warning(f"Invalid API key attempt from {authorization[:20]}...")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return token


@app.post("/search", response_model=List[SearchResult])
@limiter.limit(settings.rate_limit)
async def search_trends(
    request: Request,
    search_request: SearchRequest,
    embedder: Annotated[TextEmbedding, Depends(get_embedder)],
    collection: Annotated[chromadb.Collection, Depends(get_collection)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Search trend reports - called by Custom GPT

    Returns relevant chunks from the trend reports with source citations.

    Args:
        request: Search query and parameters
        embedder: Injected FastEmbed model
        collection: Injected ChromaDB collection
        _: API key verification (discarded after validation)

    Returns:
        List of SearchResult objects with content, source, page, and relevance score
    """
    # Validation is now handled by Pydantic model

    try:
        # Embed the query (fastembed returns generator, get first embedding)
        query_embedding = list(embedder.embed([search_request.query]))[0].tolist()

        # Search ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=search_request.top_k,
            include=["documents", "metadatas", "distances"]
        )

        # Format for GPT
        formatted_results = []

        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append(SearchResult(
                    content=doc,
                    source=results["metadatas"][0][i].get("filename", "Unknown"),
                    page=results["metadatas"][0][i].get("page", 0),
                    relevance_score=round(1 - results["distances"][0][i], 3)  # Convert distance to similarity
                ))

        logger.info(f"Search completed: query='{search_request.query[:50]}...', results={len(formatted_results)}")
        return formatted_results

    except chromadb.errors.ChromaError as e:
        logger.error(f"ChromaDB error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search service temporarily unavailable")
    except ValueError as e:
        logger.warning(f"Invalid search parameters: {e}")
        raise HTTPException(status_code=400, detail="Invalid search parameters")
    except Exception as e:
        logger.error(f"Unexpected search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@app.get("/health")
async def health_check(
    collection: Annotated[chromadb.Collection, Depends(get_collection)]
):
    """
    Comprehensive health check endpoint.

    Returns:
        - status: "healthy", "degraded", or "unhealthy"
        - documents: Number of documents in ChromaDB
        - chroma_connection: Connection status
        - model: Embedding model name
        - version: API version
        - environment: Current environment
        - timestamp: Current server time (UTC)
    """
    health_status = {
        "status": "healthy",
        "documents": 0,
        "chroma_connection": "disconnected",
        "model": "BAAI/bge-small-en-v1.5",
        "version": "1.0.1",
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        # Test ChromaDB connection with a lightweight query
        doc_count = collection.count()

        # Perform a test query to ensure embeddings work
        collection.peek(limit=1)

        health_status["documents"] = doc_count
        health_status["chroma_connection"] = "connected"

        if doc_count == 0:
            health_status["status"] = "degraded"
            health_status["warning"] = "No documents in database"

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        raise HTTPException(
            status_code=503,
            detail="Service unavailable - database connection failed"
        )

    return health_status


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": "Trend Reports API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/search",
            "health": "/health",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
