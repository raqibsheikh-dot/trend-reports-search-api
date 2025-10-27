"""
Search Service - Core business logic for trend report searches

Extracts search logic from main.py to improve maintainability and testability.
"""

import logging
from typing import List, Optional, Dict, Any
from contextvars import ContextVar

from pydantic import BaseModel
from chromadb_wrapper import SafeChromaDBWrapper, ChromaDBError, ChromaDBConnectionError, ChromaDBQueryError, ChromaDBTimeoutError
from resilience import CircuitBreakerOpenError
from input_validation import validate_search_request, SuspiciousInputError, ValidationError as InputValidationError
from cache import QueryCache
from synthesis import TrendSynthesizer
from advanced_search import AdvancedSearchEngine
from response_formatter import ResponseFormatter

logger = logging.getLogger(__name__)

# Context variable for request ID tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="unknown")


class SearchRequest(BaseModel):
    """Search request model"""
    query: str
    top_k: int = 5


class SearchResult(BaseModel):
    """Individual search result"""
    content: str
    source: str
    page: int
    relevance_score: float


class SearchService:
    """
    Service for handling all search operations

    Centralizes search logic including:
    - Input validation
    - Caching
    - Vector search
    - Result formatting
    - Error handling
    """

    def __init__(
        self,
        collection: SafeChromaDBWrapper,
        embedder: Any,  # TextEmbedding type
        cache: Optional[QueryCache] = None,
        synthesizer: Optional[TrendSynthesizer] = None,
        formatter: Optional[ResponseFormatter] = None,
        advanced_engine: Optional[AdvancedSearchEngine] = None
    ):
        """
        Initialize search service

        Args:
            collection: Safe ChromaDB wrapper
            embedder: Text embedding model
            cache: Optional query cache
            synthesizer: Optional LLM synthesizer
            formatter: Optional response formatter
            advanced_engine: Optional advanced search engine
        """
        self.collection = collection
        self.embedder = embedder
        self.cache = cache
        self.synthesizer = synthesizer
        self.formatter = formatter
        self.advanced_engine = advanced_engine

    def _get_request_id(self) -> str:
        """Get current request ID from context"""
        return request_id_var.get()

    def _validate_and_sanitize(self, query: str, top_k: int) -> tuple[str, int]:
        """
        Validate and sanitize search inputs

        Args:
            query: User query string
            top_k: Number of results requested

        Returns:
            Tuple of (sanitized_query, validated_top_k)

        Raises:
            SuspiciousInputError: If malicious input detected
            InputValidationError: If input is invalid
        """
        request_id = self._get_request_id()

        try:
            clean_query, validated_top_k = validate_search_request(query, top_k)
            logger.debug(
                f"[{request_id}] Input validated: query_len={len(clean_query)}, top_k={validated_top_k}"
            )
            return clean_query, validated_top_k
        except (SuspiciousInputError, InputValidationError) as e:
            logger.warning(f"[{request_id}] Input validation failed: {e}")
            raise

    def _check_cache(self, query: str, top_k: int) -> Optional[List[Dict[str, Any]]]:
        """
        Check cache for existing results

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Cached results as dicts, or None if not found
        """
        if not self.cache:
            return None

        request_id = self._get_request_id()
        cached_results = self.cache.get_search_results(query=query, top_k=top_k)

        if cached_results:
            logger.info(
                f"[{request_id}] Cache HIT: query='{query[:50]}...', results={len(cached_results)}"
            )
            return cached_results

        logger.debug(f"[{request_id}] Cache MISS: query='{query[:50]}...'")
        return None

    def _save_to_cache(self, query: str, top_k: int, results: List[SearchResult]) -> None:
        """
        Save results to cache

        Args:
            query: Search query
            top_k: Number of results
            results: Search results to cache
        """
        if not self.cache or not results:
            return

        request_id = self._get_request_id()
        cache_data = [r.model_dump() for r in results]
        self.cache.set_search_results(query=query, top_k=top_k, results=cache_data)
        logger.debug(f"[{request_id}] Cached {len(results)} results for query '{query[:50]}...'")

    async def _embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for query

        Args:
            query: Query text

        Returns:
            Embedding vector as list of floats
        """
        request_id = self._get_request_id()
        logger.debug(f"[{request_id}] Generating embedding for query: '{query[:50]}...'")

        # FastEmbed returns generator, get first embedding
        embedding = list(self.embedder.embed([query]))[0].tolist()
        return embedding

    async def _perform_vector_search(
        self,
        query_embedding: List[float],
        top_k: int
    ) -> Dict[str, Any]:
        """
        Perform vector search in ChromaDB

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results

        Returns:
            Raw ChromaDB results

        Raises:
            ChromaDB errors (handled by wrapper)
        """
        request_id = self._get_request_id()
        logger.debug(f"[{request_id}] Performing vector search with top_k={top_k}")

        results = await self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        return results

    def _format_search_results(self, raw_results: Dict[str, Any]) -> List[SearchResult]:
        """
        Format raw ChromaDB results into SearchResult objects

        Args:
            raw_results: Raw results from ChromaDB

        Returns:
            List of formatted SearchResult objects
        """
        formatted_results = []

        if raw_results["documents"] and raw_results["documents"][0]:
            for i, doc in enumerate(raw_results["documents"][0]):
                formatted_results.append(SearchResult(
                    content=doc,
                    source=raw_results["metadatas"][0][i].get("filename", "Unknown"),
                    page=raw_results["metadatas"][0][i].get("page", 0),
                    relevance_score=round(1 - raw_results["distances"][0][i], 3)
                ))

        return formatted_results

    async def basic_search(self, query: str, top_k: int) -> List[SearchResult]:
        """
        Perform basic vector search

        Args:
            query: User search query
            top_k: Number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            SuspiciousInputError: If malicious input detected
            InputValidationError: If input is invalid
            CircuitBreakerOpenError: If circuit breaker is open
            ChromaDBTimeoutError: If search times out
            ChromaDBConnectionError: If database unavailable
            ChromaDBQueryError: If query fails
        """
        request_id = self._get_request_id()

        # 1. Validate and sanitize input
        clean_query, validated_top_k = self._validate_and_sanitize(query, top_k)

        # 2. Check cache
        cached = self._check_cache(clean_query, validated_top_k)
        if cached:
            return [SearchResult(**r) for r in cached]

        # 3. Perform search
        query_embedding = await self._embed_query(clean_query)
        raw_results = await self._perform_vector_search(query_embedding, validated_top_k)

        # 4. Format results
        formatted_results = self._format_search_results(raw_results)

        # 5. Cache results
        self._save_to_cache(clean_query, validated_top_k, formatted_results)

        logger.info(
            f"[{request_id}] Search completed: query='{clean_query[:50]}...', "
            f"results={len(formatted_results)}"
        )

        return formatted_results

    async def search_with_synthesis(
        self,
        query: str,
        top_k: int,
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search with LLM synthesis

        Args:
            query: User search query
            top_k: Number of results
            style: Optional response style

        Returns:
            Synthesized response dictionary

        Raises:
            ValueError: If synthesizer not available
            Same exceptions as basic_search
        """
        if not self.synthesizer:
            raise ValueError("Synthesizer not configured")

        request_id = self._get_request_id()
        logger.info(f"[{request_id}] Starting synthesis search")

        # Get basic search results
        search_results = await self.basic_search(query, top_k)

        # Synthesize with LLM
        synthesis_result = await self.synthesizer.synthesize(
            query=query,
            results=[r.model_dump() for r in search_results],
            min_sources_for_meta=2
        )

        logger.info(f"[{request_id}] Synthesis completed")
        return synthesis_result

    async def search_with_structure(
        self,
        query: str,
        top_k: int
    ) -> Dict[str, Any]:
        """
        Search with structured response formatting

        Args:
            query: User search query
            top_k: Number of results

        Returns:
            Structured response dictionary

        Raises:
            ValueError: If formatter not available
            Same exceptions as basic_search
        """
        if not self.formatter:
            raise ValueError("Formatter not configured")

        request_id = self._get_request_id()
        logger.info(f"[{request_id}] Starting structured search")

        # Get basic search results
        search_results = await self.basic_search(query, top_k)

        # Format with structure
        structured_result = await self.formatter.format_response(
            query=query,
            results=[r.model_dump() for r in search_results]
        )

        logger.info(f"[{request_id}] Structured formatting completed")
        return structured_result

    async def advanced_search(
        self,
        query: str,
        query_type: str = "simple",
        top_k: int = 5,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Advanced multi-dimensional search

        Args:
            query: User search query
            query_type: Type of query (simple, multi_dimensional, temporal, etc.)
            top_k: Number of results
            **kwargs: Additional search parameters

        Returns:
            Advanced search results dictionary

        Raises:
            ValueError: If advanced_engine not available
            Same exceptions as basic_search
        """
        if not self.advanced_engine:
            raise ValueError("Advanced search engine not configured")

        request_id = self._get_request_id()
        logger.info(f"[{request_id}] Starting advanced search: type={query_type}")

        # Validate input
        clean_query, validated_top_k = self._validate_and_sanitize(query, top_k)

        # Perform advanced search
        advanced_result = await self.advanced_engine.search(
            query=clean_query,
            query_type=query_type,
            top_k=validated_top_k,
            **kwargs
        )

        logger.info(f"[{request_id}] Advanced search completed")
        return advanced_result


def create_search_service(
    collection: SafeChromaDBWrapper,
    embedder: Any,
    cache: Optional[QueryCache] = None,
    synthesizer: Optional[TrendSynthesizer] = None,
    formatter: Optional[ResponseFormatter] = None,
    advanced_engine: Optional[AdvancedSearchEngine] = None
) -> SearchService:
    """
    Factory function to create SearchService

    Args:
        collection: Safe ChromaDB wrapper
        embedder: Text embedding model
        cache: Optional query cache
        synthesizer: Optional LLM synthesizer
        formatter: Optional response formatter
        advanced_engine: Optional advanced search engine

    Returns:
        Configured SearchService instance
    """
    return SearchService(
        collection=collection,
        embedder=embedder,
        cache=cache,
        synthesizer=synthesizer,
        formatter=formatter,
        advanced_engine=advanced_engine
    )
