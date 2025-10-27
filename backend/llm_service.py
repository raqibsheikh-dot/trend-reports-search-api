"""
LLM Service Abstraction Layer

Unified interface for working with Large Language Models (Claude, GPT).
Provides error handling, retries, cost tracking, and prompt templates.

Supports:
- Anthropic Claude (Claude 3.5 Sonnet, Claude 3 Opus, etc.)
- OpenAI GPT (GPT-4, GPT-4 Turbo, GPT-3.5 Turbo)
- Automatic retries with exponential backoff
- Cost tracking and budget limits
- Prompt templating
- Response caching

Usage:
    from llm_service import get_llm_service

    llm = get_llm_service()
    response = await llm.generate(
        prompt="Analyze this trend data...",
        system_prompt="You are a trend analyst.",
        max_tokens=1000
    )
"""

import os
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class LLMUsage:
    """Track LLM API usage and costs"""
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    usage: LLMUsage
    model: str
    provider: str
    cached: bool = False


class CostTracker:
    """Track and limit LLM costs"""

    # Approximate pricing (as of January 2024)
    PRICING = {
        "anthropic": {
            "claude-3-5-sonnet-20241022": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
            "claude-3-opus-20240229": {"input": 15.0 / 1_000_000, "output": 75.0 / 1_000_000},
            "claude-3-sonnet-20240229": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
            "claude-3-haiku-20240307": {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000},
        },
        "openai": {
            "gpt-4-turbo-preview": {"input": 10.0 / 1_000_000, "output": 30.0 / 1_000_000},
            "gpt-4": {"input": 30.0 / 1_000_000, "output": 60.0 / 1_000_000},
            "gpt-3.5-turbo": {"input": 0.5 / 1_000_000, "output": 1.5 / 1_000_000},
        }
    }

    def __init__(self, monthly_budget_usd: float = 50.0):
        """
        Initialize cost tracker

        Args:
            monthly_budget_usd: Monthly budget limit in USD
        """
        self.monthly_budget = monthly_budget_usd
        self.total_cost = 0.0
        self.usage_history: List[LLMUsage] = []

    def calculate_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate cost for a request"""
        pricing = self.PRICING.get(provider, {}).get(model)

        if not pricing:
            logger.warning(f"Unknown pricing for {provider}/{model}, using fallback")
            # Fallback to Claude 3 Haiku pricing
            pricing = {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000}

        cost = (prompt_tokens * pricing["input"]) + (completion_tokens * pricing["output"])
        return cost

    def track_usage(self, usage: LLMUsage):
        """Track usage and update total cost"""
        self.usage_history.append(usage)
        self.total_cost += usage.estimated_cost_usd

        logger.info(
            f"LLM usage: {usage.provider}/{usage.model} "
            f"- {usage.total_tokens} tokens "
            f"- ${usage.estimated_cost_usd:.4f}"
        )

    def check_budget(self) -> bool:
        """Check if budget limit has been exceeded"""
        if self.total_cost >= self.monthly_budget:
            logger.warning(
                f"⚠️  Budget limit reached: ${self.total_cost:.2f} / ${self.monthly_budget:.2f}"
            )
            return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_cost_usd": round(self.total_cost, 4),
            "budget_usd": self.monthly_budget,
            "budget_remaining_usd": round(self.monthly_budget - self.total_cost, 4),
            "budget_used_percent": round((self.total_cost / self.monthly_budget) * 100, 2),
            "total_requests": len(self.usage_history),
            "total_tokens": sum(u.total_tokens for u in self.usage_history),
        }


class LLMService:
    """
    Unified LLM service supporting multiple providers

    Handles API calls, retries, error handling, and cost tracking
    """

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        cost_tracker: Optional[CostTracker] = None,
        max_connections: int = 10,
        max_keepalive_connections: int = 5
    ):
        """
        Initialize LLM service with HTTP connection pooling

        Args:
            provider: LLM provider to use
            model: Model name (uses defaults if not specified)
            api_key: API key (reads from env if not provided)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            cost_tracker: Cost tracking instance
            max_connections: Maximum HTTP connections in pool (default: 10)
            max_keepalive_connections: Maximum keepalive connections (default: 5)
        """
        self.provider = provider
        self.timeout = timeout
        self.max_retries = max_retries
        self.cost_tracker = cost_tracker or CostTracker()
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections

        # Set up provider-specific client
        if provider == LLMProvider.ANTHROPIC:
            self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            self._setup_anthropic()

        elif provider == LLMProvider.OPENAI:
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self._setup_openai()

        else:
            raise ValueError(f"Unsupported provider: {provider}")

        if not self.api_key:
            raise ValueError(f"API key not found for {provider}")

        logger.info(f"✓ LLM service initialized: {provider.value}/{self.model}")

    def _setup_anthropic(self):
        """Initialize Anthropic client with HTTP connection pooling"""
        try:
            from anthropic import AsyncAnthropic
            import httpx

            # Create HTTP client with connection pooling
            http_client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=self.max_connections,
                    max_keepalive_connections=self.max_keepalive_connections,
                    keepalive_expiry=30.0  # Keep connections alive for 30 seconds
                ),
                timeout=self.timeout
            )

            self.client = AsyncAnthropic(
                api_key=self.api_key,
                timeout=self.timeout,
                http_client=http_client
            )
            logger.info(f"✓ Anthropic client initialized with connection pool (max: {self.max_connections})")
        except ImportError as e:
            logger.error(f"Required package not installed: {e}")
            logger.error("Install with: pip install anthropic httpx")
            raise

    def _setup_openai(self):
        """Initialize OpenAI client with HTTP connection pooling"""
        try:
            from openai import AsyncOpenAI
            import httpx

            # Create HTTP client with connection pooling
            http_client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=self.max_connections,
                    max_keepalive_connections=self.max_keepalive_connections,
                    keepalive_expiry=30.0  # Keep connections alive for 30 seconds
                ),
                timeout=self.timeout
            )

            self.client = AsyncOpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                http_client=http_client
            )
            logger.info(f"✓ OpenAI client initialized with connection pool (max: {self.max_connections})")
        except ImportError as e:
            logger.error(f"Required package not installed: {e}")
            logger.error("Install with: pip install openai httpx")
            raise

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text completion

        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt for context
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with generated text and metadata
        """
        # Check budget before making request
        if not self.cost_tracker.check_budget():
            raise Exception(f"Monthly budget limit of ${self.cost_tracker.monthly_budget} reached")

        # Retry with exponential backoff
        for attempt in range(self.max_retries):
            try:
                if self.provider == LLMProvider.ANTHROPIC:
                    response = await self._generate_anthropic(
                        prompt, system_prompt, max_tokens, temperature, **kwargs
                    )
                elif self.provider == LLMProvider.OPENAI:
                    response = await self._generate_openai(
                        prompt, system_prompt, max_tokens, temperature, **kwargs
                    )

                # Track usage
                self.cost_tracker.track_usage(response.usage)

                return response

            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"LLM generation failed after {self.max_retries} attempts: {e}")
                    raise

                wait_time = (2 ** attempt) + (time.time() % 1)  # Exponential backoff with jitter
                logger.warning(f"LLM request failed (attempt {attempt + 1}), retrying in {wait_time:.1f}s: {e}")
                await asyncio.sleep(wait_time)

    async def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """Generate using Anthropic Claude"""
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt or "",
            messages=messages,
            **kwargs
        )

        # Extract usage
        usage = LLMUsage(
            provider="anthropic",
            model=self.model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            estimated_cost_usd=self.cost_tracker.calculate_cost(
                "anthropic",
                self.model,
                response.usage.input_tokens,
                response.usage.output_tokens
            )
        )

        return LLMResponse(
            content=response.content[0].text,
            usage=usage,
            model=self.model,
            provider="anthropic"
        )

    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """Generate using OpenAI GPT"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
            **kwargs
        )

        # Extract usage
        usage = LLMUsage(
            provider="openai",
            model=self.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            estimated_cost_usd=self.cost_tracker.calculate_cost(
                "openai",
                self.model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            usage=usage,
            model=self.model,
            provider="openai"
        )

    def get_cost_stats(self) -> Dict[str, Any]:
        """Get cost tracking statistics"""
        return self.cost_tracker.get_stats()


# Prompt templates for common tasks
class PromptTemplates:
    """Pre-defined prompt templates for trend analysis"""

    @staticmethod
    def categorize_trend(content: str) -> str:
        """Template for trend categorization"""
        return f"""Classify this trend report excerpt into ONE category:
