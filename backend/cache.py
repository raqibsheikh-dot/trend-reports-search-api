"""
Query Caching Layer for Trend Reports API

Supports both Redis (production) and in-memory LRU cache (development).
Caching dramatically improves response times for repeated queries.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Optional, List
import os

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache implementations"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Store value in cache with TTL (time-to-live in seconds)"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        pass

    @abstractmethod
    def clear(self) -> bool:
        """Clear entire cache"""
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """Get cache statistics"""
        pass


class RedisCache(CacheBackend):
    """Redis-based cache implementation for production with connection pooling"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl: int = 3600,
        max_connections: int = 10,
        socket_connect_timeout: int = 5,
        socket_keepalive: bool = True
    ):
        """
        Initialize Redis cache connection with connection pooling

        Args:
            redis_url: Redis connection URL
            ttl: Default time-to-live for cached items (seconds)
            max_connections: Maximum number of connections in pool (default: 10)
            socket_connect_timeout: Connection timeout in seconds (default: 5)
            socket_keepalive: Enable TCP keepalive (default: True)
        """
        try:
            import redis

            # Create connection pool for better concurrent performance
            pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                socket_connect_timeout=socket_connect_timeout,
                socket_keepalive=socket_keepalive,
                decode_responses=True
            )

            # Create Redis client with connection pool
            self.redis = redis.Redis(connection_pool=pool)
            self.ttl = ttl
            self.max_connections = max_connections

            # Test connection
            self.redis.ping()
            logger.info(
                f"✓ Connected to Redis at {redis_url} "
                f"(pool: {max_connections} connections)"
            )
        except ImportError:
            logger.error("Redis package not installed. Install with: pip install redis")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from Redis"""
        try:
            data = self.redis.get(key)
            if data:
                logger.debug(f"Cache HIT: {key[:20]}...")
                return json.loads(data)
            logger.debug(f"Cache MISS: {key[:20]}...")
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Store value in Redis with TTL"""
        try:
            ttl = ttl or self.ttl
            serialized = json.dumps(value)
            self.redis.setex(key, ttl, serialized)
            logger.debug(f"Cached: {key[:20]}... (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    def clear(self) -> bool:
        """Clear entire Redis database"""
        try:
            self.redis.flushdb()
            logger.info("Redis cache cleared")
            return True
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return False

    def get_stats(self) -> dict:
        """Get Redis statistics including connection pool info"""
        try:
            info = self.redis.info()

            # Get connection pool stats
            pool = self.redis.connection_pool
            pool_stats = {
                "max_connections": self.max_connections,
                "connections_created": len(pool._created_connections) if hasattr(pool, '_created_connections') else "N/A",
                "available_connections": len(pool._available_connections) if hasattr(pool, '_available_connections') else "N/A",
                "in_use_connections": len(pool._in_use_connections) if hasattr(pool, '_in_use_connections') else "N/A",
            }

            return {
                "type": "redis",
                "connected": True,
                "keys": self.redis.dbsize(),
                "memory_used": info.get("used_memory_human", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "connection_pool": pool_stats
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {"type": "redis", "connected": False, "error": str(e)}


class LRUCache(CacheBackend):
    """In-memory LRU cache implementation for development"""

    def __init__(self, max_size: int = 256):
        """
        Initialize in-memory LRU cache

        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        self.sets = 0
        logger.info(f"✓ Initialized LRU cache (max_size={max_size})")

        # Create the actual LRU cache function
        self._cache = {}  # Store for manual tracking
        self._lru_get = lru_cache(maxsize=max_size)(self._cache_get)

    def _cache_get(self, key: str) -> Optional[str]:
        """Internal method used by lru_cache decorator"""
        return self._cache.get(key)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from LRU cache"""
        try:
            data = self._lru_get(key)
            if data:
                self.hits += 1
                logger.debug(f"Cache HIT: {key[:20]}...")
                return json.loads(data)
            self.misses += 1
            logger.debug(f"Cache MISS: {key[:20]}...")
            return None
        except Exception as e:
            logger.error(f"LRU get error: {e}")
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Store value in LRU cache

        Note: TTL is ignored in LRU cache (not supported by functools.lru_cache)
        Items are evicted based on LRU policy when max_size is reached
        """
        try:
            serialized = json.dumps(value)
            self._cache[key] = serialized
            self.sets += 1
            # Clear the lru_cache to force recomputation
            self._lru_get.cache_clear()
            logger.debug(f"Cached: {key[:20]}...")
            return True
        except Exception as e:
            logger.error(f"LRU set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from LRU cache"""
        try:
            if key in self._cache:
                del self._cache[key]
                self._lru_get.cache_clear()
            return True
        except Exception as e:
            logger.error(f"LRU delete error: {e}")
            return False

    def clear(self) -> bool:
        """Clear entire LRU cache"""
        try:
            self._cache.clear()
            self._lru_get.cache_clear()
            logger.info("LRU cache cleared")
            return True
        except Exception as e:
            logger.error(f"LRU clear error: {e}")
            return False

    def get_stats(self) -> dict:
        """Get LRU cache statistics"""
        cache_info = self._lru_get.cache_info()
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "type": "lru",
            "max_size": self.max_size,
            "current_size": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "hit_rate_percent": round(hit_rate, 2),
            "functools_stats": {
                "hits": cache_info.hits,
                "misses": cache_info.misses,
                "maxsize": cache_info.maxsize,
                "currsize": cache_info.currsize,
            },
        }


class QueryCache:
    """
    High-level query caching interface for search results

    Automatically generates cache keys from query parameters and manages
    storage/retrieval in the configured cache backend.
    """

    def __init__(self, backend: CacheBackend, prefix: str = "search"):
        """
        Initialize query cache

        Args:
            backend: Cache backend implementation (Redis or LRU)
            prefix: Prefix for cache keys (useful for namespacing)
        """
        self.backend = backend
        self.prefix = prefix
        logger.info(f"✓ QueryCache initialized with {backend.__class__.__name__}")

    def _make_cache_key(self, query: str, top_k: int, **kwargs) -> str:
        """
        Generate deterministic cache key from query parameters

        Args:
            query: Search query text
            top_k: Number of results
            **kwargs: Additional parameters (e.g., category, filters)

        Returns:
            Hex-encoded SHA256 hash suitable as cache key
        """
        # Create deterministic string representation of all parameters
        key_data = {
            "query": query.lower().strip(),
            "top_k": top_k,
            **kwargs  # Include any additional parameters (categories, filters, etc.)
        }

        # Sort keys for consistent hashing
        key_string = json.dumps(key_data, sort_keys=True)

        # Generate hash
        hash_digest = hashlib.sha256(key_string.encode()).hexdigest()

        # Return prefixed key
        return f"{self.prefix}:{hash_digest[:16]}"

    def get_search_results(self, query: str, top_k: int, **kwargs) -> Optional[List[dict]]:
        """
        Retrieve cached search results

        Args:
            query: Search query text
            top_k: Number of results
            **kwargs: Additional parameters

        Returns:
            Cached results or None if not found
        """
        cache_key = self._make_cache_key(query, top_k, **kwargs)
        return self.backend.get(cache_key)

    def set_search_results(
        self, query: str, top_k: int, results: List[dict], ttl: int = None, **kwargs
    ) -> bool:
        """
        Cache search results

        Args:
            query: Search query text
            top_k: Number of results
            results: Search results to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (optional)
            **kwargs: Additional parameters

        Returns:
            True if cached successfully
        """
        cache_key = self._make_cache_key(query, top_k, **kwargs)
        return self.backend.set(cache_key, results, ttl)

    def invalidate_query(self, query: str, top_k: int, **kwargs) -> bool:
        """
        Invalidate specific cached query

        Args:
            query: Search query text
            top_k: Number of results
            **kwargs: Additional parameters

        Returns:
            True if invalidated successfully
        """
        cache_key = self._make_cache_key(query, top_k, **kwargs)
        return self.backend.delete(cache_key)

    def clear_all(self) -> bool:
        """Clear entire cache"""
        return self.backend.clear()

    def get_stats(self) -> dict:
        """Get cache statistics"""
        return self.backend.get_stats()


# Factory function for creating cache instance
def create_cache(
    enable_cache: bool = True,
    use_lru: bool = False,
    redis_url: str = "redis://localhost:6379",
    lru_size: int = 256,
    ttl: int = 3600,
    max_connections: int = 10,
) -> Optional[QueryCache]:
    """
    Factory function to create appropriate cache instance based on configuration

    Args:
        enable_cache: Whether to enable caching at all
        use_lru: Use LRU cache instead of Redis
        redis_url: Redis connection URL
        lru_size: LRU cache size
        ttl: Default TTL for cached items
        max_connections: Maximum Redis connections in pool (default: 10)

    Returns:
        QueryCache instance or None if caching is disabled
    """
    if not enable_cache:
        logger.info("Caching is disabled")
        return None

    try:
        if use_lru:
            backend = LRUCache(max_size=lru_size)
        else:
            backend = RedisCache(
                redis_url=redis_url,
                ttl=ttl,
                max_connections=max_connections
            )

        return QueryCache(backend=backend)

    except Exception as e:
        logger.error(f"Failed to initialize cache: {e}")
        logger.warning("Continuing without caching")
        return None


# Convenience function to get cache from environment variables
def get_cache_from_env() -> Optional[QueryCache]:
    """
    Create cache instance from environment variables

    Environment variables:
        - ENABLE_CACHE: Enable/disable caching (default: true)
        - USE_LRU_CACHE: Use LRU instead of Redis (default: false)
        - REDIS_URL: Redis connection URL
        - LRU_CACHE_SIZE: LRU cache size (default: 256)
        - CACHE_TTL: Cache TTL in seconds (default: 3600)
        - REDIS_MAX_CONNECTIONS: Max connections in pool (default: 10)

    Returns:
        QueryCache instance or None
    """
    enable_cache = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    use_lru = os.getenv("USE_LRU_CACHE", "false").lower() == "true"
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    lru_size = int(os.getenv("LRU_CACHE_SIZE", "256"))
    ttl = int(os.getenv("CACHE_TTL", "3600"))
    max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))

    return create_cache(
        enable_cache=enable_cache,
        use_lru=use_lru,
        redis_url=redis_url,
        lru_size=lru_size,
        ttl=ttl,
        max_connections=max_connections,
    )


if __name__ == "__main__":
    # Test the caching system
    logging.basicConfig(level=logging.INFO)

    # Test LRU cache
    print("\n=== Testing LRU Cache ===")
    lru_cache = QueryCache(backend=LRUCache(max_size=3))

    # Add some items
    lru_cache.set_search_results("AI trends", 5, [{"result": "AI data"}])
    lru_cache.set_search_results("marketing 2025", 3, [{"result": "Marketing data"}])

    # Retrieve
    result = lru_cache.get_search_results("AI trends", 5)
    print(f"Retrieved: {result}")

    # Stats
    print(f"Cache stats: {json.dumps(lru_cache.get_stats(), indent=2)}")

    # Test Redis cache (if Redis is available)
    try:
        print("\n=== Testing Redis Cache ===")
        redis_cache = QueryCache(backend=RedisCache())
        redis_cache.set_search_results("test query", 5, [{"result": "test data"}])
        result = redis_cache.get_search_results("test query", 5)
        print(f"Retrieved: {result}")
        print(f"Cache stats: {json.dumps(redis_cache.get_stats(), indent=2)}")
        redis_cache.clear_all()
    except Exception as e:
        print(f"Redis test skipped: {e}")
