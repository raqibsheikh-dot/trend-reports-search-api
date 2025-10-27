"""
Services Module

Business logic layer for the Trend Intelligence API.
Extracts domain logic from framework code for better maintainability.
"""

from .search_service import SearchService, create_search_service, SearchRequest, SearchResult

__all__ = [
    "SearchService",
    "create_search_service",
    "SearchRequest",
    "SearchResult",
]
