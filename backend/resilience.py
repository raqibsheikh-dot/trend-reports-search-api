"""
Resilience and Fault Tolerance

Implements production-grade resilience patterns:
- Request timeouts
- Circuit breaker pattern
- Retry logic with exponential backoff
- Graceful degradation
- Health checks

Ensures system stability under load and failure conditions.
"""

import asyncio
import time
import logging
from typing import Callable, Any, Optional, Dict
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failures detected, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 2  # Successes needed to close from half-open
    timeout: int = 60  # Seconds circuit stays open
    half_open_max_calls: int = 3  # Max calls to try in half-open state


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.now)
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """
    Circuit Breaker Pattern Implementation

    Prevents cascading failures by stopping requests to failing services.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker

        Args:
            name: Name of the circuit (for logging)
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()

        logger.info(f"Circuit breaker '{name}' initialized")

    def _should_attempt_call(self) -> bool:
        """Check if call should be attempted based on current state"""
        if self.stats.state == CircuitState.CLOSED:
            return True

        if self.stats.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.stats.last_failure_time:
                time_since_failure = (datetime.now() - self.stats.last_failure_time).total_seconds()
                if time_since_failure >= self.config.timeout:
                    self._transition_to_half_open()
                    return True
            return False

        if self.stats.state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self.stats.total_calls < self.config.half_open_max_calls

        return False

    def _transition_to_half_open(self):
        """Transition circuit to half-open state"""
        logger.info(f"Circuit breaker '{self.name}': OPEN -> HALF_OPEN")
        self.stats.state = CircuitState.HALF_OPEN
        self.stats.success_count = 0
        self.stats.failure_count = 0
        self.stats.last_state_change = datetime.now()

    def _transition_to_open(self):
        """Transition circuit to open state"""
        logger.warning(f"Circuit breaker '{self.name}': {self.stats.state} -> OPEN (failures: {self.stats.failure_count})")
        self.stats.state = CircuitState.OPEN
        self.stats.last_failure_time = datetime.now()
        self.stats.last_state_change = datetime.now()

    def _transition_to_closed(self):
        """Transition circuit to closed state"""
        logger.info(f"Circuit breaker '{self.name}': HALF_OPEN -> CLOSED (successes: {self.stats.success_count})")
        self.stats.state = CircuitState.CLOSED
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self.stats.last_state_change = datetime.now()

    def record_success(self):
        """Record successful call"""
        self.stats.total_calls += 1
        self.stats.total_successes += 1

        if self.stats.state == CircuitState.HALF_OPEN:
            self.stats.success_count += 1
            if self.stats.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.stats.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.stats.failure_count = 0

    def record_failure(self):
        """Record failed call"""
        self.stats.total_calls += 1
        self.stats.total_failures += 1
        self.stats.failure_count += 1
        self.stats.last_failure_time = datetime.now()

        if self.stats.state == CircuitState.HALF_OPEN:
            # Any failure in half-open goes back to open
            self._transition_to_open()
        elif self.stats.state == CircuitState.CLOSED:
            if self.stats.failure_count >= self.config.failure_threshold:
                self._transition_to_open()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection

        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        if not self._should_attempt_call():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Service unavailable (failures: {self.stats.total_failures})"
            )

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.stats.state,
            "total_calls": self.stats.total_calls,
            "total_successes": self.stats.total_successes,
            "total_failures": self.stats.total_failures,
            "current_failure_count": self.stats.failure_count,
            "last_state_change": self.stats.last_state_change.isoformat(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "timeout": self.config.timeout
            }
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class TimeoutError(Exception):
    """Raised when operation times out"""
    pass


async def with_timeout(coro, timeout_seconds: int, operation_name: str = "Operation"):
    """
    Execute coroutine with timeout

    Args:
        coro: Coroutine to execute
        timeout_seconds: Timeout in seconds
        operation_name: Name for error messages

    Returns:
        Coroutine result

    Raises:
        TimeoutError: If operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"{operation_name} timed out after {timeout_seconds}s")
        raise TimeoutError(f"{operation_name} timed out after {timeout_seconds} seconds")


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """
    Retry function with exponential backoff

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff
        exceptions: Tuple of exceptions to retry on
        *args, **kwargs: Arguments to pass to function

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"All {max_retries} retries failed for {func.__name__}: {e}")
                raise

            # Calculate backoff delay
            delay = min(initial_delay * (exponential_base ** attempt), max_delay)
            # Add jitter (random variation)
            jitter = delay * 0.1 * (2 * (time.time() % 1) - 1)
            delay = delay + jitter

            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                f"Retrying in {delay:.2f}s..."
            )

            await asyncio.sleep(delay)

    # Should never reach here, but just in case
    raise last_exception


def timeout(seconds: int):
    """
    Decorator to add timeout to async functions

    Usage:
        @timeout(30)
        async def my_function():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_timeout(
                func(*args, **kwargs),
                timeout_seconds=seconds,
                operation_name=func.__name__
            )
        return wrapper
    return decorator


def circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """
    Decorator to add circuit breaker to async functions

    Usage:
        @circuit_breaker("my_service")
        async def call_external_service():
            ...
    """
    breaker = CircuitBreaker(name, config)

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        # Attach circuit breaker to function for stats access
        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator


# Global circuit breakers for different services
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get or create circuit breaker by name"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def get_all_circuit_breaker_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all circuit breakers"""
    return {
        name: breaker.get_stats()
        for name, breaker in _circuit_breakers.items()
    }


# Health check utilities
class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """Health check result"""
    status: HealthStatus
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class HealthChecker:
    """
    System health checker

    Aggregates health from multiple components.
    """

    def __init__(self):
        self.checks: Dict[str, Callable] = {}

    def register_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.checks[name] = check_func
        logger.info(f"Registered health check: {name}")

    async def check_health(self) -> HealthCheck:
        """
        Run all health checks

        Returns:
            Aggregated health status
        """
        results = {}
        overall_status = HealthStatus.HEALTHY

        for name, check_func in self.checks.items():
            try:
                # Run check with timeout
                result = await with_timeout(
                    check_func(),
                    timeout_seconds=5,
                    operation_name=f"Health check: {name}"
                )
                results[name] = {"status": "ok", "result": result}
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e}")
                results[name] = {"status": "error", "error": str(e)}
                overall_status = HealthStatus.UNHEALTHY

        # Check circuit breakers
        breaker_stats = get_all_circuit_breaker_stats()
        open_circuits = [
            name for name, stats in breaker_stats.items()
            if stats["state"] == CircuitState.OPEN
        ]

        if open_circuits:
            results["circuit_breakers"] = {
                "status": "warning",
                "open_circuits": open_circuits
            }
            if overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        return HealthCheck(
            status=overall_status,
            details=results
        )


# Global health checker
_health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """Get global health checker"""
    return _health_checker


# Example usage and testing
if __name__ == "__main__":
    import random

    async def test_circuit_breaker():
        """Test circuit breaker functionality"""

        # Simulated flaky service
        call_count = 0

        async def flaky_service():
            nonlocal call_count
            call_count += 1

            # Fail first 5 calls, then succeed
            if call_count <= 5:
                raise Exception(f"Service failure #{call_count}")

            return "Success"

        # Create circuit breaker
        breaker = CircuitBreaker("test_service", CircuitBreakerConfig(
            failure_threshold=3,
            timeout=5,
            success_threshold=2
        ))

        print("Testing circuit breaker pattern...")

        # Make calls
        for i in range(15):
            try:
                result = await breaker.call(flaky_service)
                print(f"Call {i+1}: {result} - Circuit: {breaker.stats.state}")
            except CircuitBreakerOpenError as e:
                print(f"Call {i+1}: Circuit OPEN - {e}")
            except Exception as e:
                print(f"Call {i+1}: Failed - {e} - Circuit: {breaker.stats.state}")

            await asyncio.sleep(0.5)

        print(f"\nFinal stats: {breaker.get_stats()}")

    async def test_retry():
        """Test retry with backoff"""

        attempt_count = 0

        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count < 3:
                raise Exception(f"Temporary failure #{attempt_count}")

            return "Success after retries"

        print("\nTesting retry with exponential backoff...")

        result = await retry_with_backoff(
            flaky_operation,
            max_retries=3,
            initial_delay=0.5,
            exponential_base=2
        )

        print(f"Result: {result} (took {attempt_count} attempts)")

    async def test_timeout():
        """Test timeout functionality"""

        async def slow_operation():
            await asyncio.sleep(5)
            return "Completed"

        print("\nTesting timeout (should fail)...")

        try:
            result = await with_timeout(slow_operation(), 2, "Slow operation")
            print(f"Result: {result}")
        except TimeoutError as e:
            print(f"Timeout caught: {e}")

    async def main():
        """Run all tests"""
        await test_circuit_breaker()
        await test_retry()
        await test_timeout()

    # Run tests
    asyncio.run(main())
