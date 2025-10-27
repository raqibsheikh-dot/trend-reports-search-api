from fastapi import FastAPI, HTTPException, Header, Depends, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict
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

# Import caching layer
from cache import get_cache_from_env, QueryCache

# Import ChromaDB safe wrapper
from chromadb_wrapper import (
    SafeChromaDBWrapper,
    create_safe_wrapper,
    ChromaDBError,
    ChromaDBConnectionError,
    ChromaDBQueryError,
    ChromaDBTimeoutError
)

# Import input validation
from input_validation import (
    sanitize_query,
    validate_search_request,
    ValidationError as InputValidationError,
    SuspiciousInputError
)

# Import advanced features
from categorization import Categorizer, TrendCategory
from synthesis import TrendSynthesizer
from response_formatter import ResponseFormatter, ResponseStyle
from advanced_search import AdvancedSearchEngine, AdvancedSearchRequest

# Import services
from services import SearchService, create_search_service

# Import resilience and monitoring
from resilience import (
    with_timeout,
    retry_with_backoff,
    get_circuit_breaker,
    get_all_circuit_breaker_stats,
    get_health_checker,
    HealthStatus,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    TimeoutError as ResilienceTimeoutError
)
from monitoring import (
    MetricsRecorder,
    metrics_endpoint,
    init_app_info
)

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

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    def get_allowed_origins_list(self) -> list[str]:
        """Convert comma-separated origins to list"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


# Initialize settings (will raise error if invalid)
try:
    settings = Settings()
    logger.info("✓ Settings loaded and validated successfully")
except Exception as e:
    logger.error(f"❌ Configuration error: {e}")
    raise


app = FastAPI(
    title="Trend Intelligence API",
    description="AI-powered creative strategy insights across 51 trend reports",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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

# ============================================================================
# API v1 Router
# ============================================================================
v1_router = APIRouter(
    prefix="/v1",
    tags=["v1"],
    responses={
        401: {"description": "Unauthorized - Invalid API key"},
        429: {"description": "Too Many Requests - Rate limit exceeded"},
        503: {"description": "Service Unavailable - Temporary issue"},
    }
)

# Initialize monitoring on startup
@app.on_event("startup")
async def startup_event():
    """Initialize monitoring and health checks"""
    init_app_info(version="2.0.0", environment=settings.environment)
    logger.info("✓ Application started with monitoring enabled")

    # Register health checks
    health_checker = get_health_checker()

    async def check_chromadb():
        """Check if ChromaDB is accessible"""
        collection = get_collection()
        count = collection.count()
        return {"status": "healthy", "document_count": count}

    async def check_cache():
        """Check if cache is accessible"""
        cache = get_cache()
        if cache:
            stats = cache.get_stats()
            return {"status": "healthy", "stats": stats}
        return {"status": "disabled"}

    health_checker.register_check("chromadb", check_chromadb)
    health_checker.register_check("cache", check_cache)

    logger.info("✓ Health checks registered")


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


# Monitoring middleware
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    """Record metrics for all requests"""
    start_time = time.time()
    method = request.method
    endpoint = request.url.path

    # Skip metrics endpoint to avoid recursion
    if endpoint == "/metrics":
        return await call_next(request)

    try:
        response = await call_next(request)
        status = response.status_code

        # Record successful request
        duration = time.time() - start_time
        MetricsRecorder.record_http_request(method, endpoint, status, duration)

        return response
    except Exception as e:
        # Record failed request
        duration = time.time() - start_time
        MetricsRecorder.record_http_request(method, endpoint, 500, duration)
        raise


# Dependency injection for embedder and ChromaDB (replaces global state)
def get_embedder() -> TextEmbedding:
    """Dependency: Get or create embedder instance (thread-safe)"""
    if not hasattr(get_embedder, "_instance"):
        logger.info("Loading FastEmbed model (BAAI/bge-small-en-v1.5)...")
        get_embedder._instance = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        logger.info("✓ FastEmbed model loaded")
    return get_embedder._instance


def get_collection() -> SafeChromaDBWrapper:
    """Dependency: Get or create safe ChromaDB collection wrapper (thread-safe)"""
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
        collection = chroma.get_or_create_collection(name="trend_reports")

        # Wrap with safe error handling
        get_collection._instance = create_safe_wrapper(
            collection=collection,
            timeout_seconds=10,
            max_retries=3
        )

        doc_count = collection.count()
        logger.info(f"✓ Connected to ChromaDB ({doc_count} documents) with safe wrapper")
    return get_collection._instance


def get_cache() -> Optional[QueryCache]:
    """Dependency: Get or create cache instance (thread-safe)"""
    if not hasattr(get_cache, "_instance"):
        get_cache._instance = get_cache_from_env()
        if get_cache._instance:
            logger.info("✓ Query cache enabled")
        else:
            logger.info("Query cache disabled")
    return get_cache._instance


def get_llm() -> Optional['LLMService']:
    """Dependency: Get or create LLM service instance (thread-safe)"""
    if not hasattr(get_llm, "_instance"):
        from llm_service import get_llm_service
        get_llm._instance = get_llm_service()
        if get_llm._instance:
            logger.info("✓ LLM service enabled")
        else:
            logger.info("LLM service disabled (advanced features limited)")
    return get_llm._instance


def get_categorizer(llm: Annotated[Optional['LLMService'], Depends(get_llm)]) -> Categorizer:
    """Dependency: Get categorizer instance"""
    if not hasattr(get_categorizer, "_instance"):
        get_categorizer._instance = Categorizer(
            llm_service=llm,
            use_hybrid=llm is not None
        )
    return get_categorizer._instance


def get_synthesizer(llm: Annotated[Optional['LLMService'], Depends(get_llm)]) -> TrendSynthesizer:
    """Dependency: Get synthesis engine instance"""
    if not hasattr(get_synthesizer, "_instance"):
        get_synthesizer._instance = TrendSynthesizer(llm_service=llm)
    return get_synthesizer._instance


def get_formatter(llm: Annotated[Optional['LLMService'], Depends(get_llm)]) -> ResponseFormatter:
    """Dependency: Get response formatter instance"""
    if not hasattr(get_formatter, "_instance"):
        get_formatter._instance = ResponseFormatter(llm_service=llm)
    return get_formatter._instance


def get_advanced_search(
    embedder: Annotated[TextEmbedding, Depends(get_embedder)],
    collection: Annotated[SafeChromaDBWrapper, Depends(get_collection)],
    llm: Annotated[Optional['LLMService'], Depends(get_llm)]
) -> AdvancedSearchEngine:
    """Dependency: Get advanced search engine instance"""
    if not hasattr(get_advanced_search, "_instance"):
        get_advanced_search._instance = AdvancedSearchEngine(
            embedder=embedder,
            collection=collection,
            llm_service=llm
        )
    return get_advanced_search._instance


def get_search_service(
    collection: Annotated[SafeChromaDBWrapper, Depends(get_collection)],
    embedder: Annotated[TextEmbedding, Depends(get_embedder)],
    cache: Annotated[Optional[QueryCache], Depends(get_cache)],
    synthesizer: Annotated[TrendSynthesizer, Depends(get_synthesizer)],
    formatter: Annotated[ResponseFormatter, Depends(get_formatter)],
    advanced_engine: Annotated[AdvancedSearchEngine, Depends(get_advanced_search)]
) -> SearchService:
    """Dependency: Get search service instance with all dependencies"""
    if not hasattr(get_search_service, "_instance"):
        get_search_service._instance = create_search_service(
            collection=collection,
            embedder=embedder,
            cache=cache,
            synthesizer=synthesizer,
            formatter=formatter,
            advanced_engine=advanced_engine
        )
        logger.info("✓ SearchService initialized")
    return get_search_service._instance


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


# ============================================================================
# ROUTER INCLUDES
# ============================================================================
# Import routers after all dependencies are defined to avoid circular imports
from routers.search_router import router as search_router
from routers.admin_router import router as admin_router
from routers.util_router import router as util_router

# Include all routers in v1_router
v1_router.include_router(search_router)
v1_router.include_router(admin_router)
v1_router.include_router(util_router)

# Note: Endpoints have been organized into domain routers:
# - routers/search_router.py: POST /search, /search/synthesized, /search/structured, /search/advanced
# - routers/admin_router.py: GET /cache/stats, POST /cache/clear
# - routers/util_router.py: GET /categories, GET /llm/stats

# ============================================================================
# APP-LEVEL ENDPOINTS (not versioned)
# ============================================================================
# Note: All /v1 endpoints have been moved to routers/
# Only health and metrics remain at app level


@app.get("/health")
async def health_check(
    collection: Annotated[chromadb.Collection, Depends(get_collection)]
):
    """
    Comprehensive health check endpoint with resilience monitoring.

    Returns:
        - status: "healthy", "degraded", or "unhealthy"
        - components: Health status of all components
        - circuit_breakers: Circuit breaker states
        - version: API version
        - timestamp: Current server time (UTC)
    """
    # Run comprehensive health checks
    health_checker = get_health_checker()
    health_result = await health_checker.check_health()

    # Get circuit breaker stats
    circuit_stats = get_all_circuit_breaker_stats()

    # Build response
    response = {
        "status": health_result.status,
        "version": "2.0.0",
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": health_result.details,
        "circuit_breakers": circuit_stats
    }

    # Return appropriate status code
    if health_result.status == HealthStatus.UNHEALTHY:
        raise HTTPException(status_code=503, detail=response)
    elif health_result.status == HealthStatus.DEGRADED:
        response["warning"] = "System is degraded but operational"

    return response


@app.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    """
    return await metrics_endpoint()


