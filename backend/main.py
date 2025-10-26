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

# Import caching layer
from cache import get_cache_from_env, QueryCache

# Import advanced features
from categorization import Categorizer, TrendCategory
from synthesis import TrendSynthesizer
from response_formatter import ResponseFormatter, ResponseStyle
from advanced_search import AdvancedSearchEngine, AdvancedSearchRequest

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
    title="Trend Intelligence API",
    description="AI-powered creative strategy insights across 51 trend reports",
    version="2.0.0"
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
    collection: Annotated[chromadb.Collection, Depends(get_collection)],
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
    cache: Annotated[Optional[QueryCache], Depends(get_cache)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Search trend reports - called by Custom GPT

    Returns relevant chunks from the trend reports with source citations.
    Results are cached for improved performance.

    Args:
        request: Search query and parameters
        embedder: Injected FastEmbed model
        collection: Injected ChromaDB collection
        cache: Injected cache instance (optional)
        _: API key verification (discarded after validation)

    Returns:
        List of SearchResult objects with content, source, page, and relevance score
    """
    request_id = request_id_var.get()

    # Check cache first
    if cache:
        cached_results = cache.get_search_results(
            query=search_request.query,
            top_k=search_request.top_k
        )
        if cached_results:
            logger.info(
                f"[{request_id}] Cache HIT: query='{search_request.query[:50]}...', "
                f"results={len(cached_results)}"
            )
            # Convert cached dicts back to SearchResult objects
            return [SearchResult(**r) for r in cached_results]

        logger.debug(f"[{request_id}] Cache MISS: query='{search_request.query[:50]}...'")

    # Cache miss or caching disabled - perform search
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

        # Cache the results
        if cache and formatted_results:
            # Convert SearchResult objects to dicts for caching
            cache_data = [r.model_dump() for r in formatted_results]
            cache.set_search_results(
                query=search_request.query,
                top_k=search_request.top_k,
                results=cache_data
            )

        logger.info(
            f"[{request_id}] Search completed: query='{search_request.query[:50]}...', "
            f"results={len(formatted_results)}"
        )
        return formatted_results

    except chromadb.errors.ChromaError as e:
        logger.error(f"[{request_id}] ChromaDB error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search service temporarily unavailable")
    except ValueError as e:
        logger.warning(f"[{request_id}] Invalid search parameters: {e}")
        raise HTTPException(status_code=400, detail="Invalid search parameters")
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@app.post("/search/synthesized")
@limiter.limit(settings.rate_limit)
async def search_with_synthesis(
    request: Request,
    search_request: SearchRequest,
    embedder: Annotated[TextEmbedding, Depends(get_embedder)],
    collection: Annotated[chromadb.Collection, Depends(get_collection)],
    synthesizer: Annotated[TrendSynthesizer, Depends(get_synthesizer)],
    cache: Annotated[Optional[QueryCache], Depends(get_cache)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Search with cross-report synthesis

    Identifies meta-trends, consensus, and contradictions across sources.
    Requires LLM integration for best results.

    Returns:
        Synthesized insights with meta-trends and analysis
    """
    request_id = request_id_var.get()

    # Perform base search
    base_results = await search_trends(
        request, search_request, embedder, collection, cache, _
    )

    # Convert SearchResult objects to dicts for synthesis
    results_dicts = [r.model_dump() for r in base_results]

    # Perform synthesis
    try:
        synthesis_result = await synthesizer.synthesize(
            query=search_request.query,
            results=results_dicts,
            min_sources_for_meta=2
        )

        logger.info(
            f"[{request_id}] Synthesis completed: "
            f"{len(synthesis_result.meta_trends)} meta-trends identified"
        )

        return synthesizer.format_for_display(synthesis_result)

    except Exception as e:
        logger.error(f"[{request_id}] Synthesis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Synthesis failed. Ensure LLM service is configured."
        )


@app.post("/search/structured")
@limiter.limit(settings.rate_limit)
async def search_with_structure(
    request: Request,
    search_request: SearchRequest,
    embedder: Annotated[TextEmbedding, Depends(get_embedder)],
    collection: Annotated[chromadb.Collection, Depends(get_collection)],
    formatter: Annotated[ResponseFormatter, Depends(get_formatter)],
    cache: Annotated[Optional[QueryCache], Depends(get_cache)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Search with structured response format

    Returns results formatted according to claude.md framework:
    - Relevant trends
    - Context
    - Data points
    - Applications
    - Connections
    - Next steps

    Requires LLM integration for best results.

    Returns:
        Structured response with actionable insights
    """
    request_id = request_id_var.get()

    # Perform base search
    base_results = await search_trends(
        request, search_request, embedder, collection, cache, _
    )

    # Convert to dicts
    results_dicts = [r.model_dump() for r in base_results]

    # Format response
    try:
        structured_response = await formatter.format_response(
            query=search_request.query,
            results=results_dicts
        )

        logger.info(
            f"[{request_id}] Structured response generated: "
            f"{len(structured_response.relevant_trends)} trends, "
            f"{len(structured_response.applications)} applications"
        )

        return structured_response.model_dump()

    except Exception as e:
        logger.error(f"[{request_id}] Response formatting failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Response formatting failed. Ensure LLM service is configured."
        )


@app.post("/search/advanced")
@limiter.limit(settings.rate_limit)
async def advanced_search(
    request: Request,
    search_request: AdvancedSearchRequest,
    advanced_engine: Annotated[AdvancedSearchEngine, Depends(get_advanced_search)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Advanced search with multiple query strategies

    Supported query types:
    - simple: Standard vector search
    - multi_dimensional: Intersection of multiple concepts
    - scenario: "What if" scenario analysis
    - trend_stack: Combine specific trends

    Args:
        search_request: Advanced search request with query_type and parameters

    Returns:
        Results optimized for the selected query type
    """
    request_id = request_id_var.get()

    try:
        results = await advanced_engine.search(search_request)

        logger.info(
            f"[{request_id}] Advanced search ({search_request.query_type}): "
            f"{len(results.get('results', []))} results"
        )

        return results

    except Exception as e:
        logger.error(f"[{request_id}] Advanced search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Advanced search failed: {str(e)}"
        )


@app.get("/categories")
async def list_categories():
    """
    List available trend categories

    Returns:
        List of category names and descriptions
    """
    return {
        "categories": [
            {
                "id": cat.name,
                "name": cat.value,
                "description": f"Trends related to {cat.value.lower()}"
            }
            for cat in TrendCategory
        ]
    }


@app.get("/llm/stats")
async def llm_stats(
    llm: Annotated[Optional['LLMService'], Depends(get_llm)]
):
    """
    Get LLM usage statistics

    Returns cost tracking and usage metrics for LLM-powered features.
    """
    if not llm:
        return {
            "enabled": False,
            "message": "LLM service not configured"
        }

    stats = llm.get_cost_stats()
    return {
        "enabled": True,
        **stats
    }


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


@app.get("/cache/stats")
async def cache_stats(
    cache: Annotated[Optional[QueryCache], Depends(get_cache)]
):
    """
    Get cache statistics

    Returns:
        Cache performance metrics including hit/miss rates, size, etc.
    """
    if not cache:
        return {
            "enabled": False,
            "message": "Caching is disabled"
        }

    stats = cache.get_stats()
    return {
        "enabled": True,
        **stats
    }


@app.post("/cache/clear")
async def clear_cache(
    cache: Annotated[Optional[QueryCache], Depends(get_cache)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Clear all cached search results

    Requires authentication. Useful for invalidating cache after data updates.

    Returns:
        Success status
    """
    if not cache:
        return {"success": False, "message": "Caching is disabled"}

    success = cache.clear_all()
    if success:
        logger.info("Cache cleared via API")
        return {"success": True, "message": "Cache cleared successfully"}
    else:
        logger.error("Failed to clear cache")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": "Trend Intelligence API - Creative Strategy Intelligence",
        "version": "2.0.0",
        "description": "AI-powered trend analysis across 51+ reports with 6,109+ documents",
        "endpoints": {
            "core": {
                "search": "POST /search - Basic semantic search",
                "health": "GET /health - System health check with resilience monitoring",
                "metrics": "GET /metrics - Prometheus metrics endpoint"
            },
            "advanced_search": {
                "synthesized": "POST /search/synthesized - Cross-report synthesis with meta-trends",
                "structured": "POST /search/structured - Formatted strategic response",
                "advanced": "POST /search/advanced - Multi-dimensional, scenario, and trend stacking queries"
            },
            "utilities": {
                "categories": "GET /categories - List trend categories",
                "cache_stats": "GET /cache/stats - Query cache performance",
                "cache_clear": "POST /cache/clear - Clear cache (auth required)",
                "llm_stats": "GET /llm/stats - LLM usage and costs"
            },
            "documentation": {
                "swagger": "/docs - Interactive API documentation",
                "openapi": "/openapi.json - OpenAPI specification"
            }
        },
        "features": [
            "Semantic search across 51+ trend reports",
            "Cross-report synthesis & meta-trend identification",
            "Structured strategic responses for presentations",
            "Multi-dimensional query support",
            "Query caching for performance",
            "LLM-powered analysis (Claude/GPT)",
            "Automated backups with S3 support",
            "Cost tracking & budget limits",
            "Circuit breakers for fault tolerance",
            "Prometheus metrics & monitoring",
            "Request timeouts & retry logic"
        ],
        "authentication": "Bearer token required (see docs)"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
