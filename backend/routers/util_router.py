"""
Utility Router

Utility endpoints for the Trend Intelligence API.
Includes categories listing and LLM statistics.

Extracted from main.py to improve code organization.
"""

from fastapi import APIRouter, Depends
from typing import Annotated, Optional
import logging

logger = logging.getLogger(__name__)

# Create router - will be included by v1_router in main.py
router = APIRouter(tags=["utilities"])

# Import dependencies from main at module level
# This must happen before the decorators are used
from main import (
    get_llm,
    TrendCategory
)


@router.get("/categories")
async def list_categories():
    """
    List available trend categories

    Returns:
        List of category names and descriptions
    """
    return {
        "categories": [
            {
                "id": cat.name,
                "name": cat.value,
                "description": f"Trends related to {cat.value.lower()}"
            }
            for cat in TrendCategory
        ]
    }


@router.get("/llm/stats")
async def llm_stats(
    llm: Annotated[Optional['LLMService'], Depends(get_llm)]
):
    """
    Get LLM usage statistics

    Returns cost tracking and usage metrics for LLM-powered features.
    """
    if not llm:
        return {
            "enabled": False,
            "message": "LLM service not configured"
        }

    stats = llm.get_cost_stats()
    return {
        "enabled": True,
        **stats
    }
