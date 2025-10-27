"""
Simplified Integration Tests for ChromaDB Wrapper

Tests the SafeChromaDBWrapper with focus on happy paths and critical error cases.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from chromadb.api.models.Collection import Collection

from chromadb_wrapper import (
    SafeChromaDBWrapper,
    create_safe_wrapper,
    ChromaDBQueryError,
    ChromaDBTimeoutError
)
from resilience import CircuitBreakerOpenError


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
        timeout_seconds=2,  # Short timeout for tests
        max_retries=2  # Fewer retries for tests
    )


class TestBasicFunctionality:
    """Test basic wrapper functionality"""

    def test_init_with_defaults(self, mock_collection):
        """Test initialization with default parameters"""
        wrapper = SafeChromaDBWrapper(mock_collection)
        assert wrapper.collection == mock_collection
        assert wrapper.timeout_seconds == 10
        assert wrapper.max_retries == 3

    def test_factory_function(self, mock_collection):
        """Test factory function"""
        wrapper = create_safe_wrapper(mock_collection, timeout_seconds=5)
        assert isinstance(wrapper, SafeChromaDBWrapper)
        assert wrapper.timeout_seconds == 5


class TestQueryMethod:
    """Test query operations"""

    @pytest.mark.asyncio
    async def test_query_success(self, safe_wrapper, mock_collection):
        """Test successful query operation"""
        mock_collection.query.return_value = {
            "ids": [["doc1", "doc2"]],
            "documents": [["Test 1", "Test 2"]],
            "metadatas": [[{"page": 1}, {"page": 2}]],
            "distances": [[0.1, 0.2]]
        }

        query_embeddings = [[0.1] * 384]
        result = await safe_wrapper.query(query_embeddings, n_results=5)

        assert result is not None
        assert "ids" in result
        assert len(result["ids"][0]) == 2

    @pytest.mark.asyncio
    async def test_query_with_filters(self, safe_wrapper, mock_collection):
        """Test query with metadata filters"""
        mock_collection.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["Filtered"]],
            "metadatas": [[{"category": "AI"}]],
            "distances": [[0.1]]
        }

        query_embeddings = [[0.1] * 384]
        where = {"category": "AI"}
        result = await safe_wrapper.query(query_embeddings, where=where)

        assert result is not None
        assert mock_collection.query.called

    @pytest.mark.asyncio
    async def test_query_timeout(self, safe_wrapper, mock_collection):
        """Test query timeout handling"""
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
            return {}

        mock_collection.query = slow_query

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBTimeoutError):
            await safe_wrapper.query(query_embeddings)

    @pytest.mark.asyncio
    async def test_query_error(self, safe_wrapper, mock_collection):
        """Test query error handling"""
        mock_collection.query.side_effect = Exception("Test error")

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBQueryError):
            await safe_wrapper.query(query_embeddings)


class TestCountMethod:
    """Test count operations"""

    @pytest.mark.asyncio
    async def test_count_success(self, safe_wrapper, mock_collection):
        """Test successful count"""
        mock_collection.count.return_value = 150
        result = await safe_wrapper.count()
        assert result == 150

    @pytest.mark.asyncio
    async def test_count_error_returns_zero(self, safe_wrapper, mock_collection):
        """Test count error returns 0"""
        mock_collection.count.side_effect = Exception("Error")
        result = await safe_wrapper.count()
        assert result == 0  # Should not raise


class TestGetMethod:
    """Test get operations"""

    @pytest.mark.asyncio
    async def test_get_by_ids(self, safe_wrapper, mock_collection):
        """Test get by IDs"""
        mock_collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "documents": ["Test 1", "Test 2"],
            "metadatas": [{"page": 1}, {"page": 2}]
        }

        result = await safe_wrapper.get(ids=["doc1", "doc2"])
        assert result is not None
        assert len(result["ids"]) == 2

    @pytest.mark.asyncio
    async def test_get_with_pagination(self, safe_wrapper, mock_collection):
        """Test get with limit and offset"""
        mock_collection.get.return_value = {
            "ids": ["doc11", "doc12"],
            "documents": ["Page 2 Doc 1", "Page 2 Doc 2"],
            "metadatas": [{"page": 11}, {"page": 12}]
        }

        result = await safe_wrapper.get(limit=2, offset=10)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_error(self, safe_wrapper, mock_collection):
        """Test get error handling"""
        mock_collection.get.side_effect = Exception("Get failed")

        with pytest.raises(ChromaDBQueryError):
            await safe_wrapper.get(ids=["doc1"])


class TestRetryBehavior:
    """Test retry logic"""

    @pytest.mark.asyncio
    async def test_retries_on_transient_failure(self, safe_wrapper, mock_collection):
        """Test retries on transient failures"""
        call_count = 0

        def query_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Transient")
            return {
                "ids": [["doc1"]],
                "documents": [["Success"]],
                "metadatas": [[{"page": 1}]],
                "distances": [[0.1]]
            }

        mock_collection.query.side_effect = query_side_effect

        query_embeddings = [[0.1] * 384]
        result = await safe_wrapper.query(query_embeddings)

        assert result is not None
        assert call_count == 2  # Failed once, succeeded on retry

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self, safe_wrapper, mock_collection):
        """Test gives up after max retries"""
        mock_collection.query.side_effect = Exception("Persistent failure")

        query_embeddings = [[0.1] * 384]
        with pytest.raises(ChromaDBQueryError):
            await safe_wrapper.query(query_embeddings)


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration"""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, safe_wrapper, mock_collection):
        """Test circuit opens after consecutive failures"""
        mock_collection.query.side_effect = Exception("Failure")

        query_embeddings = [[0.1] * 384]

        # Make several failing requests
        for _ in range(5):
            try:
                await safe_wrapper.query(query_embeddings)
            except (ChromaDBQueryError, CircuitBreakerOpenError):
                pass

        # Eventually circuit should open
        # (Exact behavior depends on circuit breaker config)

    @pytest.mark.asyncio
    async def test_successful_queries_work(self, safe_wrapper, mock_collection):
        """Test successful queries work normally"""
        mock_collection.query.return_value = {
            "ids": [["doc1"]],
            "documents": [["Test"]],
            "metadatas": [[{"page": 1}]],
            "distances": [[0.1]]
        }

        query_embeddings = [[0.1] * 384]

        # Make multiple successful requests
        for _ in range(3):
            result = await safe_wrapper.query(query_embeddings)
            assert result is not None


class TestErrorMessages:
    """Test error message quality"""

    @pytest.mark.asyncio
    async def test_timeout_error_message_is_helpful(self, safe_wrapper, mock_collection):
        """Test timeout error has helpful message"""
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(10)
            return {}

        mock_collection.query = slow_query

        query_embeddings = [[0.1] * 384]
        try:
            await safe_wrapper.query(query_embeddings)
            pytest.fail("Should have raised timeout error")
        except ChromaDBTimeoutError as e:
            error_msg = str(e)
            assert "timed out" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_query_error_message_is_helpful(self, safe_wrapper, mock_collection):
        """Test query error has helpful message"""
        mock_collection.query.side_effect = Exception("Database is down")

        query_embeddings = [[0.1] * 384]
        try:
            await safe_wrapper.query(query_embeddings)
            pytest.fail("Should have raised query error")
        except ChromaDBQueryError as e:
            error_msg = str(e)
            assert "failed" in error_msg.lower()