- Consumer & Culture
- Technology & Innovation
- Marketing & Advertising
- Business & Industry
- Customer Experience

Excerpt: {content[:500]}

Return ONLY the category name, nothing else."""

    @staticmethod
    def synthesize_trends(results: List[dict], query: str) -> str:
        """Template for cross-report synthesis"""
        results_text = "\n\n".join([
            f"Source: {r['source']}\nContent: {r['content'][:300]}..."
            for r in results[:5]
        ])

        return f"""Analyze these search results and identify meta-trends.

Query: "{query}"

Results from multiple trend reports:
{results_text}

Provide:
1. Common themes across reports
2. Contradictions or different perspectives
3. Emerging meta-trends
4. Confidence level (high/medium/low)

Format as JSON."""

    @staticmethod
    def structure_response(results: List[dict], query: str) -> str:
        """Template for structured response generation"""
        results_text = "\n\n".join([
            f"[{i+1}] {r['content'][:200]}... (Source: {r['source']})"
            for i, r in enumerate(results[:5])
        ])

        return f"""Based on these trend report excerpts, create a structured analysis.

Query: "{query}"

Search Results:
{results_text}

Provide a JSON response with:
{{
  "relevant_trends": ["trend1", "trend2", "trend3"],
  "context": "Why these trends matter...",
  "data_points": [{{"statistic": "...", "source": "..."}}],
  "applications": ["practical application 1", "..."],
  "connections": ["how trends connect"],
  "next_steps": ["suggested actions"]
}}"""

    @staticmethod
    def expand_query(query: str) -> str:
        """Template for query expansion"""
        return f"""Generate 3 similar search queries for: "{query}"

