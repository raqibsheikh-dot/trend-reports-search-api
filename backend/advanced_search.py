"""
Advanced Query Types

Implements sophisticated search patterns from claude.md:
1. Multi-dimensional queries: Intersection of multiple concepts (e.g., "AI + sustainability + Gen Z")
2. Scenario-based search: "What if" scenarios (e.g., "luxury brands entering metaverse")
3. Trend stacking: Combining specific trends to find synergies
4. Query expansion: Generating related queries for broader coverage

Uses LLM for query understanding and expansion.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field
from llm_service import LLMService
from fastembed import TextEmbedding
import chromadb

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Advanced query types"""
    SIMPLE = "simple"
    MULTI_DIMENSIONAL = "multi_dimensional"
    SCENARIO = "scenario"
    TREND_STACK = "trend_stack"


class AdvancedSearchRequest(BaseModel):
    """Request model for advanced search"""
    query: str = Field(description="Main search query")
    query_type: QueryType = Field(
        default=QueryType.SIMPLE,
        description="Type of advanced search to perform"
    )
    dimensions: Optional[List[str]] = Field(
        None,
        description="For multi-dimensional: list of concepts to intersect"
    )
    scenario: Optional[str] = Field(
        None,
        description="For scenario-based: the scenario context"
    )
    trends: Optional[List[str]] = Field(
        None,
        description="For trend stacking: specific trends to combine"
    )
    top_k: int = Field(default=5, ge=1, le=20)
    enable_expansion: bool = Field(
        default=False,
        description="Enable query expansion for broader results"
    )


