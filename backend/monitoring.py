"""
Monitoring and Observability

Implements comprehensive monitoring using Prometheus metrics:
- Request/response metrics (latency, throughput, errors)
- LLM usage metrics (tokens, cost, latency)
- Cache performance metrics
- Circuit breaker metrics
- ChromaDB query metrics
- System resource metrics

Provides observability for production operations.
"""

import time
import logging
import psutil
from typing import Optional, Callable
from functools import wraps
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    Summary,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry
)
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ============================================
# Prometheus Metrics Registry
# ============================================

# Use custom registry to avoid conflicts
registry = CollectorRegistry()

# ============================================
# API Metrics
# ============================================

# Request counters
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

http_request_size_bytes = Summary(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

http_response_size_bytes = Summary(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

# ============================================
# Search Metrics
# ============================================

search_queries_total = Counter(
    'search_queries_total',
    'Total search queries executed',
    ['query_type', 'status'],
    registry=registry
)

search_duration_seconds = Histogram(
    'search_duration_seconds',
    'Search query duration in seconds',
    ['query_type'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

search_results_count = Histogram(
    'search_results_count',
    'Number of results returned per search',
    ['query_type'],
    buckets=[1, 3, 5, 10, 20, 50, 100],
    registry=registry
)

# ============================================
# LLM Metrics
# ============================================

llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['provider', 'model', 'status'],
    registry=registry
)

llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration in seconds',
    ['provider', 'model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens consumed',
    ['provider', 'model', 'token_type'],
    registry=registry
)

llm_cost_total = Counter(
    'llm_cost_total',
    'Total LLM cost in USD',
    ['provider', 'model'],
    registry=registry
)

llm_errors_total = Counter(
    'llm_errors_total',
    'Total LLM errors',
    ['provider', 'model', 'error_type'],
    registry=registry
)

# ============================================
# Cache Metrics
# ============================================

cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'status'],
    registry=registry
)

cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type'],
    registry=registry
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type'],
    registry=registry
)

cache_size_bytes = Gauge(
    'cache_size_bytes',
    'Current cache size in bytes',
    ['cache_type'],
    registry=registry
)

cache_items_count = Gauge(
    'cache_items_count',
    'Number of items in cache',
    ['cache_type'],
    registry=registry
)

# ============================================
# Circuit Breaker Metrics
# ============================================

circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['circuit_name'],
    registry=registry
)

circuit_breaker_failures_total = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['circuit_name'],
    registry=registry
)

circuit_breaker_successes_total = Counter(
    'circuit_breaker_successes_total',
    'Total circuit breaker successes',
    ['circuit_name'],
    registry=registry
)

circuit_breaker_rejections_total = Counter(
    'circuit_breaker_rejections_total',
    'Total rejected calls (circuit open)',
    ['circuit_name'],
    registry=registry
)

# ============================================
# ChromaDB Metrics
# ============================================

chromadb_queries_total = Counter(
    'chromadb_queries_total',
    'Total ChromaDB queries',
    ['operation', 'status'],
    registry=registry
)

chromadb_query_duration_seconds = Histogram(
    'chromadb_query_duration_seconds',
    'ChromaDB query duration in seconds',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    registry=registry
)

chromadb_collection_size = Gauge(
    'chromadb_collection_size',
    'Number of documents in ChromaDB collection',
    registry=registry
)

# ============================================
# System Metrics
# ============================================

system_cpu_percent = Gauge(
    'system_cpu_percent',
    'System CPU usage percentage',
    registry=registry
)

system_memory_bytes = Gauge(
    'system_memory_bytes',
    'System memory usage in bytes',
    ['type'],
    registry=registry
)

system_disk_bytes = Gauge(
    'system_disk_bytes',
    'System disk usage in bytes',
    ['type', 'path'],
    registry=registry
)

# ============================================
# Application Info
# ============================================

app_info = Info(
    'app',
    'Application information',
    registry=registry
)

# ============================================
# Metric Recording Functions
# ============================================

