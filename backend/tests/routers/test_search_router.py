"""
Tests for Search Router

Tests all search endpoints in isolation with mocked dependencies.
Ensures router layer correctly handles HTTP requests and delegates to SearchService.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

# Import app and dependencies
from main import app
from services.search_service import SearchResult


class TestBasicSearchEndpoint:
    """Tests for POST /v1/search endpoint"""

    def setup_method(self):
        """Setup test client and mocks"""
        self.client = TestClient(app)
        self.api_key = "test-api-key"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_basic_search_success(self, mock_service_dep, mock_auth):
        """Test successful basic search"""
        # Mock authentication
        mock_auth.return_value = self.api_key

        # Mock SearchService
        mock_service = Mock()
        mock_service.basic_search = AsyncMock(return_value=[
            SearchResult(
                content="AI trends are accelerating",
                source="Gartner 2025",
                page=10,
                score=0.95,
                category="Technology"
            ),
            SearchResult(
                content="Machine learning adoption growing",
                source="McKinsey Report",
                page=5,
                score=0.89,
                category="Technology"
            )
        ])
        mock_service_dep.return_value = mock_service

        # Make request
        response = self.client.post(
            "/v1/search",
            json={"query": "AI trends", "top_k": 5},
            headers=self.headers
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["content"] == "AI trends are accelerating"
        assert data[0]["score"] == 0.95
        assert data[1]["source"] == "McKinsey Report"

        # Verify service was called correctly
        mock_service.basic_search.assert_called_once_with(
            query="AI trends",
            top_k=5
        )

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_basic_search_default_top_k(self, mock_service_dep, mock_auth):
        """Test basic search with default top_k"""
        mock_auth.return_value = self.api_key
        mock_service = Mock()
        mock_service.basic_search = AsyncMock(return_value=[])
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search",
            json={"query": "sustainability trends"},
            headers=self.headers
        )

        assert response.status_code == 200
        mock_service.basic_search.assert_called_once_with(
            query="sustainability trends",
            top_k=10  # Default value
        )

    def test_basic_search_missing_auth(self):
        """Test basic search without authentication"""
        response = self.client.post(
            "/v1/search",
            json={"query": "test", "top_k": 5}
        )

        assert response.status_code in [401, 403]  # Unauthorized or Forbidden

    @patch('main.verify_api_key')
    def test_basic_search_invalid_query(self, mock_auth):
        """Test basic search with invalid query"""
        mock_auth.return_value = self.api_key

        response = self.client.post(
            "/v1/search",
            json={"query": "", "top_k": 5},
            headers=self.headers
        )

        assert response.status_code == 422  # Validation error

    @patch('main.verify_api_key')
    def test_basic_search_invalid_top_k(self, mock_auth):
        """Test basic search with invalid top_k"""
        mock_auth.return_value = self.api_key

        response = self.client.post(
            "/v1/search",
            json={"query": "test", "top_k": -1},
            headers=self.headers
        )

        assert response.status_code == 422  # Validation error

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_basic_search_service_error(self, mock_service_dep, mock_auth):
        """Test basic search when service raises exception"""
        mock_auth.return_value = self.api_key
        mock_service = Mock()
        mock_service.basic_search = AsyncMock(side_effect=Exception("Service error"))
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search",
            json={"query": "test", "top_k": 5},
            headers=self.headers
        )

        assert response.status_code == 500
        assert "Service error" in response.json()["detail"] or "Internal" in response.json()["detail"]


class TestSynthesizedSearchEndpoint:
    """Tests for POST /v1/search/synthesized endpoint"""

    def setup_method(self):
        """Setup test client and mocks"""
        self.client = TestClient(app)
        self.api_key = "test-api-key"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_synthesized_search_success(self, mock_service_dep, mock_auth):
        """Test successful synthesized search"""
        mock_auth.return_value = self.api_key

        mock_service = Mock()
        mock_service.search_with_synthesis = AsyncMock(return_value={
            "synthesis": "AI and sustainability are converging...",
            "key_insights": [
                "70% of companies investing in AI",
                "Sustainability becoming core strategy"
            ],
            "sources": ["Gartner 2025", "McKinsey"],
            "confidence": 0.92
        })
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search/synthesized",
            json={"query": "AI sustainability", "top_k": 10},
            headers=self.headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "synthesis" in data
        assert "key_insights" in data
        assert len(data["sources"]) == 2
        assert data["confidence"] == 0.92

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_synthesized_search_with_style(self, mock_service_dep, mock_auth):
        """Test synthesized search with response style"""
        mock_auth.return_value = self.api_key

        mock_service = Mock()
        mock_service.search_with_synthesis = AsyncMock(return_value={
            "synthesis": "Brief synthesis",
            "sources": []
        })
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search/synthesized",
            json={"query": "test", "top_k": 5, "style": "concise"},
            headers=self.headers
        )

        assert response.status_code == 200
        mock_service.search_with_synthesis.assert_called_once()
        call_args = mock_service.search_with_synthesis.call_args
        assert call_args.kwargs["style"] == "concise"


class TestStructuredSearchEndpoint:
    """Tests for POST /v1/search/structured endpoint"""

    def setup_method(self):
        """Setup test client and mocks"""
        self.client = TestClient(app)
        self.api_key = "test-api-key"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_structured_search_success(self, mock_service_dep, mock_auth):
        """Test successful structured search"""
        mock_auth.return_value = self.api_key

        mock_service = Mock()
        mock_service.search_with_structure = AsyncMock(return_value={
            "executive_summary": "Key findings on Gen Z trends",
            "key_statistics": [
                "65% prefer mobile shopping",
                "80% value sustainability"
            ],
            "recommendations": [
                "Invest in mobile-first design",
                "Highlight sustainability"
            ],
            "sources": ["Forrester", "Gartner"]
        })
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search/structured",
            json={"query": "Gen Z shopping behavior", "top_k": 15},
            headers=self.headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "executive_summary" in data
        assert "key_statistics" in data
        assert "recommendations" in data
        assert len(data["key_statistics"]) == 2


class TestAdvancedSearchEndpoint:
    """Tests for POST /v1/search/advanced endpoint"""

    def setup_method(self):
        """Setup test client and mocks"""
        self.client = TestClient(app)
        self.api_key = "test-api-key"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_advanced_search_success(self, mock_service_dep, mock_auth):
        """Test successful advanced search"""
        mock_auth.return_value = self.api_key

        mock_service = Mock()
        mock_service.advanced_search = AsyncMock(return_value={
            "results": [
                {"content": "Result 1", "score": 0.95},
                {"content": "Result 2", "score": 0.87}
            ],
            "analysis": "Advanced analysis of results",
            "metadata": {"query_type": "multi_dimensional"}
        })
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search/advanced",
            json={
                "query": "AI + sustainability + Gen Z",
                "top_k": 20,
                "mode": "multi_dimensional"
            },
            headers=self.headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert "analysis" in data
        assert data["metadata"]["query_type"] == "multi_dimensional"

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_advanced_search_with_filters(self, mock_service_dep, mock_auth):
        """Test advanced search with category filters"""
        mock_auth.return_value = self.api_key

        mock_service = Mock()
        mock_service.advanced_search = AsyncMock(return_value={
            "results": [],
            "metadata": {}
        })
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search/advanced",
            json={
                "query": "trends",
                "top_k": 10,
                "categories": ["TECHNOLOGY", "MARKETING"]
            },
            headers=self.headers
        )

        assert response.status_code == 200
        mock_service.advanced_search.assert_called_once()


class TestErrorHandling:
    """Tests for error handling across all search endpoints"""

    def setup_method(self):
        """Setup test client"""
        self.client = TestClient(app)
        self.api_key = "test-api-key"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_chromadb_connection_error(self, mock_service_dep, mock_auth):
        """Test handling of ChromaDB connection errors"""
        from chromadb_wrapper import ChromaDBConnectionError

        mock_auth.return_value = self.api_key
        mock_service = Mock()
        mock_service.basic_search = AsyncMock(
            side_effect=ChromaDBConnectionError("Database unavailable")
        )
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search",
            json={"query": "test", "top_k": 5},
            headers=self.headers
        )

        assert response.status_code == 503  # Service Unavailable
        assert "database" in response.json()["detail"].lower()

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_circuit_breaker_open(self, mock_service_dep, mock_auth):
        """Test handling when circuit breaker is open"""
        from resilience import CircuitBreakerOpenError

        mock_auth.return_value = self.api_key
        mock_service = Mock()
        mock_service.basic_search = AsyncMock(
            side_effect=CircuitBreakerOpenError("Circuit breaker open")
        )
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search",
            json={"query": "test", "top_k": 5},
            headers=self.headers
        )

        assert response.status_code == 503
        assert "circuit breaker" in response.json()["detail"].lower()

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_suspicious_input_error(self, mock_service_dep, mock_auth):
        """Test handling of suspicious input"""
        from input_validation import SuspiciousInputError

        mock_auth.return_value = self.api_key
        mock_service = Mock()
        mock_service.basic_search = AsyncMock(
            side_effect=SuspiciousInputError("Malicious pattern detected")
        )
        mock_service_dep.return_value = mock_service

        response = self.client.post(
            "/v1/search",
            json={"query": "<script>alert('xss')</script>", "top_k": 5},
            headers=self.headers
        )

        assert response.status_code == 400
        assert "suspicious" in response.json()["detail"].lower() or "malicious" in response.json()["detail"].lower()


class TestRateLimiting:
    """Tests for rate limiting on search endpoints"""

    def setup_method(self):
        """Setup test client"""
        self.client = TestClient(app)
        self.api_key = "test-api-key"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @pytest.mark.skip(reason="Rate limiting requires external service - test in integration")
    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_rate_limit_exceeded(self, mock_service_dep, mock_auth):
        """Test rate limiting (integration test placeholder)"""
        # This would require actual rate limiter setup
        # Include as placeholder for integration tests
        pass


class TestBackwardCompatibility:
    """Tests for backward compatibility endpoints"""

    def setup_method(self):
        """Setup test client"""
        self.client = TestClient(app)
        self.api_key = "test-api-key"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @patch('main.verify_api_key')
    @patch('main.get_search_service')
    def test_unversioned_search_redirects(self, mock_service_dep, mock_auth):
        """Test that /search redirects to /v1/search"""
        mock_auth.return_value = self.api_key
        mock_service = Mock()
        mock_service.basic_search = AsyncMock(return_value=[])
        mock_service_dep.return_value = mock_service

        # Try unversioned endpoint
        response = self.client.post(
            "/search",
            json={"query": "test", "top_k": 5},
            headers=self.headers
        )

        # Should still work (backward compatibility)
        assert response.status_code in [200, 307]  # 200 OK or 307 Temporary Redirect


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
