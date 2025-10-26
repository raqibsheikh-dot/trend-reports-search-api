"""
Resilience Module Tests

Tests for circuit breakers, retries, timeouts, and health checks.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    TimeoutError as ResilienceTimeoutError,
    with_timeout,
    retry_with_backoff,
    HealthChecker,
    HealthStatus
)


@pytest.mark.unit
class TestCircuitBreaker:
    """Tests for circuit breaker functionality"""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes correctly"""
        breaker = CircuitBreaker("test_service")

        assert breaker.name == "test_service"
        assert breaker.stats.state == CircuitState.CLOSED
        assert breaker.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """Test circuit breaker with successful calls"""
        breaker = CircuitBreaker("test_service")

        async def successful_operation():
            return "success"

        result = await breaker.call(successful_operation)

        assert result == "success"
        assert breaker.stats.total_successes == 1
        assert breaker.stats.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test circuit opens after threshold failures"""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test_service", config)

        async def failing_operation():
            raise Exception("Service error")

        # Trigger failures
        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(failing_operation)

        # Circuit should be open
        assert breaker.stats.state == CircuitState.OPEN
        assert breaker.stats.total_failures == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(self):
        """Test circuit rejects calls when open"""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test_service", config)

        async def failing_operation():
            raise Exception("Service error")

        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_operation)

        # Next call should be rejected
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_operation)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_to_closed(self):
        """Test circuit transitions from half-open to closed on success"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout=0  # Immediate transition to half-open
        )
        breaker = CircuitBreaker("test_service", config)

        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1

            # Fail first 2 calls to open circuit
            if call_count <= 2:
                raise Exception("Failure")

            # Succeed afterwards
            return "success"

        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(flaky_operation)

        assert breaker.stats.state == CircuitState.OPEN

        # Wait for half-open (immediate with timeout=0)
        await asyncio.sleep(0.1)

        # Force transition to half-open manually for testing
        breaker._transition_to_half_open()

        # Successful calls should close the circuit
        for i in range(2):
            result = await breaker.call(flaky_operation)
            assert result == "success"

        assert breaker.stats.state == CircuitState.CLOSED

    def test_circuit_breaker_get_stats(self):
        """Test getting circuit breaker statistics"""
        breaker = CircuitBreaker("test_service")
        stats = breaker.get_stats()

        assert stats["name"] == "test_service"
        assert stats["state"] == CircuitState.CLOSED
        assert "total_calls" in stats
        assert "config" in stats


@pytest.mark.unit
class TestTimeout:
    """Tests for timeout functionality"""

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test operation completes within timeout"""
        async def quick_operation():
            await asyncio.sleep(0.01)
            return "completed"

        result = await with_timeout(quick_operation(), 1, "Quick op")
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_with_timeout_fails(self):
        """Test operation times out"""
        async def slow_operation():
            await asyncio.sleep(2)
            return "completed"

        with pytest.raises(ResilienceTimeoutError):
            await with_timeout(slow_operation(), 0.1, "Slow op")


@pytest.mark.unit
class TestRetryWithBackoff:
    """Tests for retry logic"""

    @pytest.mark.asyncio
    async def test_retry_eventual_success(self):
        """Test retry succeeds after failures"""
        attempt_count = 0

        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count < 3:
                raise Exception("Temporary failure")

            return "success"

        result = await retry_with_backoff(
            flaky_operation,
            max_retries=3,
            initial_delay=0.01,
            exponential_base=2
        )

        assert result == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_all_failures(self):
        """Test retry fails after all attempts"""
        async def always_fails():
            raise Exception("Persistent failure")

        with pytest.raises(Exception, match="Persistent failure"):
            await retry_with_backoff(
                always_fails,
                max_retries=2,
                initial_delay=0.01
            )

    @pytest.mark.asyncio
    async def test_retry_first_success(self):
        """Test operation succeeds on first try (no retries needed)"""
        async def immediate_success():
            return "success"

        result = await retry_with_backoff(
            immediate_success,
            max_retries=3,
            initial_delay=0.01
        )

        assert result == "success"


@pytest.mark.unit
class TestHealthChecker:
    """Tests for health checker"""

    @pytest.mark.asyncio
    async def test_health_checker_all_healthy(self):
        """Test health checker with all components healthy"""
        checker = HealthChecker()

        async def check_db():
            return {"status": "ok", "connections": 10}

        async def check_cache():
            return {"status": "ok", "hits": 100}

        checker.register_check("database", check_db)
        checker.register_check("cache", check_cache)

        result = await checker.check_health()

        assert result.status == HealthStatus.HEALTHY
        assert "database" in result.details
        assert "cache" in result.details

    @pytest.mark.asyncio
    async def test_health_checker_component_failure(self):
        """Test health checker with failing component"""
        checker = HealthChecker()

        async def check_failing():
            raise Exception("Service down")

        checker.register_check("failing_service", check_failing)

        result = await checker.check_health()

        assert result.status == HealthStatus.UNHEALTHY
        assert "failing_service" in result.details
        assert result.details["failing_service"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_checker_timeout(self):
        """Test health check times out for slow checks"""
        checker = HealthChecker()

        async def slow_check():
            await asyncio.sleep(10)
            return {"status": "ok"}

        checker.register_check("slow_service", slow_check)

        result = await checker.check_health()

        # Should timeout and mark as unhealthy
        assert result.status == HealthStatus.UNHEALTHY
        assert "slow_service" in result.details
        assert "error" in result.details["slow_service"]


@pytest.mark.integration
class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with real async operations"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_circuit_breaker_full_cycle(self):
        """Test full circuit breaker lifecycle"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=1  # 1 second timeout
        )
        breaker = CircuitBreaker("integration_test", config)

        call_count = 0

        async def simulated_service():
            nonlocal call_count
            call_count += 1

            # Fail first 5 calls
            if call_count <= 5:
                await asyncio.sleep(0.01)
                raise Exception(f"Service failure #{call_count}")

            # Succeed afterwards
            await asyncio.sleep(0.01)
            return f"Success #{call_count}"

        # 1. Open the circuit (3 failures)
        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(simulated_service)

        assert breaker.stats.state == CircuitState.OPEN

        # 2. Calls rejected while open
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(simulated_service)

        # 3. Wait for timeout to transition to half-open
        await asyncio.sleep(1.1)

        # 4. Force transition for testing
        breaker._transition_to_half_open()
        assert breaker.stats.state == CircuitState.HALF_OPEN

        # 5. Success in half-open closes circuit
        for i in range(2):
            result = await breaker.call(simulated_service)
            assert "Success" in result

        assert breaker.stats.state == CircuitState.CLOSED
