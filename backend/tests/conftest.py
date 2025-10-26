"""
Pytest Configuration and Fixtures

Provides shared fixtures for all tests including:
- Test client
- Mock database
- Mock cache
- Mock LLM
- Sample data
"""

import pytest
import os
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import chromadb
from chromadb.config import Settings as ChromaSettings


# Set test environment variables before importing app
os.environ["API_KEY"] = "test_api_key_that_is_at_least_32_characters_long"
os.environ["ENVIRONMENT"] = "test"
os.environ["CHROMA_DB_PATH"] = "./test_chroma_data"
os.environ["ENABLE_CACHE"] = "false"  # Disable cache for tests by default
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Import app after setting environment variables
from main import app, get_collection, get_embedder, get_cache, get_llm


@pytest.fixture(scope="session")
def test_client() -> Generator[TestClient, None, None]:
    """Create test client for the entire test session"""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth_headers() -> dict:
    """Authentication headers for API requests"""
    return {"Authorization": "Bearer test_api_key_that_is_at_least_32_characters_long"}


@pytest.fixture
def mock_collection():
    """Mock ChromaDB collection"""
    collection = MagicMock()
    collection.count.return_value = 100
    collection.peek.return_value = {"ids": ["test_id"], "documents": ["test doc"]}
    collection.query.return_value = {
        "ids": [["doc1", "doc2"]],
        "documents": [["Test document 1", "Test document 2"]],
        "metadatas": [[
            {"filename": "test1.pdf", "page": 1},
            {"filename": "test2.pdf", "page": 2}
        ]],
        "distances": [[0.1, 0.2]]
    }
    return collection


@pytest.fixture
def mock_embedder():
    """Mock embedder"""
    embedder = MagicMock()
    embedder.embed.return_value = [[0.1] * 384]  # Mock embedding vector
    return embedder


@pytest.fixture
def mock_llm_service():
    """Mock LLM service"""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value=MagicMock(
        content='{"trends": ["Trend 1", "Trend 2"]}',
        usage=MagicMock(
            input_tokens=100,
            output_tokens=200
        )
    ))
    llm.get_cost_stats.return_value = {
        "total_requests": 10,
        "total_cost": 0.50,
        "budget_remaining": 49.50
    }
    llm.cost_tracker = MagicMock()
    llm.cost_tracker.check_budget.return_value = True
    return llm


@pytest.fixture
def mock_cache():
    """Mock cache"""
    cache = MagicMock()
    cache.get.return_value = None
    cache.set.return_value = True
    cache.get_stats.return_value = {
        "hits": 10,
        "misses": 5,
        "hit_rate": 0.67
    }
    return cache


@pytest.fixture
def sample_search_request():
    """Sample search request data"""
    return {
        "query": "AI trends in marketing",
        "top_k": 5
    }


@pytest.fixture
def sample_advanced_search_request():
    """Sample advanced search request"""
    return {
        "query": "AI trends",
        "query_type": "multi_dimensional",
        "dimensions": ["sustainability", "Gen Z"],
        "top_k": 5
    }


@pytest.fixture
def sample_search_results():
    """Sample search results"""
    return [
        {
            "content": "AI is transforming marketing with personalization",
            "source": "McKinsey_Marketing_2025.pdf",
            "page": 15,
            "relevance_score": 0.95
        },
        {
            "content": "Generative AI enables creative content at scale",
            "source": "Forrester_AI_Trends.pdf",
            "page": 23,
            "relevance_score": 0.88
        }
    ]


@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    """Reset FastAPI dependency overrides after each test"""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_dependencies(
    mock_collection,
    mock_embedder,
    mock_llm_service,
    mock_cache
):
    """Override all dependencies with mocks"""
    app.dependency_overrides[get_collection] = lambda: mock_collection
    app.dependency_overrides[get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_llm] = lambda: mock_llm_service
    app.dependency_overrides[get_cache] = lambda: mock_cache
    yield
    app.dependency_overrides.clear()


# Pytest async support
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Skip markers
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "llm: tests that require actual LLM API calls (expensive)"
    )
    config.addinivalue_line(
        "markers", "redis: tests that require Redis"
    )
    config.addinivalue_line(
        "markers", "s3: tests that require S3/boto3"
    )
    config.addinivalue_line(
        "markers", "slow: tests that take more than 1 second"
    )
