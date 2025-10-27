"""
Integration Tests for ChromaDB Wrapper

Tests the SafeChromaDBWrapper with circuit breaker, retries, and timeouts.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from chromadb.api.models.Collection import Collection

from chromadb_wrapper import (
    SafeChromaDBWrapper,
    create_safe_wrapper,
    ChromaDBError,
    ChromaDBConnectionError,
    ChromaDBQueryError,
    ChromaDBTimeoutError
)
from resilience import CircuitBreakerOpenError, TimeoutError as ResilienceTimeoutError


@pytest.fixture
def mock_collection():
    """Create a mock ChromaDB collection"""
    collection = MagicMock(spec=Collection)
    collection.name = "test_collection"
    collection.count.return_value = 100
    return collection


@pytest.fixture
def safe_wrapper(mock_collection):
    """Create SafeChromaDBWrapper with mock collection"""
    return SafeChromaDBWrapper(
        collection=mock_collection,
        circuit_breaker_name="test_chromadb",
        timeout_seconds=5,
        max_retries=3
    )


class TestSafeChromaDBWrapperInit:
    """Test wrapper initialization"""

    def test_init_with_defaults(self, mock_collection):
        """Test initialization with default parameters"""
        wrapper = SafeChromaDBWrapper(mock_collection)
        assert wrapper.collection == mock_collection
        assert wrapper.timeout_seconds == 10
        assert wrapper.max_retries == 3

    def test_init_with_custom_params(self, mock_collection):
        """Test initialization with custom parameters"""
        wrapper = SafeChromaDBWrapper(
            mock_collection,
            circuit_breaker_name="custom_cb",
            timeout_seconds=15,
            max_retries=5
        )
        assert wrapper.timeout_seconds == 15
        assert wrapper.max_retries == 5

    def test_circuit_breaker_created(self, mock_collection):
        """Test that circuit breaker is properly initialized"""
        wrapper = SafeChromaDBWrapper(mock_collection)
        assert wrapper.circuit_breaker is not None
        assert wrapper.circuit_breaker.name == "chromadb"


class TestQueryMethod:
    """Test safe query operations"""

    @pytest.mark.asyncio
    async def test_query_success(self, safe_wrapper, mock_collection):
        """Test successful query operation"""
        # Mock successful query response
        mock_collection.query.return_value = {
            "ids": [["doc1", "doc2"]],
            "documents": [["Test doc 1", "Test doc 2"]],
            "metadatas": [[{"page": 1}, {"page": 2}]],
            "distances": [[0.1, 0.2]]
        }

        query_embeddings = [[0.1] * 384]
        result = await safe_wrapper.query(query_embeddings, n_results=5)

        assert result is not None
        assert "ids" in result
        assert len(result["ids"][0]) == 2
        mock_collection.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_filters(self, safe_wrapper, mock_collection):
        """Test query with where filters"""
        mock_collection.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["Filtered doc"]],
            "metadatas": [[{"category": "AI"}]],
            "distances": [[0.1]]
        }

        query_embeddings = [[0.1] * 384]
        where_filter = {"category": "AI"}
        result = await safe_wrapper.query(
            query_embeddings,
            n_results=5,
            where=where_filter
        )

        assert result is not None
        mock_collection.query.assert_called_once()
        call_args = mock_collection.query.call_args
        assert call_args.kwargs["where"] == where_filter

    @pytest.mark.asyncio
    async def test_query_with_custom_include(self, safe_wrapper, mock_collection):
        """Test query with custom include fields"""
        mock_collection.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["Test"]],
        }

        query_embeddings = [[0.1] * 384]
        include = ["documents", "ids"]
        result = await safe_wrapper.query(
            query_embeddings,
            include=include
        )

        assert result is not None
        call_args = mock_collection.query.call_args
        assert call_args.kwargs["include"] == include

    @pytest.mark.asyncio
    async def test_query_circuit_breaker_open(self, safe_wrapper):
        """Test query fails when circuit breaker is open"""
        # Manually open the circuit breaker
        safe_wrapper.circuit_breaker.failure_count = 10
        safe_wrapper.circuit_breaker.last_failure_time = asyncio.get_event_loop().time()

        query_embeddings = [[0.1] * 384]
        with pytest.raises(CircuitBreakerOpenError, match="circuit breaker is open"):
            await safe_wrapper.query(query_embeddings)

    @pytest.mark.asyncio
    async def test_query_timeout_error(self, safe_wrapper, mock_collection):
        """Test query timeout handling"""
        # Make query hang to trigger timeout
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
            return {"ids": [[]], "documents": [[]]}

        mock_collection.query = slow_query

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBTimeoutError, match="timed out"):
            await safe_wrapper.query(query_embeddings)

    @pytest.mark.asyncio
    async def test_query_connection_error(self, safe_wrapper, mock_collection):
        """Test query connection error handling"""
        import chromadb.errors

        mock_collection.query.side_effect = chromadb.errors.ConnectionError("Connection failed")

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBConnectionError, match="Unable to connect"):
            await safe_wrapper.query(query_embeddings)

    @pytest.mark.asyncio
    async def test_query_generic_error(self, safe_wrapper, mock_collection):
        """Test query generic error handling"""
        mock_collection.query.side_effect = Exception("Unknown error")

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBQueryError, match="Database query failed"):
            await safe_wrapper.query(query_embeddings)

    @pytest.mark.asyncio
    async def test_query_records_success(self, safe_wrapper, mock_collection):
        """Test that successful query records success in circuit breaker"""
        mock_collection.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["Test"]],
            "metadatas": [[{"page": 1}]],
            "distances": [[0.1]]
        }

        initial_success_count = safe_wrapper.circuit_breaker.success_count
        query_embeddings = [[0.1] * 384]
        await safe_wrapper.query(query_embeddings)

        # Success should be recorded
        assert safe_wrapper.circuit_breaker.success_count > initial_success_count

    @pytest.mark.asyncio
    async def test_query_records_failure(self, safe_wrapper, mock_collection):
        """Test that failed query records failure in circuit breaker"""
        mock_collection.query.side_effect = Exception("Test failure")

        initial_failure_count = safe_wrapper.circuit_breaker.failure_count
        query_embeddings = [[0.1] * 384]

        with pytest.raises(ChromaDBQueryError):
            await safe_wrapper.query(query_embeddings)

        # Failure should be recorded
        assert safe_wrapper.circuit_breaker.failure_count > initial_failure_count


class TestCountMethod:
    """Test safe count operations"""

    @pytest.mark.asyncio
    async def test_count_success(self, safe_wrapper, mock_collection):
        """Test successful count operation"""
        mock_collection.count.return_value = 150

        result = await safe_wrapper.count()

        assert result == 150
        mock_collection.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_failure_returns_zero(self, safe_wrapper, mock_collection):
        """Test that count failure returns 0 instead of raising"""
        mock_collection.count.side_effect = Exception("Count failed")

        result = await safe_wrapper.count()

        assert result == 0  # Should not raise, just return 0

    @pytest.mark.asyncio
    async def test_count_timeout(self, safe_wrapper, mock_collection):
        """Test count with timeout"""
        async def slow_count(*args, **kwargs):
            await asyncio.sleep(10)
            return 100

        mock_collection.count = slow_count

        # Count has 5 second timeout, should return 0 on timeout
        result = await safe_wrapper.count()
        assert result == 0


class TestGetMethod:
    """Test safe get operations"""

    @pytest.mark.asyncio
    async def test_get_by_ids(self, safe_wrapper, mock_collection):
        """Test get operation with IDs"""
        mock_collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "documents": ["Test 1", "Test 2"],
            "metadatas": [{"page": 1}, {"page": 2}]
        }

        result = await safe_wrapper.get(ids=["doc1", "doc2"])

        assert result is not None
        assert len(result["ids"]) == 2
        mock_collection.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_with_where(self, safe_wrapper, mock_collection):
        """Test get with where filter"""
        mock_collection.get.return_value = {
            "ids": ["doc1"],
            "documents": ["Filtered doc"],
            "metadatas": [{"category": "AI"}]
        }

        where_filter = {"category": "AI"}
        result = await safe_wrapper.get(where=where_filter, limit=10)

        assert result is not None
        call_args = mock_collection.get.call_args
        assert call_args.kwargs["where"] == where_filter
        assert call_args.kwargs["limit"] == 10

    @pytest.mark.asyncio
    async def test_get_with_pagination(self, safe_wrapper, mock_collection):
        """Test get with limit and offset"""
        mock_collection.get.return_value = {
            "ids": ["doc11", "doc12"],
            "documents": ["Doc 11", "Doc 12"],
            "metadatas": [{"page": 11}, {"page": 12}]
        }

        result = await safe_wrapper.get(limit=2, offset=10)

        assert result is not None
        call_args = mock_collection.get.call_args
        assert call_args.kwargs["limit"] == 2
        assert call_args.kwargs["offset"] == 10

    @pytest.mark.asyncio
    async def test_get_error_handling(self, safe_wrapper, mock_collection):
        """Test get error handling"""
        mock_collection.get.side_effect = Exception("Get failed")

        with pytest.raises(ChromaDBQueryError, match="Failed to retrieve"):
            await safe_wrapper.get(ids=["doc1"])


class TestRetryLogic:
    """Test retry behavior"""

    @pytest.mark.asyncio
    async def test_query_retries_on_failure(self, safe_wrapper, mock_collection):
        """Test that query retries on transient failures"""
        # Fail twice, then succeed
        call_count = 0

        def query_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient failure")
            return {
                "ids": [["doc1"]],
                "documents": [["Success"]],
                "metadatas": [[{"page": 1}]],
                "distances": [[0.1]]
            }

        mock_collection.query.side_effect = query_side_effect

        query_embeddings = [[0.1] * 384]
        result = await safe_wrapper.query(query_embeddings)

        # Should succeed after retries
        assert result is not None
        assert call_count == 3  # Failed twice, succeeded on third try

    @pytest.mark.asyncio
    async def test_query_gives_up_after_max_retries(self, safe_wrapper, mock_collection):
        """Test that query gives up after max retries"""
        mock_collection.query.side_effect = Exception("Persistent failure")

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBQueryError):
            await safe_wrapper.query(query_embeddings)

        # Should have tried max_retries times
        assert mock_collection.query.call_count >= 3


class TestFactoryFunction:
    """Test create_safe_wrapper factory function"""

    def test_create_safe_wrapper_defaults(self, mock_collection):
        """Test factory function with defaults"""
        wrapper = create_safe_wrapper(mock_collection)

        assert isinstance(wrapper, SafeChromaDBWrapper)
        assert wrapper.collection == mock_collection
        assert wrapper.timeout_seconds == 10
        assert wrapper.max_retries == 3

    def test_create_safe_wrapper_custom_params(self, mock_collection):
        """Test factory function with custom parameters"""
        wrapper = create_safe_wrapper(
            mock_collection,
            timeout_seconds=20,
            max_retries=5
        )

        assert wrapper.timeout_seconds == 20
        assert wrapper.max_retries == 5


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration"""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, safe_wrapper, mock_collection):
        """Test that circuit opens after consecutive failures"""
        mock_collection.query.side_effect = Exception("Failure")

        query_embeddings = [[0.1] * 384]

        # Make several failing requests
        for _ in range(5):
            try:
                await safe_wrapper.query(query_embeddings)
            except (ChromaDBQueryError, CircuitBreakerOpenError):
                pass

        # Circuit should be open now
        # Next request should fail immediately with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await safe_wrapper.query(query_embeddings)

    @pytest.mark.asyncio
    async def test_circuit_closes_after_success(self, safe_wrapper, mock_collection):
        """Test that circuit closes after successful request"""
        # Start with successful response
        mock_collection.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["Test"]],
            "metadatas": [[{"page": 1}]],
            "distances": [[0.1]]
        }

        query_embeddings = [[0.1] * 384]

        # Make successful request
        result = await safe_wrapper.query(query_embeddings)
        assert result is not None

        # Circuit should remain closed
        result = await safe_wrapper.query(query_embeddings)
        assert result is not None


