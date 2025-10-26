"""
Trend Categorization System

Automatically categorizes trend report content into predefined categories:
- Consumer & Culture
- Technology & Innovation
- Marketing & Advertising
- Business & Industry
- Customer Experience

Supports both LLM-based and rule-based categorization.
"""

import re
import logging
from typing import Optional, Dict, List
from enum import Enum
from collections import Counter
from llm_service import LLMService, PromptTemplates

logger = logging.getLogger(__name__)


class TrendCategory(str, Enum):
    """Predefined trend categories"""
    CONSUMER_CULTURE = "Consumer & Culture"
    TECHNOLOGY = "Technology & Innovation"
    MARKETING = "Marketing & Advertising"
    BUSINESS = "Business & Industry"
    CUSTOMER_EXPERIENCE = "Customer Experience"
    GENERAL = "General"  # Fallback category


class Categorizer:
    """
    Trend categorization engine with multiple strategies

    Supports:
    - LLM-based categorization (accurate but slower, costs money)
    - Rule-based categorization (fast but less accurate)
    - Hybrid approach (rule-based with LLM fallback)
    """

    # Keywords for rule-based categorization
    CATEGORY_KEYWORDS = {
        TrendCategory.CONSUMER_CULTURE: [
            "consumer", "generation", "gen z", "millennials", "gen alpha",
            "lifestyle", "cultural", "behavior", "demographics", "psychographics",
            "values", "beliefs", "social movements", "entertainment", "media consumption",
            "wellness", "health trends", "fashion", "food trends", "travel"
        ],
        TrendCategory.TECHNOLOGY: [
            "ai", "artificial intelligence", "machine learning", "automation",
            "ar", "vr", "augmented reality", "virtual reality", "metaverse",
            "blockchain", "web3", "cryptocurrency", "nft",
            "cloud", "saas", "platform", "api", "integration",
            "innovation", "digital transformation", "tech stack", "emerging technology"
        ],
        TrendCategory.MARKETING: [
            "marketing", "advertising", "campaign", "brand", "branding",
            "social media", "content", "influencer", "creator economy",
            "seo", "sem", "paid media", "organic", "engagement",
            "conversion", "funnel", "performance marketing", "attribution",
            "personalization", "targeting", "segmentation", "messaging"
        ],
        TrendCategory.BUSINESS: [
            "business", "strategy", "revenue", "growth", "profitability",
            "digital transformation", "sustainability", "esg", "governance",
            "e-commerce", "retail", "b2b", "enterprise", "startup",
            "investment", "funding", "market", "competition", "industry"
        ],
        TrendCategory.CUSTOMER_EXPERIENCE: [
            "customer experience", "cx", "customer service", "support",
            "personalization", "omnichannel", "journey", "touchpoint",
            "satisfaction", "retention", "loyalty", "churn",
            "user experience", "ux", "usability", "accessibility",
            "customer success", "onboarding", "engagement"
        ]
    }

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        use_llm: bool = False,
        use_hybrid: bool = True
    ):
        """
        Initialize categorizer

        Args:
            llm_service: LLM service for intelligent categorization
            use_llm: Use LLM for all categorizations (expensive but accurate)
            use_hybrid: Use rules first, LLM for uncertain cases (balanced)
        """
        self.llm_service = llm_service
        self.use_llm = use_llm and llm_service is not None
        self.use_hybrid = use_hybrid and llm_service is not None

        if self.use_llm:
            logger.info("Categorizer: LLM-based mode enabled")
        elif self.use_hybrid:
            logger.info("Categorizer: Hybrid mode (rule-based + LLM fallback)")
        else:
            logger.info("Categorizer: Rule-based mode only")

    async def categorize(self, content: str, filename: Optional[str] = None) -> TrendCategory:
        """
        Categorize content into a trend category

        Args:
            content: Text content to categorize
            filename: Optional filename for context

        Returns:
            TrendCategory enum value
        """
        # Strategy 1: Pure LLM-based
        if self.use_llm:
            return await self._categorize_with_llm(content)

        # Strategy 2: Rule-based
        rule_based_category, confidence = self._categorize_with_rules(content, filename)

        # Strategy 3: Hybrid (rules with LLM fallback for low confidence)
        if self.use_hybrid and confidence < 0.5:
            logger.debug(f"Low confidence ({confidence:.2f}), using LLM fallback")
            return await self._categorize_with_llm(content)

        return rule_based_category

    def _categorize_with_rules(
        self,
        content: str,
        filename: Optional[str] = None
    ) -> tuple[TrendCategory, float]:
        """
        Rule-based categorization using keyword matching

        Args:
            content: Text to categorize
            filename: Optional filename for additional context

        Returns:
            Tuple of (category, confidence_score)
        """
        # Normalize content
        text = content.lower()
        if filename:
            text += " " + filename.lower()

        # Count keyword matches for each category
        category_scores = {}

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = 0
            matched_keywords = []

            for keyword in keywords:
                # Use word boundaries for better matching
                pattern = r'\b' + re.escape(keyword) + r'\b'
                matches = len(re.findall(pattern, text, re.IGNORECASE))

                if matches > 0:
                    score += matches
                    matched_keywords.append(keyword)

            category_scores[category] = {
                "score": score,
                "matched_keywords": matched_keywords
            }

        # Find category with highest score
        if not any(cat["score"] > 0 for cat in category_scores.values()):
            return TrendCategory.GENERAL, 0.0

        best_category = max(category_scores.items(), key=lambda x: x[1]["score"])
        category = best_category[0]
        score = best_category[1]["score"]

        # Calculate confidence (normalized by content length and number of categories)
        total_score = sum(cat["score"] for cat in category_scores.values())
        confidence = score / total_score if total_score > 0 else 0.0

        logger.debug(
            f"Rule-based: {category.value} "
            f"(confidence: {confidence:.2f}, matches: {score})"
        )

        return category, confidence

    async def _categorize_with_llm(self, content: str) -> TrendCategory:
        """
        LLM-based categorization for high accuracy

        Args:
            content: Text to categorize

        Returns:
            TrendCategory enum value
        """
        try:
            prompt = PromptTemplates.categorize_trend(content)

            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a precise trend categorization system.",
                max_tokens=20,
                temperature=0.0  # Deterministic output
            )

            # Parse response and map to category
            category_text = response.content.strip()

            # Map response to enum
            for category in TrendCategory:
                if category.value.lower() in category_text.lower():
                    logger.debug(f"LLM categorized as: {category.value}")
                    return category

            # Fallback if no match
            logger.warning(f"LLM returned unexpected category: {category_text}")
            return TrendCategory.GENERAL

        except Exception as e:
            logger.error(f"LLM categorization failed: {e}")
            # Fallback to rule-based
            category, _ = self._categorize_with_rules(content)
            return category

    def categorize_batch_sync(
        self,
        items: List[Dict[str, str]]
    ) -> List[TrendCategory]:
        """
        Synchronous batch categorization (rule-based only)

        Useful for processing large batches without LLM costs.

        Args:
            items: List of dicts with 'content' and optional 'filename'

        Returns:
            List of TrendCategory values
        """
        results = []

        for item in items:
            category, _ = self._categorize_with_rules(
                content=item.get("content", ""),
                filename=item.get("filename")
            )
            results.append(category)

        return results

    def get_category_distribution(
        self,
        categories: List[TrendCategory]
    ) -> Dict[str, int]:
        """
        Get distribution of categories

        Args:
            categories: List of categorized items

        Returns:
            Dict mapping category names to counts
        """
        counter = Counter(cat.value for cat in categories)
        return dict(counter)