Return only the queries, one per line, no numbering or explanation."""


# Factory function
def get_llm_service() -> Optional[LLMService]:
    """
    Create LLM service from environment configuration with HTTP connection pooling

    Environment variables:
        - LLM_PROVIDER: "anthropic" or "openai" (default: anthropic)
        - ANTHROPIC_API_KEY / OPENAI_API_KEY: API keys
        - ANTHROPIC_MODEL / OPENAI_MODEL: Model names
        - LLM_TIMEOUT: Request timeout (default: 30)
        - LLM_BUDGET_LIMIT: Monthly budget in USD (default: 50.0)
        - LLM_MAX_CONNECTIONS: Max HTTP connections in pool (default: 10)
        - LLM_MAX_KEEPALIVE: Max keepalive connections (default: 5)

    Returns:
        LLMService instance or None if not configured
    """
    provider_name = os.getenv("LLM_PROVIDER", "anthropic").lower()

    try:
        provider = LLMProvider(provider_name)
    except ValueError:
        logger.error(f"Invalid LLM provider: {provider_name}")
        return None

    # Check if API key is configured
    if provider == LLMProvider.ANTHROPIC and not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not configured, LLM features disabled")
        return None

    if provider == LLMProvider.OPENAI and not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not configured, LLM features disabled")
        return None

    timeout = int(os.getenv("LLM_TIMEOUT", "30"))
    budget_limit = float(os.getenv("LLM_BUDGET_LIMIT", "50.0"))
    max_connections = int(os.getenv("LLM_MAX_CONNECTIONS", "10"))
    max_keepalive = int(os.getenv("LLM_MAX_KEEPALIVE", "5"))

    cost_tracker = CostTracker(monthly_budget_usd=budget_limit)

    try:
        return LLMService(
            provider=provider,
            timeout=timeout,
            cost_tracker=cost_tracker,
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive
        )
    except Exception as e:
        logger.error(f"Failed to initialize LLM service: {e}")
        return None


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test_llm():
        """Test LLM service"""
        logging.basicConfig(level=logging.INFO)

        llm = get_llm_service()
        if not llm:
            print("LLM service not configured")
            return

        # Test generation
        response = await llm.generate(
            prompt="What are the top 3 AI trends in marketing for 2025?",
            system_prompt="You are a concise trend analyst.",
            max_tokens=200
        )

        print(f"\n{'='*60}")
        print(f"Response: {response.content}")
        print(f"Model: {response.model}")
        print(f"Tokens: {response.usage.total_tokens}")
        print(f"Cost: ${response.usage.estimated_cost_usd:.4f}")
        print(f"{'='*60}\n")

        # Check cost stats
        stats = llm.get_cost_stats()
        print(f"Cost Stats: {stats}")

    asyncio.run(test_llm())
