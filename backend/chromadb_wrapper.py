"""
Safe ChromaDB Wrapper with Error Handling and Circuit Breaker

Provides fault-tolerant ChromaDB operations to prevent cascading failures.
All database operations are wrapped with error handling, retries, and circuit breakers.
"""

import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.api.models.Collection import Collection

from resilience import (
    retry_with_backoff,
    with_timeout,
    get_circuit_breaker,
    CircuitBreakerOpenError,
    TimeoutError as ResilienceTimeoutError
)

logger = logging.getLogger(__name__)


class ChromaDBError(Exception):
    """Base exception for ChromaDB operations"""
    pass


class ChromaDBConnectionError(ChromaDBError):
    """ChromaDB connection failed"""
    pass


class ChromaDBQueryError(ChromaDBError):
    """ChromaDB query failed"""
    pass


class ChromaDBTimeoutError(ChromaDBError):
    """ChromaDB operation timed out"""
    pass


class SafeChromaDBWrapper:
    """
    Thread-safe wrapper for ChromaDB operations with comprehensive error handling.

    Features:
    - Circuit breaker pattern
    - Automatic retries with exponential backoff
    - Timeout protection
    - Detailed error logging
    - Graceful degradation
    """

    def __init__(
        self,
        collection: Collection,
        circuit_breaker_name: str = "chromadb",
        timeout_seconds: int = 10,
        max_retries: int = 3
    ):
        """
        Initialize safe ChromaDB wrapper

        Args:
            collection: ChromaDB collection instance
            circuit_breaker_name: Name for circuit breaker tracking
            timeout_seconds: Max seconds for each operation
            max_retries: Number of retry attempts
        """
        self.collection = collection
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Get or create circuit breaker for ChromaDB operations
        self.circuit_breaker = get_circuit_breaker(circuit_breaker_name)

        logger.info(
            f"Initialized SafeChromaDBWrapper for collection '{collection.name}' "
            f"(timeout={timeout_seconds}s, retries={max_retries})"
        )

    async def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: List[str] = None
    ) -> Dict[str, Any]:
        """
        Safe query operation with error handling

        Args:
            query_embeddings: Query embedding vectors
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document filter
            include: Fields to include in results

        Returns:
            Query results dictionary

        Raises:
            ChromaDBConnectionError: If connection fails
            ChromaDBQueryError: If query fails
            ChromaDBTimeoutError: If operation times out
            CircuitBreakerOpenError: If circuit breaker is open
        """
        if include is None:
            include = ["documents", "metadatas", "distances"]

        operation_name = f"chromadb_query_{self.collection.name}"

        try:
            # Check circuit breaker
            if not self.circuit_breaker._should_attempt_call():
                logger.warning(
                    f"Circuit breaker '{self.circuit_breaker.name}' is OPEN - "
                    "rejecting ChromaDB query"
                )
                raise CircuitBreakerOpenError(
                    f"ChromaDB circuit breaker is open. "
                    f"Service degraded. Try again later."
                )

            # Execute query with retry and timeout
            @retry_with_backoff(
                max_retries=self.max_retries,
                initial_delay=0.5,
                exponential_base=2.0,
                max_delay=10.0
            )
            async def _execute_query():
                # Wrap in timeout
                async def _query():
                    return self.collection.query(
                        query_embeddings=query_embeddings,
                        n_results=n_results,
                        where=where,
                        where_document=where_document,
                        include=include
                    )

                return await with_timeout(
                    _query(),
                    timeout_seconds=self.timeout_seconds,
                    operation_name=operation_name
                )

            # Execute
            results = await _execute_query()

            # Record success
            self.circuit_breaker.record_success()

            logger.debug(
                f"ChromaDB query successful: {len(results.get('ids', [[]])[0])} results"
            )

            return results

        except ResilienceTimeoutError as e:
            self.circuit_breaker.record_failure()
            logger.error(
                f"ChromaDB query timeout after {self.timeout_seconds}s: {e}",
                exc_info=True
            )
            raise ChromaDBTimeoutError(
                f"Database query timed out after {self.timeout_seconds} seconds. "
                "Please try again or reduce the search scope."
            ) from e

        except CircuitBreakerOpenError:
            # Already logged above, just re-raise
            raise

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(
                f"Unexpected error during ChromaDB query: {type(e).__name__}: {e}",
                exc_info=True
            )
            raise ChromaDBQueryError(
                f"Database query failed: {str(e)}"
            ) from e

    async def count(self) -> int:
        """
        Safe count operation

        Returns:
            Number of documents in collection

        Raises:
            ChromaDBError: If operation fails
        """
        try:
            @retry_with_backoff(max_retries=2)
            async def _execute_count():
                async def _count():
                    return self.collection.count()

                return await with_timeout(
                    _count(),
                    timeout_seconds=5,
                    operation_name="chromadb_count"
                )

            count = await _execute_count()
            self.circuit_breaker.record_success()
            return count

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"ChromaDB count failed: {e}", exc_info=True)
            # Don't raise for count - just return 0
            return 0

    async def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include: List[str] = None
    ) -> Dict[str, Any]:
        """
        Safe get operation

        Args:
            ids: Document IDs to retrieve
            where: Metadata filter
            limit: Max results
            offset: Offset for pagination
            include: Fields to include

        Returns:
            Get results dictionary

        Raises:
            ChromaDBError: If operation fails
        """
        if include is None:
            include = ["documents", "metadatas"]

        try:
            @retry_with_backoff(max_retries=self.max_retries)
            async def _execute_get():
                async def _get():
                    return self.collection.get(
                        ids=ids,
                        where=where,
                        limit=limit,
                        offset=offset,
                        include=include
                    )

                return await with_timeout(
                    _get(),
                    timeout_seconds=self.timeout_seconds,
                    operation_name="chromadb_get"
                )

            results = await _execute_get()
            self.circuit_breaker.record_success()
            return results

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"ChromaDB get failed: {e}", exc_info=True)
            raise ChromaDBQueryError(f"Failed to retrieve documents: {str(e)}") from e


def create_safe_wrapper(
    collection: Collection,
    timeout_seconds: int = 10,
    max_retries: int = 3
) -> SafeChromaDBWrapper:
    """
    Factory function to create a safe ChromaDB wrapper

    Args:
        collection: ChromaDB collection
        timeout_seconds: Operation timeout
        max_retries: Number of retries

    Returns:
        SafeChromaDBWrapper instance
    """
    return SafeChromaDBWrapper(
        collection=collection,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries
    )