class AdvancedSearchEngine:
    """
    Advanced search engine with multiple query strategies

    Combines vector search with LLM-powered query understanding
    for sophisticated information retrieval.
    """

    def __init__(
        self,
        embedder: TextEmbedding,
        collection: chromadb.Collection,
        llm_service: Optional[LLMService] = None
    ):
        """
        Initialize advanced search engine

        Args:
            embedder: Embedding model
            collection: ChromaDB collection
            llm_service: LLM service for query expansion
        """
        self.embedder = embedder
        self.collection = collection
        self.llm_service = llm_service

        logger.info("Advanced search engine initialized")

    async def search(
        self,
        request: AdvancedSearchRequest
    ) -> Dict[str, Any]:
        """
        Execute advanced search based on query type

        Args:
            request: Advanced search request

        Returns:
            Search results with metadata
        """
        if request.query_type == QueryType.MULTI_DIMENSIONAL:
            return await self.multi_dimensional_search(
                main_query=request.query,
                dimensions=request.dimensions or [],
                top_k=request.top_k
            )

        elif request.query_type == QueryType.SCENARIO:
            return await self.scenario_search(
                query=request.query,
                scenario=request.scenario or "",
                top_k=request.top_k
            )

        elif request.query_type == QueryType.TREND_STACK:
            return await self.trend_stack_search(
                trends=request.trends or [request.query],
                top_k=request.top_k
            )

        else:  # SIMPLE
            if request.enable_expansion and self.llm_service:
                return await self.expanded_search(request.query, request.top_k)
            else:
                return await self.simple_search(request.query, request.top_k)

    async def multi_dimensional_search(
        self,
        main_query: str,
        dimensions: List[str],
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Multi-dimensional search: Find intersection of multiple concepts

        Example: "AI + sustainability + Gen Z values"

        Args:
            main_query: Primary search query
            dimensions: Additional dimensions to consider
            top_k: Results per dimension

        Returns:
            Combined results ranked by relevance across all dimensions
        """
        logger.info(f"Multi-dimensional search: {main_query} + {dimensions}")

        # Build combined query
        all_concepts = [main_query] + dimensions
        combined_query = " AND ".join(all_concepts)

        # If LLM available, enhance the query
        if self.llm_service:
            enhanced_query = await self._enhance_multi_dim_query(main_query, dimensions)
        else:
            enhanced_query = combined_query

        # Perform searches for each dimension
        dimension_results = []

        for concept in all_concepts:
            results = await self.simple_search(concept, top_k=top_k)
            dimension_results.append({
                "concept": concept,
                "results": results["results"]
            })

        # Also search the combined query
        combined_results = await self.simple_search(enhanced_query, top_k=top_k * 2)

        # Find documents that appear across multiple dimensions (intersection)
        doc_scores = {}

        for dim_result in dimension_results:
            for result in dim_result["results"]:
                doc_id = f"{result['source']}:{result['page']}"

                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "result": result,
                        "dimensions_matched": set(),
                        "avg_score": 0.0
                    }

                doc_scores[doc_id]["dimensions_matched"].add(dim_result["concept"])
                doc_scores[doc_id]["avg_score"] += result["relevance_score"]

        # Calculate final scores (favor documents matching multiple dimensions)
        for doc_id, data in doc_scores.items():
            match_count = len(data["dimensions_matched"])
            data["avg_score"] = data["avg_score"] / match_count
            # Boost score based on number of dimensions matched
            data["multi_dim_score"] = data["avg_score"] * (1 + (match_count - 1) * 0.2)

        # Sort by multi-dimensional score
        ranked_results = sorted(
            doc_scores.values(),
            key=lambda x: x["multi_dim_score"],
            reverse=True
        )[:top_k]

        return {
            "query": main_query,
            "query_type": "multi_dimensional",
            "dimensions": all_concepts,
            "results": [
                {
                    **r["result"],
                    "dimensions_matched": list(r["dimensions_matched"]),
                    "match_count": len(r["dimensions_matched"]),
                    "multi_dim_score": round(r["multi_dim_score"], 3)
                }
                for r in ranked_results
            ],
            "metadata": {
                "total_dimensions": len(all_concepts),
                "enhanced_query": enhanced_query
            }
        }

    async def scenario_search(
        self,
        query: str,
        scenario: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Scenario-based search: "What if" analysis

        Example: "What if luxury brands enter the metaverse?"

        Args:
            query: Main query/topic
            scenario: Scenario description
            top_k: Number of results

        Returns:
            Results relevant to the scenario
        """
        logger.info(f"Scenario search: {query} in scenario: {scenario}")

        # If LLM available, expand scenario into search queries
        if self.llm_service:
            search_queries = await self._expand_scenario_query(query, scenario)
        else:
            search_queries = [f"{query} {scenario}"]

        # Search for each expanded query
        all_results = []

        for sq in search_queries:
            results = await self.simple_search(sq, top_k=top_k)
            all_results.extend(results["results"])

        # Deduplicate and rank
        seen = set()
        unique_results = []

        for result in all_results:
            doc_id = f"{result['source']}:{result['page']}"
            if doc_id not in seen:
                seen.add(doc_id)
                unique_results.append(result)

        # Take top results
        unique_results = sorted(
            unique_results,
            key=lambda x: x["relevance_score"],
            reverse=True
        )[:top_k]

        return {
            "query": query,
            "query_type": "scenario",
            "scenario": scenario,
            "results": unique_results,
            "metadata": {
                "expanded_queries": search_queries,
                "scenario_context": scenario
            }
        }

    async def trend_stack_search(
        self,
        trends: List[str],
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Trend stacking: Find synergies between specific trends

        Example: ["personalization", "social commerce", "AR"]

        Args:
            trends: List of trends to stack
            top_k: Number of results

        Returns:
            Results showing trend intersections
        """
        logger.info(f"Trend stacking: {trends}")

        # Search for each trend
        trend_results = {}

        for trend in trends:
            results = await self.simple_search(trend, top_k=top_k * 2)
            trend_results[trend] = results["results"]

        # Find documents mentioning multiple trends
        doc_trend_map = {}

        for trend, results in trend_results.items():
            for result in results:
                doc_id = f"{result['source']}:{result['page']}"

                if doc_id not in doc_trend_map:
                    doc_trend_map[doc_id] = {
                        "result": result,
                        "trends_found": set(),
                        "synergy_score": 0.0
                    }

                doc_trend_map[doc_id]["trends_found"].add(trend)
                doc_trend_map[doc_id]["synergy_score"] += result["relevance_score"]

        # Rank by synergy (documents with more trends ranked higher)
        synergy_results = []

        for doc_id, data in doc_trend_map.items():
            trend_count = len(data["trends_found"])

            # Only include if at least 2 trends found
            if trend_count >= 2:
                synergy_score = data["synergy_score"] * trend_count
                synergy_results.append({
                    **data["result"],
                    "trends_found": list(data["trends_found"]),
                    "trend_count": trend_count,
                    "synergy_score": round(synergy_score, 3)
                })

        # Sort by synergy score
        synergy_results = sorted(
            synergy_results,
            key=lambda x: x["synergy_score"],
            reverse=True
        )[:top_k]

        return {
            "query": " + ".join(trends),
            "query_type": "trend_stack",
            "trends": trends,
            "results": synergy_results,
            "metadata": {
                "total_trends": len(trends),
                "synergies_found": len(synergy_results)
            }
        }

    async def expanded_search(
        self,
        query: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Expanded search: Generate similar queries for broader coverage

        Args:
            query: Original query
            top_k: Results per query variant

        Returns:
            Combined results from all query variants
        """
        if not self.llm_service:
            return await self.simple_search(query, top_k)

        # Generate query variants
        variants = await self._expand_query(query)

        logger.info(f"Query expansion: {query} -> {variants}")

        # Search for each variant
        all_results = []

        for variant in [query] + variants:
            results = await self.simple_search(variant, top_k=top_k)
            all_results.extend(results["results"])

        # Deduplicate and rank
        seen = set()
        unique_results = []

        for result in all_results:
            doc_id = f"{result['source']}:{result['page']}"
            if doc_id not in seen:
                seen.add(doc_id)
                unique_results.append(result)

        # Take top results
        unique_results = sorted(
            unique_results,
            key=lambda x: x["relevance_score"],
            reverse=True
        )[:top_k * 2]  # Return more results with expansion

        return {
            "query": query,
            "query_type": "expanded",
            "results": unique_results,
            "metadata": {
                "original_query": query,
                "expanded_queries": variants,
                "total_variants": len(variants) + 1
            }
        }

    async def simple_search(
        self,
        query: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Simple vector search (baseline)

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Search results
        """
        # Embed query
        query_embedding = list(self.embedder.embed([query]))[0].tolist()

        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        # Format results
        formatted_results = []

        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append({
                    "content": doc,
                    "source": results["metadatas"][0][i].get("filename", "Unknown"),
                    "page": results["metadatas"][0][i].get("page", 0),
                    "relevance_score": round(1 - results["distances"][0][i], 3)
                })

        return {
            "query": query,
            "query_type": "simple",
            "results": formatted_results
        }

    async def _enhance_multi_dim_query(
        self,
        main_query: str,
        dimensions: List[str]
    ) -> str:
        """Use LLM to create enhanced multi-dimensional query"""
        prompt = f"""Create a search query that captures the intersection of these concepts:

Main concept: {main_query}
Additional dimensions: {', '.join(dimensions)}

Return only the enhanced search query (1-2 sentences), no explanation."""

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                max_tokens=100,
                temperature=0.3
            )
            return response.content.strip()
        except Exception as e:
            logger.error(f"Query enhancement failed: {e}")
            return f"{main_query} {' '.join(dimensions)}"

    async def _expand_scenario_query(
        self,
        query: str,
        scenario: str
    ) -> List[str]:
        """Expand scenario into multiple search queries"""
        prompt = f"""Generate 3 search queries to explore this scenario:

Topic: {query}
Scenario: {scenario}

Return only the 3 queries, one per line, no numbering."""

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                max_tokens=150,
                temperature=0.5
            )

            queries = [
                q.strip()
                for q in response.content.split('\n')
                if q.strip()
            ]

            return queries[:3]

        except Exception as e:
            logger.error(f"Scenario expansion failed: {e}")
            return [f"{query} {scenario}"]

    async def _expand_query(self, query: str) -> List[str]:
        """Expand query into related searches"""
        prompt = f"""Generate 3 similar search queries for: "{query}"

Return only the queries, one per line, no numbering or explanation."""

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                max_tokens=100,
                temperature=0.6
            )

            queries = [
                q.strip()
                for q in response.content.split('\n')
                if q.strip() and q.strip() != query
            ]

            return queries[:3]

        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return []


# Example usage
if __name__ == "__main__":
    # This would be tested with actual embedder and collection
    print("Advanced search engine module loaded")
    print("Use with FastAPI endpoints for full functionality")
