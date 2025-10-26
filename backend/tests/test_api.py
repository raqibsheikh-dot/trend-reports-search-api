"""
API Endpoint Tests

Tests for all FastAPI endpoints including:
- Health checks
- Search endpoints
- Advanced search
- Utility endpoints
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health and status endpoints"""

    def test_root_endpoint(self, test_client):
        """Test root endpoint returns API info"""
        response = test_client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Trend Intelligence API - Creative Strategy Intelligence"
        assert data["version"] == "2.0.0"
        assert "endpoints" in data
        assert "features" in data

    def test_health_endpoint_healthy(
        self,
        test_client,
        override_dependencies
    ):
        """Test health endpoint when system is healthy"""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["version"] == "2.0.0"
        assert "components" in data
        assert "circuit_breakers" in data

    def test_metrics_endpoint(self, test_client):
        """Test Prometheus metrics endpoint"""
        response = test_client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        # Check for some expected metrics
        content = response.text
        assert "http_requests_total" in content or "app_info" in content


class TestSearchEndpoints:
    """Tests for search endpoints"""

    def test_search_without_auth(self, test_client):
        """Test search endpoint requires authentication"""
        response = test_client.post("/search", json={"query": "AI trends", "top_k": 5})
        assert response.status_code == 403

    def test_search_with_invalid_auth(self, test_client):
        """Test search with invalid API key"""
        headers = {"Authorization": "Bearer invalid_key"}
        response = test_client.post(
            "/search",
            json={"query": "AI trends", "top_k": 5},
            headers=headers
        )
        assert response.status_code == 403

    def test_search_success(
        self,
        test_client,
        auth_headers,
        override_dependencies,
        sample_search_request
    ):
        """Test successful search"""
        response = test_client.post(
            "/search",
            json=sample_search_request,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert all("content" in result for result in data)
        assert all("source" in result for result in data)
        assert all("relevance_score" in result for result in data)

    def test_search_empty_query(self, test_client, auth_headers, override_dependencies):
        """Test search with empty query"""
        response = test_client.post(
            "/search",
            json={"query": "", "top_k": 5},
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error

    def test_search_invalid_top_k(self, test_client, auth_headers, override_dependencies):
        """Test search with invalid top_k value"""
        response = test_client.post(
            "/search",
            json={"query": "test", "top_k": 100},  # Max is 20
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error


class TestAdvancedSearchEndpoints:
    """Tests for advanced search endpoints"""

    def test_synthesis_search(
        self,
        test_client,
        auth_headers,
        override_dependencies,
        sample_search_request
    ):
        """Test synthesis search endpoint"""
        response = test_client.post(
            "/search/synthesized",
            json=sample_search_request,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        # Check for synthesis-specific fields
        assert "summary" in data or "meta_analysis" in data

    def test_structured_search(
        self,
        test_client,
        auth_headers,
        override_dependencies,
        sample_search_request
    ):
        """Test structured response endpoint"""
        response = test_client.post(
            "/search/structured",
            json=sample_search_request,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        # Check for structured response fields
        assert "query" in data

    def test_advanced_search_multi_dimensional(
        self,
        test_client,
        auth_headers,
        override_dependencies,
        sample_advanced_search_request
    ):
        """Test multi-dimensional advanced search"""
        response = test_client.post(
            "/search/advanced",
            json=sample_advanced_search_request,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "query" in data
        assert "results" in data

    def test_advanced_search_scenario(
        self,
        test_client,
        auth_headers,
        override_dependencies
    ):
        """Test scenario-based search"""
        request_data = {
            "query": "luxury brands",
            "query_type": "scenario",
            "scenario": "What if luxury brands enter the metaverse?",
            "top_k": 5
        }

        response = test_client.post(
            "/search/advanced",
            json=request_data,
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_advanced_search_trend_stack(
        self,
        test_client,
        auth_headers,
        override_dependencies
    ):
        """Test trend stacking search"""
        request_data = {
            "query": "personalization",
            "query_type": "trend_stack",
            "trends": ["personalization", "social commerce", "AR"],
            "top_k": 5
        }

        response = test_client.post(
            "/search/advanced",
            json=request_data,
            headers=auth_headers
        )
        assert response.status_code == 200


class TestUtilityEndpoints:
    """Tests for utility endpoints"""

    def test_categories_endpoint(self, test_client):
        """Test categories endpoint"""
        response = test_client.get("/categories")
        assert response.status_code == 200

        data = response.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) > 0

    def test_cache_stats_disabled(self, test_client):
        """Test cache stats when cache is disabled"""
        response = test_client.get("/cache/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["enabled"] == False

    def test_cache_stats_enabled(
        self,
        test_client,
        override_dependencies,
        mock_cache
    ):
        """Test cache stats when cache is enabled"""
        # Override cache dependency to return mock
        from main import get_cache
        test_client.app.dependency_overrides[get_cache] = lambda: mock_cache

        response = test_client.get("/cache/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["enabled"] == True
        assert "hits" in data

    def test_cache_clear_requires_auth(self, test_client):
        """Test cache clear requires authentication"""
        response = test_client.post("/cache/clear")
        assert response.status_code == 403

    def test_cache_clear_success(
        self,
        test_client,
        auth_headers,
        override_dependencies
    ):
        """Test successful cache clear"""
        response = test_client.post("/cache/clear", headers=auth_headers)
        # Should work even if cache is disabled
        assert response.status_code in [200, 404]  # 404 if no cache

    def test_llm_stats_disabled(self, test_client):
        """Test LLM stats when LLM is disabled"""
        response = test_client.get("/llm/stats")
        # May be 200 with enabled:false or actually work with mock
        assert response.status_code == 200


@pytest.mark.unit
class TestRequestValidation:
    """Tests for request validation"""

    def test_search_missing_query(self, test_client, auth_headers):
        """Test search with missing query field"""
        response = test_client.post(
            "/search",
            json={"top_k": 5},  # Missing query
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_search_invalid_json(self, test_client, auth_headers):
        """Test search with invalid JSON"""
        response = test_client.post(
            "/search",
            data="not json",
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_advanced_search_invalid_query_type(
        self,
        test_client,
        auth_headers,
        override_dependencies
    ):
        """Test advanced search with invalid query type"""
        response = test_client.post(
            "/search/advanced",
            json={
                "query": "test",
                "query_type": "invalid_type",
                "top_k": 5
            },
            headers=auth_headers
        )
        assert response.status_code == 422
