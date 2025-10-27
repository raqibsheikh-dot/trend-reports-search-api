"""
Admin Router

Administrative endpoints for the Trend Intelligence API.
Includes cache management and system administration.

Extracted from main.py to improve code organization.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated, Optional
import logging

logger = logging.getLogger(__name__)

# Create router - will be included by v1_router in main.py
router = APIRouter(tags=["admin"])

# Import dependencies from main at module level
# This must happen before the decorators are used
from main import (
    get_cache,
    verify_api_key,
    QueryCache
)


@router.get("/cache/stats")
async def cache_stats(
    cache: Annotated[Optional[QueryCache], Depends(get_cache)]
):
    """
    Get cache statistics

    Returns:
        Cache performance metrics including hit/miss rates, size, etc.
    """
    if not cache:
        return {
            "enabled": False,
            "message": "Caching is disabled"
        }

    stats = cache.get_stats()
    return {
        "enabled": True,
        **stats
    }


@router.post("/cache/clear")
async def clear_cache(
    cache: Annotated[Optional[QueryCache], Depends(get_cache)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Clear all cached search results

    Requires authentication. Useful for invalidating cache after data updates.

    Returns:
        Success status
    """
    if not cache:
        return {"success": False, "message": "Caching is disabled"}

    success = cache.clear_all()
    if success:
        logger.info("Cache cleared via API")
        return {"success": True, "message": "Cache cleared successfully"}
    else:
        logger.error("Failed to clear cache")
        raise HTTPException(status_code=500, detail="Failed to clear cache")