# Filename-based category hints (for report-level categorization)
REPORT_CATEGORY_HINTS = {
    # Technology & Innovation
    "ai": TrendCategory.TECHNOLOGY,
    "tech": TrendCategory.TECHNOLOGY,
    "digital": TrendCategory.TECHNOLOGY,
    "innovation": TrendCategory.TECHNOLOGY,
    "automation": TrendCategory.TECHNOLOGY,

    # Marketing & Advertising
    "marketing": TrendCategory.MARKETING,
    "advertising": TrendCategory.MARKETING,
    "social": TrendCategory.MARKETING,
    "content": TrendCategory.MARKETING,
    "media": TrendCategory.MARKETING,

    # Consumer & Culture
    "consumer": TrendCategory.CONSUMER_CULTURE,
    "generation": TrendCategory.CONSUMER_CULTURE,
    "gen z": TrendCategory.CONSUMER_CULTURE,
    "culture": TrendCategory.CONSUMER_CULTURE,
    "lifestyle": TrendCategory.CONSUMER_CULTURE,

    # Business & Industry
    "business": TrendCategory.BUSINESS,
    "industry": TrendCategory.BUSINESS,
    "commerce": TrendCategory.BUSINESS,
    "retail": TrendCategory.BUSINESS,
    "b2b": TrendCategory.BUSINESS,

    # Customer Experience
    "customer": TrendCategory.CUSTOMER_EXPERIENCE,
    "cx": TrendCategory.CUSTOMER_EXPERIENCE,
    "experience": TrendCategory.CUSTOMER_EXPERIENCE,
    "service": TrendCategory.CUSTOMER_EXPERIENCE,
}


def guess_category_from_filename(filename: str) -> Optional[TrendCategory]:
    """
    Guess category from report filename

    Args:
        filename: PDF filename

    Returns:
        TrendCategory if match found, None otherwise
    """
    filename_lower = filename.lower()

    for hint, category in REPORT_CATEGORY_HINTS.items():
        if hint in filename_lower:
            return category

    return None


# Example usage
if __name__ == "__main__":
    import asyncio
    from llm_service import get_llm_service

    async def test_categorization():
        """Test categorization system"""
        logging.basicConfig(level=logging.INFO)

        # Test content
        test_cases = [
            "AI-powered marketing automation is transforming how brands engage with customers",
            "Gen Z consumers are prioritizing sustainability and authentic brand values",
            "Digital transformation initiatives are driving enterprise cloud adoption",
            "Omnichannel customer experience strategies improve retention rates by 30%"
        ]

        # Test rule-based
        print("\n=== Rule-based Categorization ===")
        categorizer = Categorizer(use_llm=False)

        for content in test_cases:
            category, confidence = categorizer._categorize_with_rules(content)
            print(f"{category.value} ({confidence:.2f}): {content[:60]}...")

        # Test LLM-based (if configured)
        llm = get_llm_service()
        if llm:
            print("\n=== LLM-based Categorization ===")
            llm_categorizer = Categorizer(llm_service=llm, use_llm=True)

            for content in test_cases:
                category = await llm_categorizer.categorize(content)
                print(f"{category.value}: {content[:60]}...")

    asyncio.run(test_categorization())
