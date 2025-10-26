"""
Structured Response Framework

Transforms raw search results into structured, actionable insights following
the framework defined in claude.md:

1. Identify Relevant Trends (3-5)
2. Provide Context (why they matter)
3. Share Data Points (statistics and sources)
4. Suggest Applications (practical use cases)
5. Connect Opportunities (trend intersections)
6. Inspire Action (next steps)

Uses LLM to generate high-quality, professional responses suitable for
client presentations and strategic planning.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pydantic import BaseModel, Field
from llm_service import LLMService, PromptTemplates

logger = logging.getLogger(__name__)


class DataPoint(BaseModel):
    """Individual data point or statistic"""
    statistic: str = Field(description="The statistic or data point")
    source: str = Field(description="Source of the data")
    context: Optional[str] = Field(None, description="Additional context")


class StructuredResponse(BaseModel):
    """
    Structured response format matching claude.md specification

    Designed for professional presentations and strategic planning.
    """
    query: str = Field(description="Original search query")

    relevant_trends: List[str] = Field(
        description="3-5 most applicable trends identified",
        min_items=1,
        max_items=5
    )

    context: str = Field(
        description="Explanation of why these trends matter for the use case"
    )

    data_points: List[DataPoint] = Field(
        description="Key statistics, projections, and credible data",
        default_factory=list
    )

    applications: List[str] = Field(
        description="Practical ways to apply insights to campaigns/strategies",
        default_factory=list
    )

    connections: List[str] = Field(
        description="Intersection points between trends and opportunities",
        default_factory=list
    )

    next_steps: List[str] = Field(
        description="Suggested actions and creative starting points",
        default_factory=list
    )

    confidence_level: str = Field(
        default="medium",
        description="Overall confidence in recommendations (high/medium/low)"
    )

    sources_analyzed: int = Field(
        description="Number of unique sources analyzed"
    )


class ResponseFormatter:
    """
    Transforms raw search results into structured, actionable responses

    Uses LLM for intelligent synthesis and formatting.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize response formatter

        Args:
            llm_service: LLM service for intelligent formatting
        """
        self.llm_service = llm_service

        if llm_service:
            logger.info("Response formatter initialized with LLM support")
        else:
            logger.warning("Response formatter initialized without LLM (limited functionality)")

    async def format_response(
        self,
        query: str,
        results: List[Dict[str, Any]],
        user_context: Optional[str] = None
    ) -> StructuredResponse:
        """
        Format search results into structured response

        Args:
            query: Original search query
            results: Raw search results
            user_context: Optional context about user's industry/needs

        Returns:
            StructuredResponse with formatted insights
        """
        if not self.llm_service:
            # Fallback to basic formatting without LLM
            return self._format_basic(query, results)

        try:
            # Build prompt for LLM
            prompt = self._build_formatting_prompt(query, results, user_context)

            # Generate structured response
            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                max_tokens=2000,
                temperature=0.5
            )

            # Parse JSON response
            structured_data = json.loads(response.content)

            # Add metadata
            structured_data["query"] = query
            structured_data["sources_analyzed"] = len(set(r.get("source") for r in results))

            # Ensure data_points are properly formatted
            if "data_points" in structured_data:
                structured_data["data_points"] = [
                    DataPoint(**dp) if isinstance(dp, dict) else dp
                    for dp in structured_data["data_points"]
                ]

            return StructuredResponse(**structured_data)

        except Exception as e:
            logger.error(f"LLM formatting failed: {e}", exc_info=True)
            return self._format_basic(query, results)

    def _build_formatting_prompt(
        self,
        query: str,
        results: List[Dict[str, Any]],
        user_context: Optional[str]
    ) -> str:
        """Build prompt for structured response generation"""

        # Format results for prompt
        results_text = "\n\n".join([
            f"[{i+1}] {r.get('content', '')[:300]}...\n"
            f"    Source: {r.get('source', 'Unknown')}\n"
            f"    Relevance: {r.get('relevance_score', 0):.2f}"
            for i, r in enumerate(results[:8])  # Limit to top 8 results
        ])

        context_section = ""
        if user_context:
            context_section = f"\nUser Context: {user_context}\n"

        prompt = f"""Analyze these trend report excerpts and create a structured strategic response.