class MetricsRecorder:
    """Helper class for recording metrics"""

    @staticmethod
    def record_http_request(method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def record_search_query(query_type: str, duration: float, result_count: int, success: bool):
        """Record search query metrics"""
        status = "success" if success else "error"
        search_queries_total.labels(query_type=query_type, status=status).inc()
        search_duration_seconds.labels(query_type=query_type).observe(duration)
        if success:
            search_results_count.labels(query_type=query_type).observe(result_count)

    @staticmethod
    def record_llm_request(
        provider: str,
        model: str,
        duration: float,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        success: bool
    ):
        """Record LLM request metrics"""
        status = "success" if success else "error"
        llm_requests_total.labels(provider=provider, model=model, status=status).inc()

        if success:
            llm_request_duration_seconds.labels(provider=provider, model=model).observe(duration)
            llm_tokens_total.labels(provider=provider, model=model, token_type="input").inc(input_tokens)
            llm_tokens_total.labels(provider=provider, model=model, token_type="output").inc(output_tokens)
            llm_cost_total.labels(provider=provider, model=model).inc(cost)

    @staticmethod
    def record_llm_error(provider: str, model: str, error_type: str):
        """Record LLM error"""
        llm_errors_total.labels(provider=provider, model=model, error_type=error_type).inc()

    @staticmethod
    def record_cache_operation(operation: str, success: bool, cache_type: str = "default"):
        """Record cache operation"""
        status = "success" if success else "error"
        cache_operations_total.labels(operation=operation, status=status).inc()

    @staticmethod
    def record_cache_hit(cache_type: str = "default"):
        """Record cache hit"""
        cache_hits_total.labels(cache_type=cache_type).inc()

    @staticmethod
    def record_cache_miss(cache_type: str = "default"):
        """Record cache miss"""
        cache_misses_total.labels(cache_type=cache_type).inc()

    @staticmethod
    def update_cache_metrics(cache_type: str, size_bytes: int, item_count: int):
        """Update cache size metrics"""
        cache_size_bytes.labels(cache_type=cache_type).set(size_bytes)
        cache_items_count.labels(cache_type=cache_type).set(item_count)

    @staticmethod
    def update_circuit_breaker_state(circuit_name: str, state: str):
        """Update circuit breaker state (closed=0, open=1, half_open=2)"""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        circuit_breaker_state.labels(circuit_name=circuit_name).set(state_map.get(state, 0))

    @staticmethod
    def record_circuit_breaker_event(circuit_name: str, event_type: str):
        """Record circuit breaker event"""
        if event_type == "success":
            circuit_breaker_successes_total.labels(circuit_name=circuit_name).inc()
        elif event_type == "failure":
            circuit_breaker_failures_total.labels(circuit_name=circuit_name).inc()
        elif event_type == "rejection":
            circuit_breaker_rejections_total.labels(circuit_name=circuit_name).inc()

    @staticmethod
    def record_chromadb_query(operation: str, duration: float, success: bool):
        """Record ChromaDB query metrics"""
        status = "success" if success else "error"
        chromadb_queries_total.labels(operation=operation, status=status).inc()
        if success:
            chromadb_query_duration_seconds.labels(operation=operation).observe(duration)

    @staticmethod
    def update_chromadb_size(doc_count: int):
        """Update ChromaDB collection size"""
        chromadb_collection_size.set(doc_count)

    @staticmethod
    def update_system_metrics():
        """Update system resource metrics"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        system_cpu_percent.set(cpu_percent)

        # Memory
        memory = psutil.virtual_memory()
        system_memory_bytes.labels(type="used").set(memory.used)
        system_memory_bytes.labels(type="available").set(memory.available)
        system_memory_bytes.labels(type="total").set(memory.total)

        # Disk
        disk = psutil.disk_usage('/')
        system_disk_bytes.labels(type="used", path="/").set(disk.used)
        system_disk_bytes.labels(type="free", path="/").set(disk.free)
        system_disk_bytes.labels(type="total", path="/").set(disk.total)


# ============================================
# Decorators for automatic metric recording
# ============================================

def monitor_endpoint(endpoint_name: str):
    """
    Decorator to monitor endpoint performance

    Usage:
        @monitor_endpoint("/search")
        async def search_endpoint():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 200

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = 500
                raise
            finally:
                duration = time.time() - start_time
                # Get method from request if available
                method = "POST"  # Default
                MetricsRecorder.record_http_request(method, endpoint_name, status, duration)

        return wrapper
    return decorator


def monitor_search(query_type: str = "simple"):
    """
    Decorator to monitor search operations

    Usage:
        @monitor_search("semantic")
        async def semantic_search(query):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            result_count = 0

            try:
                result = await func(*args, **kwargs)
                success = True

                # Try to count results
                if isinstance(result, list):
                    result_count = len(result)
                elif isinstance(result, dict) and 'results' in result:
                    result_count = len(result['results'])

                return result
            finally:
                duration = time.time() - start_time
                MetricsRecorder.record_search_query(query_type, duration, result_count, success)

        return wrapper
    return decorator


# ============================================
# Metrics Endpoint
# ============================================

async def metrics_endpoint():
    """
    Prometheus metrics endpoint

    Returns metrics in Prometheus text format.
    """
    # Update system metrics before returning
    MetricsRecorder.update_system_metrics()

    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST
    )


# ============================================
# Initialization
# ============================================

def init_app_info(version: str, environment: str):
    """Initialize application info metrics"""
    app_info.info({
        'version': version,
        'environment': environment,
        'name': 'Trend Intelligence API'
    })
    logger.info(f"Monitoring initialized: v{version} ({environment})")


# ============================================
# Example Usage
# ============================================

if __name__ == "__main__":
    import asyncio

    async def test_monitoring():
        """Test monitoring functionality"""

        # Initialize app info
        init_app_info(version="2.0.0", environment="test")

        # Simulate HTTP requests
        print("Recording HTTP requests...")
        MetricsRecorder.record_http_request("POST", "/search", 200, 0.523)
        MetricsRecorder.record_http_request("POST", "/search", 200, 0.412)
        MetricsRecorder.record_http_request("POST", "/search", 500, 1.234)

        # Simulate search queries
        print("Recording search queries...")
        MetricsRecorder.record_search_query("simple", 0.5, 10, True)
        MetricsRecorder.record_search_query("multi_dimensional", 1.2, 5, True)
        MetricsRecorder.record_search_query("synthesis", 2.5, 8, False)

        # Simulate LLM requests
        print("Recording LLM requests...")
        MetricsRecorder.record_llm_request(
            provider="anthropic",
            model="claude-3-5-sonnet",
            duration=2.3,
            input_tokens=150,
            output_tokens=500,
            cost=0.012,
            success=True
        )

        # Simulate cache operations
        print("Recording cache operations...")
        MetricsRecorder.record_cache_hit("redis")
        MetricsRecorder.record_cache_hit("redis")
        MetricsRecorder.record_cache_miss("redis")
        MetricsRecorder.update_cache_metrics("redis", 1024000, 42)

        # Update system metrics
        print("Updating system metrics...")
        MetricsRecorder.update_system_metrics()

        # Print metrics
        print("\n" + "="*60)
        print("METRICS OUTPUT")
        print("="*60)
        metrics = generate_latest(registry).decode('utf-8')
        print(metrics)

    asyncio.run(test_monitoring())
