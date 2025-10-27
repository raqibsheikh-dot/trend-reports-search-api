"""
Routers Module

FastAPI routers for organizing endpoints by domain.
Reduces main.py complexity by extracting endpoint groups into focused modules.
"""

from .search_router import router as search_router
from .admin_router import router as admin_router
from .util_router import router as util_router

__all__ = [
    "search_router",
    "admin_router",
    "util_router",
]