@app.get("/")
async def root():
    """Root endpoint with API info and versioning"""
    return {
        "name": "Trend Intelligence API - Creative Strategy Intelligence",
        "version": "2.0.0",
        "api_version": "v1",
        "description": "AI-powered trend analysis across 51+ reports with 6,109+ documents",
        "endpoints": {
            "v1_core": {
                "search": "POST /v1/search - Basic semantic search",
                "categories": "GET /v1/categories - List trend categories"
            },
            "v1_advanced_search": {
                "synthesized": "POST /v1/search/synthesized - Cross-report synthesis with meta-trends",
                "structured": "POST /v1/search/structured - Formatted strategic response",
                "advanced": "POST /v1/search/advanced - Multi-dimensional, scenario, and trend stacking queries"
            },
            "v1_utilities": {
                "cache_stats": "GET /v1/cache/stats - Query cache performance",
                "cache_clear": "POST /v1/cache/clear - Clear cache (auth required)",
                "llm_stats": "GET /v1/llm/stats - LLM usage and costs"
            },
            "operational": {
                "health": "GET /health - System health check with resilience monitoring",
                "metrics": "GET /metrics - Prometheus metrics endpoint"
            },
            "documentation": {
                "swagger": "/docs - Interactive API documentation",
                "openapi": "/openapi.json - OpenAPI specification"
            }
        },
        "backward_compatibility": {
            "note": "Unversioned endpoints redirect to /v1/",
            "examples": [
                "/search → /v1/search",
                "/categories → /v1/categories"
            ]
        },
        "features": [
            "✅ Semantic search across 51+ trend reports",
            "✅ Cross-report synthesis & meta-trend identification",
            "✅ Structured strategic responses for presentations",
            "✅ Multi-dimensional query support",
            "✅ Query caching for performance",
            "✅ LLM-powered analysis (Claude/GPT)",
            "✅ Circuit breakers & fault tolerance",
            "✅ Prometheus metrics & monitoring",
            "✅ API versioning for safe evolution"
        ],
        "authentication": "Bearer token required (Authorization: Bearer <token>)",
        "docs_url": "/docs"
    }


# ============================================================================
# Include v1 Router
# ============================================================================
app.include_router(v1_router)


# ============================================================================
# Backward Compatibility Redirects
# ============================================================================
@app.post("/search")
async def search_redirect():
    """Redirect to versioned endpoint"""
    return RedirectResponse(url="/v1/search", status_code=307)

@app.post("/search/synthesized")
async def search_synthesized_redirect():
    """Redirect to versioned endpoint"""
    return RedirectResponse(url="/v1/search/synthesized", status_code=307)

@app.post("/search/structured")
async def search_structured_redirect():
    """Redirect to versioned endpoint"""
    return RedirectResponse(url="/v1/search/structured", status_code=307)

@app.post("/search/advanced")
async def search_advanced_redirect():
    """Redirect to versioned endpoint"""
    return RedirectResponse(url="/v1/search/advanced", status_code=307)

@app.get("/categories")
async def categories_redirect():
    """Redirect to versioned endpoint"""
    return RedirectResponse(url="/v1/categories", status_code=307)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
