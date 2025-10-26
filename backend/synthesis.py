"""
Cross-Report Synthesis Engine

Analyzes search results across multiple trend reports to identify:
- Meta-trends (patterns appearing across multiple sources)
- Contradictions and different perspectives
- Trend convergence and divergence
- Confidence levels and consensus

Uses LLM to generate high-level insights from disparate data points.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from llm_service import LLMService, PromptTemplates

logger = logging.getLogger(__name__)


@dataclass
class MetaTrend:
    """Represents a meta-trend identified across multiple reports"""
    theme: str
    description: str
    sources: List[str]
    confidence: str  # "high", "medium", "low"
    supporting_evidence: List[str]


@dataclass
class SynthesisResult:
    """Complete synthesis analysis result"""
    query: str
    total_sources: int
    unique_sources: List[str]
    meta_trends: List[MetaTrend]
    consensus_themes: List[str]
    contradictions: List[Dict[str, Any]]
    coverage_analysis: Dict[str, Any]
    synthesis_summary: str


class TrendSynthesizer:
    """
    Analyzes search results to identify cross-report patterns and insights

    Combines rule-based analysis with LLM-powered synthesis for
    comprehensive trend understanding.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize synthesis engine

        Args:
            llm_service: LLM service for intelligent synthesis
        """
        self.llm_service = llm_service

        if llm_service:
            logger.info("Synthesis engine initialized with LLM support")
        else:
            logger.info("Synthesis engine initialized (rule-based only)")

    async def synthesize(
        self,
        query: str,
        results: List[Dict[str, Any]],
        min_sources_for_meta: int = 3
    ) -> SynthesisResult:
        """
        Perform comprehensive synthesis of search results

        Args:
            query: Original search query
            results: List of search results (dicts with content, source, etc.)
            min_sources_for_meta: Minimum sources needed to identify meta-trend

        Returns:
            SynthesisResult with all synthesis analysis
        """
        # Basic analysis
        source_analysis = self._analyze_sources(results)

        # Identify meta-trends
        meta_trends = []
        if self.llm_service and len(source_analysis["unique_sources"]) >= min_sources_for_meta:
            meta_trends = await self._identify_meta_trends_llm(query, results)
        else:
            # Fallback to rule-based meta-trend detection
            meta_trends = self._identify_meta_trends_rules(results, min_sources_for_meta)

        # Identify consensus and contradictions
        consensus_themes = self._identify_consensus(results)
        contradictions = self._identify_contradictions(results)

        # Generate synthesis summary
        synthesis_summary = await self._generate_summary(
            query, results, meta_trends
        ) if self.llm_service else self._generate_summary_rules(results, meta_trends)

        return SynthesisResult(
            query=query,
            total_sources=len(results),
            unique_sources=source_analysis["unique_sources"],
            meta_trends=meta_trends,
            consensus_themes=consensus_themes,
            contradictions=contradictions,
            coverage_analysis=source_analysis["coverage"],
            synthesis_summary=synthesis_summary
        )

    def _analyze_sources(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze source distribution and coverage"""
        source_counts = Counter(r.get("source", "Unknown") for r in results)

        # Calculate coverage metrics
        unique_sources = list(source_counts.keys())
        avg_results_per_source = len(results) / len(unique_sources) if unique_sources else 0

        # Identify dominant sources (more than 20% of results)
        dominant_threshold = len(results) * 0.2
        dominant_sources = [
            source for source, count in source_counts.items()
            if count > dominant_threshold
        ]

        return {
            "unique_sources": unique_sources,
            "source_counts": dict(source_counts),
            "coverage": {
                "unique_report_count": len(unique_sources),
                "avg_results_per_source": round(avg_results_per_source, 2),
                "dominant_sources": dominant_sources,
                "coverage_quality": self._assess_coverage_quality(len(unique_sources))
            }
        }

    def _assess_coverage_quality(self, unique_sources: int) -> str:
        """Assess quality of source coverage"""
        if unique_sources >= 5:
            return "excellent"
        elif unique_sources >= 3:
            return "good"
        elif unique_sources >= 2:
            return "moderate"
        else:
            return "limited"

    async def _identify_meta_trends_llm(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[MetaTrend]:
        """Use LLM to identify meta-trends across reports"""
        try:
            prompt = PromptTemplates.synthesize_trends(results, query)

            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt=(
                    "You are an expert trend analyst specializing in "
                    "cross-report synthesis and meta-trend identification."
                ),
                max_tokens=1500,
                temperature=0.3
            )

            # Parse LLM response
            synthesis_data = json.loads(response.content)

            # Convert to MetaTrend objects
            meta_trends = []

            if "meta_trends" in synthesis_data:
                for trend_data in synthesis_data["meta_trends"]:
                    meta_trends.append(MetaTrend(
                        theme=trend_data.get("theme", ""),
                        description=trend_data.get("description", ""),
                        sources=trend_data.get("sources", []),
                        confidence=trend_data.get("confidence", "medium"),
                        supporting_evidence=trend_data.get("evidence", [])
                    ))

            logger.info(f"LLM identified {len(meta_trends)} meta-trends")
            return meta_trends

        except Exception as e:
            logger.error(f"LLM meta-trend identification failed: {e}")
            # Fallback to rule-based
            return self._identify_meta_trends_rules(results, min_sources=3)

    def _identify_meta_trends_rules(
        self,
        results: List[Dict[str, Any]],
        min_sources: int = 3
    ) -> List[MetaTrend]:
        """Rule-based meta-trend detection using keyword co-occurrence"""
        # Group results by source
        by_source = defaultdict(list)
        for result in results:
            source = result.get("source", "Unknown")
            by_source[source].append(result.get("content", ""))

        # Extract common themes (simplified - looks for repeated phrases)
        # This is a basic implementation - LLM version is much better
        meta_trends = []

        if len(by_source) >= min_sources:
            meta_trends.append(MetaTrend(
                theme="Cross-Report Pattern Detected",
                description=f"Information found across {len(by_source)} different sources",
                sources=list(by_source.keys()),
                confidence="medium",
                supporting_evidence=[
                    f"Source '{source}' contains {len(contents)} relevant excerpts"
                    for source, contents in list(by_source.items())[:3]
                ]
            ))

        return meta_trends

    def _identify_consensus(self, results: List[Dict[str, Any]]) -> List[str]:
        """Identify themes that appear consistently across sources"""
        # Group by source
        sources = defaultdict(list)
        for result in results:
            sources[result.get("source", "Unknown")].append(
                result.get("content", "").lower()
            )

        # Look for common keywords across multiple sources
        # (Simplified - real implementation would use more sophisticated NLP)
        consensus_themes = []

        # If we have results from 3+ sources, there's potential consensus
        if len(sources) >= 3:
            consensus_themes.append(
                f"Consistent information found across {len(sources)} reports"
            )

        return consensus_themes

    def _identify_contradictions(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify potential contradictions between sources"""
        # This is a placeholder for contradiction detection
        # Real implementation would use semantic similarity and opposition detection
        contradictions = []

        # Check for explicit contradictory language
        contradiction_signals = [
            "however", "but", "despite", "contrary", "although",
            "on the other hand", "in contrast", "different from"
        ]

        for result in results:
            content = result.get("content", "").lower()
            if any(signal in content for signal in contradiction_signals):
                contradictions.append({
                    "source": result.get("source"),
                    "content_preview": result.get("content", "")[:200],
                    "type": "potential_contradiction",
                    "confidence": "low"
                })

        return contradictions[:3]  # Limit to top 3

    async def _generate_summary(
        self,
        query: str,
        results: List[Dict[str, Any]],
        meta_trends: List[MetaTrend]
    ) -> str:
        """Generate synthesis summary using LLM"""
        try:
            # Prepare context
            meta_trends_text = "\n".join([
                f"- {mt.theme}: {mt.description} (Sources: {', '.join(mt.sources[:3])})"
                for mt in meta_trends
            ])

            prompt = f"""Synthesize these trend insights into a brief executive summary.

Query: "{query}"

Meta-Trends Identified:
{meta_trends_text if meta_trends_text else "No clear meta-trends identified"}

Number of sources analyzed: {len(set(r.get('source') for r in results))}
Total insights: {len(results)}

Provide a 2-3 sentence synthesis highlighting:
1. The most significant finding
2. Level of consensus across sources
3. Key implication or recommendation"""

            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a concise trend analyst providing executive summaries.",
                max_tokens=300,
                temperature=0.5
            )

            return response.content

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return self._generate_summary_rules(results, meta_trends)

    def _generate_summary_rules(
        self,
        results: List[Dict[str, Any]],
        meta_trends: List[MetaTrend]
    ) -> str:
        """Generate basic summary without LLM"""
        unique_sources = len(set(r.get("source") for r in results))

        summary = (
            f"Analysis of {len(results)} insights from {unique_sources} trend reports. "
        )

        if meta_trends:
            summary += (
                f"Identified {len(meta_trends)} meta-trend(s) appearing across "
                f"multiple sources, indicating strong market signals. "
            )
        else:
            summary += "Results show diverse perspectives without clear consensus. "

        if unique_sources >= 5:
            summary += "High-quality coverage provides robust insights."
        elif unique_sources >= 3:
            summary += "Good coverage across multiple authoritative sources."
        else:
            summary += "Limited source coverage - consider broader research."

        return summary

    def format_for_display(self, synthesis: SynthesisResult) -> Dict[str, Any]:
        """Format synthesis result for API response"""
        return {
            "query": synthesis.query,
            "summary": synthesis.synthesis_summary,
            "meta_analysis": {
                "total_sources": synthesis.total_sources,
                "unique_reports": len(synthesis.unique_sources),
                "coverage_quality": synthesis.coverage_analysis.get("coverage_quality"),
                "meta_trends_count": len(synthesis.meta_trends)
            },
            "meta_trends": [
                {
                    "theme": mt.theme,
                    "description": mt.description,
                    "source_count": len(mt.sources),
                    "sources": mt.sources,
                    "confidence": mt.confidence
                }
                for mt in synthesis.meta_trends
            ],
            "consensus_themes": synthesis.consensus_themes,
            "contradictions_count": len(synthesis.contradictions),
            "contradictions": synthesis.contradictions[:3],  # Limit display
            "source_distribution": synthesis.coverage_analysis.get("source_counts", {})
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    from llm_service import get_llm_service

    async def test_synthesis():
        """Test synthesis engine"""
        logging.basicConfig(level=logging.INFO)

        # Mock search results
        test_results = [
            {
                "content": "AI-powered personalization is transforming customer experiences across retail",
                "source": "Forrester_2025_Customer_Trends.pdf",
                "relevance_score": 0.95
            },
            {
                "content": "Machine learning enables real-time personalization at scale for e-commerce",
                "source": "McKinsey_Digital_Commerce_Report.pdf",
                "relevance_score": 0.92
            },
            {
                "content": "Retailers investing in AI personalization see 30% increase in conversion rates",
                "source": "Gartner_Retail_Technology_2025.pdf",
                "relevance_score": 0.88
            },
            {
                "content": "However, privacy concerns around AI personalization are growing among consumers",
                "source": "Deloitte_Consumer_Privacy_Study.pdf",
                "relevance_score": 0.85
            }
        ]

        # Test with LLM
        llm = get_llm_service()
        synthesizer = TrendSynthesizer(llm_service=llm)

        result = await synthesizer.synthesize(
            query="AI personalization in retail",
            results=test_results
        )

        print("\n" + "=" * 60)
        print("SYNTHESIS RESULT")
        print("=" * 60)
        print(f"\nQuery: {result.query}")
        print(f"Sources Analyzed: {result.total_sources} from {len(result.unique_sources)} reports")
        print(f"\nSummary:\n{result.synthesis_summary}")
        print(f"\nMeta-Trends Found: {len(result.meta_trends)}")

        for mt in result.meta_trends:
            print(f"\n  - {mt.theme}")
            print(f"    {mt.description}")
            print(f"    Confidence: {mt.confidence}")
            print(f"    Sources: {', '.join(mt.sources[:3])}")

        print("\n" + "=" * 60)

    asyncio.run(test_synthesis())