class TestErrorMessages:
    """Test error message quality"""

    @pytest.mark.asyncio
    async def test_timeout_error_message(self, safe_wrapper, mock_collection):
        """Test timeout error has helpful message"""
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(10)
            return {}

        mock_collection.query = slow_query

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBTimeoutError) as exc_info:
            await safe_wrapper.query(query_embeddings)

        error_message = str(exc_info.value)
        assert "timed out" in error_message.lower()
        assert "5 seconds" in error_message.lower() or "timeout" in error_message.lower()

    @pytest.mark.asyncio
    async def test_connection_error_message(self, safe_wrapper, mock_collection):
        """Test connection error has helpful message"""
        import chromadb.errors
        mock_collection.query.side_effect = chromadb.errors.ConnectionError("Failed")

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBConnectionError) as exc_info:
            await safe_wrapper.query(query_embeddings)

        error_message = str(exc_info.value)
        assert "connect" in error_message.lower()
        assert "unavailable" in error_message.lower()

    @pytest.mark.asyncio
    async def test_circuit_breaker_error_message(self, safe_wrapper):
        """Test circuit breaker error has helpful message"""
        # Manually open circuit
        safe_wrapper.circuit_breaker.failure_count = 10
        safe_wrapper.circuit_breaker.last_failure_time = asyncio.get_event_loop().time()

        query_embeddings = [[0.1] * 384]
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await safe_wrapper.query(query_embeddings)

        error_message = str(exc_info.value)
        assert "circuit breaker" in error_message.lower()
        assert "open" in error_message.lower()