Query: "{query}"{context_section}

Search Results from Trend Reports:
{results_text}

Create a comprehensive analysis in JSON format with:

{{
  "relevant_trends": [
    "Trend 1: Clear, specific name",
    "Trend 2: Clear, specific name",
    "Trend 3: Clear, specific name"
  ],
  "context": "2-3 paragraphs explaining why these trends matter specifically for this query. Include market implications, timing considerations, and strategic importance.",
  "data_points": [
    {{
      "statistic": "Specific number or percentage with description",
      "source": "Report name from the results",
      "context": "Brief context about what this means"
    }}
  ],
  "applications": [
    "Practical application 1: How to use this insight in campaigns",
    "Practical application 2: Strategic implementation approach",
    "Practical application 3: Tactical execution ideas"
  ],
  "connections": [
    "How Trend 1 and Trend 2 intersect to create new opportunities",
    "How these trends collectively point to a larger shift"
  ],
  "next_steps": [
    "Immediate action: What to do this week/month",
    "Medium-term: 3-6 month initiatives",
    "Long-term: Strategic positioning"
  ],
  "confidence_level": "high/medium/low based on data quality and consensus"
}}

Important:
- Extract 3-5 specific, actionable trends (not vague themes)
- Pull actual statistics from the results when available
- Make applications practical and specific
- Ensure next_steps are concrete actions, not generic advice
- Base confidence on number of sources and consistency of findings"""

        return prompt

    def _get_system_prompt(self) -> str:
        """Get system prompt for response formatting"""
        return """You are a strategic trend analyst for creative agencies and marketing teams.

Your role is to transform trend research into actionable strategic insights that:
- Are specific and concrete (not generic)
- Include measurable data points where available
- Connect trends to real-world applications
- Provide clear next steps for implementation
- Maintain a professional but accessible tone

You analyze trends for clients in advertising, marketing, and business strategy.
Your outputs are used in client presentations, strategic planning, and campaign development.

Always ground your analysis in the actual data provided - don't invent statistics.
When data is limited, acknowledge it and adjust confidence accordingly."""

    def _format_basic(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> StructuredResponse:
        """Basic formatting without LLM (fallback)"""

        unique_sources = set(r.get("source") for r in results)

        # Extract trends from content (simple keyword extraction)
        trends = []
        for r in results[:5]:
            content = r.get("content", "")
            # Very basic trend extraction - just use first sentence
            first_sentence = content.split('.')[0] if '.' in content else content[:100]
            if first_sentence and first_sentence not in trends:
                trends.append(first_sentence)

        return StructuredResponse(
            query=query,
            relevant_trends=trends[:3] if trends else ["Trend analysis requires LLM integration"],
            context=(
                f"Analysis of {len(results)} insights from {len(unique_sources)} trend reports. "
                "For detailed analysis and strategic recommendations, enable LLM integration."
            ),
            data_points=[
                DataPoint(
                    statistic=f"{len(results)} relevant insights identified",
                    source=f"{len(unique_sources)} unique trend reports",
                    context="Coverage analysis"
                )
            ],
            applications=[
                "Enable LLM integration for specific applications",
                "Review raw search results for manual analysis"
            ],
            connections=[
                f"Results span {len(unique_sources)} different sources"
            ],
            next_steps=[
                "Configure LLM service for enhanced analysis",
                "Review individual search results for insights"
            ],
            confidence_level="low",
            sources_analyzed=len(unique_sources)
        )


class ResponseStyle:
    """Different response styles for different use cases"""

    @staticmethod
    def executive_summary(response: StructuredResponse) -> str:
        """Format as executive summary"""
        summary = f"""# Trend Analysis: {response.query}

## Executive Summary
{response.context}

## Key Trends Identified
"""
        for i, trend in enumerate(response.relevant_trends, 1):
            summary += f"{i}. {trend}\n"

        if response.data_points:
            summary += "\n## Supporting Data\n"
            for dp in response.data_points[:5]:
                summary += f"- {dp.statistic} ({dp.source})\n"

        summary += f"\n## Confidence: {response.confidence_level.upper()}\n"
        summary += f"Based on analysis of {response.sources_analyzed} authoritative sources.\n"

        return summary

    @staticmethod
    def campaign_brief(response: StructuredResponse) -> str:
        """Format as campaign brief"""
        brief = f"""# Campaign Brief: {response.query}

