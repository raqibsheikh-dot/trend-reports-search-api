"""
Search Router

All search-related endpoints for the Trend Intelligence API.
Extracted from main.py to improve code organization.

This router is included in v1_router after all dependencies are initialized.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from typing import List, Annotated
import logging

# Exception imports
from input_validation import SuspiciousInputError, ValidationError as InputValidationError
from chromadb_wrapper import (
    ChromaDBConnectionError,
    ChromaDBQueryError,
    ChromaDBTimeoutError
)
from resilience import CircuitBreakerOpenError

logger = logging.getLogger(__name__)

# Create router - will be included by v1_router in main.py
router = APIRouter(tags=["search"])

# Import dependencies from main at module level
# This must happen before the decorators are used
# This is safe because the router is imported after main defines these
from main import (
    get_search_service,
    get_synthesizer,
    get_formatter,
    get_advanced_search,
    verify_api_key,
    request_id_var,
    SearchRequest,
    AdvancedSearchRequest,
    SearchResult,
    settings,
    limiter,
    SearchService,
    TrendSynthesizer,
    ResponseFormatter,
    AdvancedSearchEngine
)


@router.post("/search")
@limiter.limit(settings.rate_limit)
async def search_trends(
    request: Request,
    search_request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Search trend reports - called by Custom GPT

    Delegates to SearchService for all business logic.
    This endpoint is now a thin controller layer that maps exceptions to HTTP responses.

    Args:
        request: FastAPI request object (for rate limiting)
        search_request: Search query and parameters
        service: Injected SearchService (handles all business logic)
        _: API key verification (discarded after validation)

    Returns:
        List of SearchResult objects with content, source, page, and relevance score

    Raises:
        HTTPException: 400/503/504/500 depending on error type
    """
    try:
        return await service.basic_search(
            query=search_request.query,
            top_k=search_request.top_k
        )
    except SuspiciousInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CircuitBreakerOpenError:
        raise HTTPException(
            status_code=503,
            detail="Search service is temporarily degraded. Please try again in a minute."
        )
    except ChromaDBTimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Search request timed out. Please try a simpler query or try again later."
        )
    except ChromaDBConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to search database. Service temporarily unavailable."
        )
    except ChromaDBQueryError:
        raise HTTPException(
            status_code=500,
            detail="Search query failed. Please try again or contact support."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid search parameters: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected search error: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during search")


@router.post("/search/synthesized")
@limiter.limit(settings.rate_limit)
async def search_with_synthesis(
    request: Request,
    search_request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
    synthesizer: Annotated[TrendSynthesizer, Depends(get_synthesizer)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Search with cross-report synthesis

    Delegates to SearchService for search, then applies synthesis.
    Identifies meta-trends, consensus, and contradictions across sources.

    Returns:
        Synthesized insights with meta-trends and analysis
    """
    request_id = request_id_var.get()

    try:
        # Perform base search using service
        base_results = await service.basic_search(
            query=search_request.query,
            top_k=search_request.top_k
        )

        # Convert SearchResult objects to dicts for synthesis
        results_dicts = [r.model_dump() for r in base_results]

        # Perform synthesis
        synthesis_result = await synthesizer.synthesize(
            query=search_request.query,
            results=results_dicts,
            min_sources_for_meta=2
        )

        logger.info(
            f"[{request_id}] Synthesis completed: "
            f"{len(synthesis_result.meta_trends)} meta-trends identified"
        )

        return synthesizer.format_for_display(synthesis_result)

    except (SuspiciousInputError, InputValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CircuitBreakerOpenError:
        raise HTTPException(status_code=503, detail="Service temporarily degraded")
    except Exception as e:
        logger.error(f"[{request_id}] Synthesis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Synthesis failed. Ensure LLM service is configured."
        )


@router.post("/search/structured")
@limiter.limit(settings.rate_limit)
async def search_with_structure(
    request: Request,
    search_request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
    formatter: Annotated[ResponseFormatter, Depends(get_formatter)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Search with structured response format

    Delegates to SearchService for search, then applies structured formatting.
    Returns results formatted according to claude.md framework.

    Returns:
        Structured response with actionable insights
    """
    request_id = request_id_var.get()

    try:
        # Perform base search using service
        base_results = await service.basic_search(
            query=search_request.query,
            top_k=search_request.top_k
        )

        # Convert to dicts for formatting
        results_dicts = [r.model_dump() for r in base_results]

        # Format response
        structured_response = await formatter.format_response(
            query=search_request.query,
            results=results_dicts
        )

        logger.info(
            f"[{request_id}] Structured response generated: "
            f"{len(structured_response.relevant_trends)} trends, "
            f"{len(structured_response.applications)} applications"
        )

        return structured_response.model_dump()

    except (SuspiciousInputError, InputValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CircuitBreakerOpenError:
        raise HTTPException(status_code=503, detail="Service temporarily degraded")
    except Exception as e:
        logger.error(f"[{request_id}] Response formatting failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Response formatting failed. Ensure LLM service is configured."
        )


@router.post("/search/advanced")
@limiter.limit(settings.rate_limit)
async def advanced_search(
    request: Request,
    search_request: AdvancedSearchRequest,
    advanced_engine: Annotated[AdvancedSearchEngine, Depends(get_advanced_search)],
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    Advanced search with multiple query strategies

    Supported query types:
    - simple: Standard vector search
    - multi_dimensional: Intersection of multiple concepts
    - scenario: "What if" scenario analysis
    - trend_stack: Combine specific trends

    Args:
        search_request: Advanced search request with query_type and parameters

    Returns:
        Results optimized for the selected query type
    """
    request_id = request_id_var.get()

    try:
        results = await advanced_engine.search(search_request)

        logger.info(
            f"[{request_id}] Advanced search ({search_request.query_type}): "
            f"{len(results.get('results', []))} results"
        )

        return results

    except Exception as e:
        logger.error(f"[{request_id}] Advanced search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Advanced search failed: {str(e)}"
        )