## Strategic Context
{response.context}

## Trend Opportunities
"""
        for i, trend in enumerate(response.relevant_trends, 1):
            brief += f"\n### {i}. {trend}\n"
            if i <= len(response.applications):
                brief += f"**Application**: {response.applications[i-1]}\n"

        if response.connections:
            brief += "\n## Opportunity Intersections\n"
            for connection in response.connections:
                brief += f"- {connection}\n"

        brief += "\n## Recommended Next Steps\n"
        for i, step in enumerate(response.next_steps, 1):
            brief += f"{i}. {step}\n"

        return brief

    @staticmethod
    def presentation_slides(response: StructuredResponse) -> List[Dict[str, str]]:
        """Format as presentation slide content"""
        slides = []

        # Title slide
        slides.append({
            "title": f"Trend Analysis: {response.query}",
            "subtitle": f"Analysis of {response.sources_analyzed} authoritative sources",
            "type": "title"
        })

        # Trends slide
        slides.append({
            "title": "Key Trends Identified",
            "content": "\n".join(f"• {trend}" for trend in response.relevant_trends),
            "type": "bullets"
        })

        # Context slide
        slides.append({
            "title": "Why This Matters",
            "content": response.context,
            "type": "text"
        })

        # Data slide
        if response.data_points:
            slides.append({
                "title": "Supporting Data",
                "content": "\n".join(
                    f"• {dp.statistic}\n  Source: {dp.source}"
                    for dp in response.data_points[:4]
                ),
                "type": "data"
            })

        # Applications slide
        if response.applications:
            slides.append({
                "title": "Practical Applications",
                "content": "\n".join(f"• {app}" for app in response.applications),
                "type": "bullets"
            })

        # Next steps slide
        slides.append({
            "title": "Recommended Next Steps",
            "content": "\n".join(f"{i}. {step}" for i, step in enumerate(response.next_steps, 1)),
            "type": "action"
        })

        return slides


# Example usage
if __name__ == "__main__":
    import asyncio
    from llm_service import get_llm_service

    async def test_formatter():
        """Test response formatter"""
        logging.basicConfig(level=logging.INFO)

        # Mock results
        test_results = [
            {
                "content": "AI-powered personalization drives 35% increase in customer engagement across retail sectors",
                "source": "McKinsey_Retail_2025.pdf",
                "relevance_score": 0.95
            },
            {
                "content": "Machine learning enables real-time product recommendations with 90% accuracy",
                "source": "Gartner_AI_Marketing.pdf",
                "relevance_score": 0.92
            },
            {
                "content": "Brands using AI personalization see 25% higher conversion rates and improved ROI",
                "source": "Forrester_Digital_Strategy.pdf",
                "relevance_score": 0.88
            }
        ]

        llm = get_llm_service()
        if llm:
            formatter = ResponseFormatter(llm_service=llm)

            response = await formatter.format_response(
                query="AI personalization for e-commerce campaigns",
                results=test_results,
                user_context="Luxury retail brand launching new digital strategy"
            )

            print("\n" + "="*60)
            print("STRUCTURED RESPONSE")
            print("="*60)
            print(f"\nQuery: {response.query}")
            print(f"\nTrends ({len(response.relevant_trends)}):")
            for trend in response.relevant_trends:
                print(f"  • {trend}")

            print(f"\nContext:\n{response.context}")

            print(f"\nData Points ({len(response.data_points)}):")
            for dp in response.data_points:
                print(f"  • {dp.statistic} - {dp.source}")

            print(f"\nApplications ({len(response.applications)}):")
            for app in response.applications:
                print(f"  • {app}")

            print(f"\nNext Steps ({len(response.next_steps)}):")
            for i, step in enumerate(response.next_steps, 1):
                print(f"  {i}. {step}")

            print(f"\nConfidence: {response.confidence_level.upper()}")
            print("="*60)

            # Test executive summary format
            print("\n" + ResponseStyle.executive_summary(response))

    asyncio.run(test_formatter())
