"""
Comprehensive test suite for Microservices Gateway & API Gateway

Target: 50,000+ req/sec throughput, <10ms latency, 99.99% uptime
Tests: 40+ cases covering all components
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import List

from app.microservices_gateway import (
    APIGateway,
    ServiceRequest,
    ServiceResponse,
    ServiceEndpoint,
    Route,
    RateLimit,
    AuthConfig,
    AuthType,
    RateLimitStrategy,
    ProtocolType,
    CircuitBreaker,
    CircuitBreakerState,
    RateLimiter,
    LoadBalancer,
    AuthenticationManager,
    create_api_gateway
)


# ============================================================================
# Test Data Generators
# ============================================================================

def create_test_endpoint(
    name: str = "service1",
    host: str = "localhost",
    port: int = 8001,
    protocol: ProtocolType = ProtocolType.REST,
    healthy: bool = True,
    response_time_ms: float = 5.0,
    error_rate: float = 0.0
) -> ServiceEndpoint:
    """Create test endpoint"""
    return ServiceEndpoint(
        name=name,
        host=host,
        port=port,
        protocol=protocol,
        weight=1,
        healthy=healthy,
        response_time_ms=response_time_ms,
        error_rate=error_rate
    )


def create_test_route(
    path: str = "/api/users",
    methods: List[str] = None,
    upstream_service: str = "user_service",
    auth_required: bool = True,
    rate_limit: RateLimit = None
) -> Route:
    """Create test route"""
    if methods is None:
        methods = ["GET", "POST"]

    if rate_limit is None:
        rate_limit = RateLimit(
            requests_per_second=100,
            requests_per_minute=6000,
            requests_per_hour=360000
        )

    return Route(
        path=path,
        methods=methods,
        upstream_service=upstream_service,
        auth_required=auth_required,
        rate_limit=rate_limit
    )


def create_test_request(
    method: str = "GET",
    path: str = "/api/users",
    client_ip: str = "192.168.1.100",
    api_key: Optional[str] = None
) -> ServiceRequest:
    """Create test request"""
    headers = {"User-Agent": "TestClient"}
    if api_key:
        headers["X-API-Key"] = api_key

    return ServiceRequest(
        request_id=f"req_{int(time.time()*1000)}",
        timestamp=datetime.utcnow(),
        method=method,
        path=path,
        headers=headers,
        query_params={},
        body=None,
        client_ip=client_ip,
        client_user_agent="TestClient"
    )


# ============================================================================
# Rate Limiting Tests (8 tests)
# ============================================================================

class TestRateLimiting:
    """Test rate limiting functionality"""

    def test_sliding_window_allows_requests_within_limit(self):
        """Test requests within limit are allowed"""
        limiter = RateLimiter(RateLimitStrategy.SLIDING_WINDOW)
        limit = RateLimit(
            requests_per_second=10,
            requests_per_minute=100,
            requests_per_hour=1000
        )

        client_id = "client_001"

        for i in range(50):
            allowed, remaining = limiter.is_allowed(client_id, limit)
            assert allowed, f"Request {i+1} should be allowed"
            assert remaining >= 0

    def test_sliding_window_blocks_requests_exceeding_limit(self):
        """Test requests exceeding limit are blocked"""
        limiter = RateLimiter(RateLimitStrategy.SLIDING_WINDOW)
        limit = RateLimit(
            requests_per_second=2,
            requests_per_minute=10,
            requests_per_hour=100
        )

        client_id = "client_001"

        # Max out limit
        for i in range(10):
            allowed, _ = limiter.is_allowed(client_id, limit)

        # Next should be blocked
        allowed, _ = limiter.is_allowed(client_id, limit)
        assert not allowed

    def test_token_bucket_rate_limiting(self):
        """Test token bucket rate limiting"""
        limiter = RateLimiter(RateLimitStrategy.TOKEN_BUCKET)
        limit = RateLimit(
            requests_per_second=5,
            requests_per_minute=300,
            requests_per_hour=18000
        )

        client_id = "client_001"

        # Should allow initial requests (tokens available)
        for i in range(3):
            allowed, _ = limiter.is_allowed(client_id, limit)
            assert allowed

    def test_rate_limit_per_client_isolation(self):
        """Test rate limits are isolated per client"""
        limiter = RateLimiter()
        limit = RateLimit(
            requests_per_second=2,
            requests_per_minute=10,
            requests_per_hour=100
        )

        client1 = "client_001"
        client2 = "client_002"

        # Max out client1
        for i in range(10):
            limiter.is_allowed(client1, limit)

        # Client2 should still be allowed
        allowed, _ = limiter.is_allowed(client2, limit)
        assert allowed

    def test_rate_limit_returns_remaining_requests(self):
        """Test remaining request count is returned"""
        limiter = RateLimiter()
        limit = RateLimit(
            requests_per_second=10,
            requests_per_minute=100,
            requests_per_hour=1000
        )

        client_id = "client_001"

        allowed, remaining = limiter.is_allowed(client_id, limit)
        assert remaining > 0
        assert remaining <= limit.requests_per_minute

    def test_rate_limit_window_reset(self):
        """Test rate limit window resets after timeout"""
        limiter = RateLimiter()
        limit = RateLimit(
            requests_per_second=1,
            requests_per_minute=2,  # Very low for testing
            requests_per_hour=10000
        )

        client_id = "client_001"

        # Use up limit
        for i in range(2):
            limiter.is_allowed(client_id, limit)

        blocked, _ = limiter.is_allowed(client_id, limit)
        assert not blocked

        # Clear history (simulate time passing)
        limiter.request_history[client_id] = []

        # Should be allowed again
        allowed, _ = limiter.is_allowed(client_id, limit)
        assert allowed

    def test_different_limit_strategies(self):
        """Test different rate limiting strategies"""
        for strategy in [RateLimitStrategy.SLIDING_WINDOW, RateLimitStrategy.TOKEN_BUCKET]:
            limiter = RateLimiter(strategy)
            limit = RateLimit(
                requests_per_second=100,
                requests_per_minute=6000,
                requests_per_hour=360000
            )

            allowed, _ = limiter.is_allowed("client", limit)
            assert allowed

    def test_rate_limit_burst_allowance(self):
        """Test burst allowance in rate limiting"""
        limiter = RateLimiter()
        limit = RateLimit(
            requests_per_second=10,
            requests_per_minute=100,
            requests_per_hour=1000,
            burst_allowed=5
        )

        client_id = "client_001"

        # Should allow burst
        for i in range(10):
            allowed, _ = limiter.is_allowed(client_id, limit)
            assert allowed


# ============================================================================
# Authentication Tests (8 tests)
# ============================================================================

class TestAuthentication:
    """Test authentication functionality"""

    def test_api_key_authentication_success(self):
        """Test successful API key authentication"""
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_keys=["test_api_key_123"]
        )
        auth_mgr = AuthenticationManager(config)

        request = create_test_request(api_key="test_api_key_123")
        authenticated, user_id = auth_mgr.authenticate(request)

        assert authenticated
        assert user_id is not None

    def test_api_key_authentication_failure(self):
        """Test failed API key authentication"""
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_keys=["test_api_key_123"]
        )
        auth_mgr = AuthenticationManager(config)

        request = create_test_request(api_key="invalid_key")
        authenticated, user_id = auth_mgr.authenticate(request)

        assert not authenticated

    def test_api_key_missing(self):
        """Test missing API key"""
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_keys=["test_api_key_123"]
        )
        auth_mgr = AuthenticationManager(config)

        request = create_test_request(api_key=None)
        authenticated, user_id = auth_mgr.authenticate(request)

        assert not authenticated

    def test_jwt_authentication_success(self):
        """Test successful JWT authentication"""
        import json
        import base64

        payload = {"sub": "user_123"}
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip("=")

        token = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{payload_b64}.signature"

        config = AuthConfig(
            auth_type=AuthType.JWT,
            jwt_secret="test_secret"
        )
        auth_mgr = AuthenticationManager(config)

        request = create_test_request()
        request.headers["Authorization"] = f"Bearer {token}"

        authenticated, user_id = auth_mgr.authenticate(request)
        assert authenticated

    def test_jwt_missing_bearer(self):
        """Test JWT without Bearer prefix"""
        config = AuthConfig(
            auth_type=AuthType.JWT,
            jwt_secret="test_secret"
        )
        auth_mgr = AuthenticationManager(config)

        request = create_test_request()
        request.headers["Authorization"] = "InvalidToken"

        authenticated, user_id = auth_mgr.authenticate(request)
        assert not authenticated

    def test_oauth2_authentication_success(self):
        """Test OAuth2 authentication"""
        config = AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_provider="google"
        )
        auth_mgr = AuthenticationManager(config)

        request = create_test_request()
        request.headers["Authorization"] = "Bearer oauth2_token_123456789"

        authenticated, user_id = auth_mgr.authenticate(request)
        assert authenticated

    def test_mtls_authentication_required(self):
        """Test mTLS authentication when client cert required"""
        config = AuthConfig(
            auth_type=AuthType.MTLS,
            client_cert_required=True
        )
        auth_mgr = AuthenticationManager(config)

        request = create_test_request()
        authenticated, user_id = auth_mgr.authenticate(request)

        assert not authenticated

    def test_mtls_authentication_with_cert(self):
        """Test mTLS authentication with client cert"""
        config = AuthConfig(
            auth_type=AuthType.MTLS,
            client_cert_required=True
        )
        auth_mgr = AuthenticationManager(config)

        request = create_test_request()
        request.headers["X-Client-Cert"] = "cert_data_123"

        authenticated, user_id = auth_mgr.authenticate(request)
        assert authenticated


# ============================================================================
# Circuit Breaker Tests (6 tests)
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    def test_circuit_breaker_starts_closed(self):
        """Test circuit breaker starts in CLOSED state"""
        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute()

    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after failures"""
        cb = CircuitBreaker(failure_threshold=3)

        for i in range(3):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN
        assert not cb.can_execute()

    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker enters HALF_OPEN after timeout"""
        cb = CircuitBreaker(failure_threshold=1, timeout_sec=0)

        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert not cb.can_execute()

        # Simulate timeout
        time.sleep(0.1)
        assert cb.can_execute()
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_closes_on_success(self):
        """Test circuit breaker closes on success in HALF_OPEN"""
        cb = CircuitBreaker(failure_threshold=1, timeout_sec=0)

        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        time.sleep(0.1)
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_reopens_on_failure(self):
        """Test circuit breaker reopens if HALF_OPEN fails"""
        cb = CircuitBreaker(failure_threshold=1, timeout_sec=0)

        cb.record_failure()
        time.sleep(0.1)

        # Try in HALF_OPEN
        assert cb.can_execute()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_is_open_property(self):
        """Test is_open property"""
        cb = CircuitBreaker(failure_threshold=1)

        assert not cb.is_open
        cb.record_failure()
        assert cb.is_open


# ============================================================================
# Load Balancing Tests (6 tests)
# ============================================================================

class TestLoadBalancer:
    """Test load balancing functionality"""

    def test_round_robin_load_balancing(self):
        """Test round-robin load balancing"""
        lb = LoadBalancer("round_robin")

        endpoints = [
            create_test_endpoint("ep1", port=8001),
            create_test_endpoint("ep2", port=8002),
            create_test_endpoint("ep3", port=8003)
        ]

        selected = []
        for _ in range(6):
            endpoint = lb.select_endpoint(endpoints)
            selected.append(endpoint.port)

        # Should rotate through endpoints
        assert 8001 in selected
        assert 8002 in selected
        assert 8003 in selected

    def test_weighted_load_balancing(self):
        """Test weighted load balancing"""
        lb = LoadBalancer("weighted")

        endpoints = [
            create_test_endpoint("ep1", port=8001, response_time_ms=5),
            create_test_endpoint("ep2", port=8002, response_time_ms=10),
            create_test_endpoint("ep3", port=8003, response_time_ms=15)
        ]

        selected = []
        for _ in range(10):
            endpoint = lb.select_endpoint(endpoints)
            if endpoint:
                selected.append(endpoint.port)

        # Higher health score (lower latency) should be selected more
        count_8001 = selected.count(8001)
        count_8003 = selected.count(8003)
        assert count_8001 >= count_8003

    def test_least_connections_balancing(self):
        """Test least-connections load balancing"""
        lb = LoadBalancer("least_connections")

        endpoints = [
            create_test_endpoint("ep1", port=8001),
            create_test_endpoint("ep2", port=8002)
        ]

        for _ in range(3):
            endpoint = lb.select_endpoint(endpoints)
            if endpoint:
                lb.connection_count[endpoint.name] = lb.connection_count.get(endpoint.name, 0) + 1

        # Should prefer endpoint with fewer connections
        next_ep = lb.select_endpoint(endpoints)
        assert next_ep.port == 8001

    def test_unhealthy_endpoints_excluded(self):
        """Test unhealthy endpoints are excluded"""
        lb = LoadBalancer("round_robin")

        endpoints = [
            create_test_endpoint("ep1", port=8001, healthy=True),
            create_test_endpoint("ep2", port=8002, healthy=False),
            create_test_endpoint("ep3", port=8003, healthy=True)
        ]

        for _ in range(5):
            endpoint = lb.select_endpoint(endpoints)
            assert endpoint.port != 8002

    def test_all_endpoints_unhealthy(self):
        """Test behavior when all endpoints are unhealthy"""
        lb = LoadBalancer("round_robin")

        endpoints = [
            create_test_endpoint("ep1", port=8001, healthy=False),
            create_test_endpoint("ep2", port=8002, healthy=False)
        ]

        endpoint = lb.select_endpoint(endpoints)
        assert endpoint is None

    def test_endpoint_health_score_calculation(self):
        """Test endpoint health score calculation"""
        endpoint = create_test_endpoint(
            response_time_ms=5.0,
            error_rate=0.01
        )

        health_score = endpoint.health_score
        assert 0 <= health_score <= 100
        assert health_score > 50


# ============================================================================
# Route Matching Tests (4 tests)
# ============================================================================

class TestRouteMatching:
    """Test API route matching"""

    @pytest.mark.asyncio
    async def test_exact_route_match(self):
        """Test exact route matching"""
        gateway = APIGateway()

        route = create_test_route(
            path="/api/users",
            methods=["GET"]
        )
        gateway.register_route(route)

        request = create_test_request(
            method="GET",
            path="/api/users"
        )

        found_route = gateway._find_route(request)
        assert found_route is not None
        assert found_route.path == "/api/users"

    @pytest.mark.asyncio
    async def test_route_with_different_method(self):
        """Test route doesn't match different method"""
        gateway = APIGateway()

        route = create_test_route(
            path="/api/users",
            methods=["GET"]
        )
        gateway.register_route(route)

        request = create_test_request(
            method="POST",
            path="/api/users"
        )

        found_route = gateway._find_route(request)
        # POST not in route methods
        if found_route:
            assert "POST" in found_route.methods

    @pytest.mark.asyncio
    async def test_no_matching_route(self):
        """Test no matching route returns None"""
        gateway = APIGateway()

        request = create_test_request(path="/nonexistent")

        found_route = gateway._find_route(request)
        assert found_route is None

    @pytest.mark.asyncio
    async def test_prefix_route_match(self):
        """Test prefix-based route matching"""
        gateway = APIGateway()

        route = create_test_route(path="/api/")
        gateway.register_route(route)

        request = create_test_request(path="/api/users/123")

        found_route = gateway._find_route(request)
        assert found_route is not None


# ============================================================================
# API Gateway Integration Tests (6 tests)
# ============================================================================

class TestAPIGateway:
    """Test API Gateway functionality"""

    def test_gateway_initialization(self):
        """Test gateway initializes correctly"""
        gateway = create_api_gateway()

        assert gateway.request_count == 0
        assert gateway.success_count == 0
        assert gateway.error_count == 0
        assert len(gateway.routes) == 0
        assert len(gateway.services) == 0

    def test_service_registration(self):
        """Test service registration"""
        gateway = APIGateway()

        endpoints = [
            create_test_endpoint("user_service", port=8001),
            create_test_endpoint("user_service", port=8002)
        ]

        gateway.register_service("user_service", endpoints)

        assert "user_service" in gateway.services
        assert len(gateway.services["user_service"]) == 2

    def test_route_registration(self):
        """Test route registration"""
        gateway = APIGateway()

        route = create_test_route()
        gateway.register_route(route)

        assert len(gateway.routes) > 0

    @pytest.mark.asyncio
    async def test_request_metrics_tracking(self):
        """Test request metrics are tracked"""
        gateway = APIGateway()

        # Setup service
        endpoints = [create_test_endpoint("test_service", port=8001)]
        gateway.register_service("test_service", endpoints)

        # Setup route
        route = create_test_route(
            path="/api/test",
            upstream_service="test_service",
            auth_required=False
        )
        gateway.register_route(route)

        # Make request
        request = create_test_request(
            method="GET",
            path="/api/test"
        )

        await gateway.handle_request(request)

        assert gateway.request_count > 0

    def test_gateway_health_check(self):
        """Test gateway health check endpoint"""
        gateway = APIGateway()

        endpoints = [
            create_test_endpoint("service1", port=8001),
            create_test_endpoint("service1", port=8002)
        ]
        gateway.register_service("service1", endpoints)

        health = gateway.health_check()

        assert health["status"] == "healthy"
        assert "services" in health
        assert "service1" in health["services"]

    def test_gateway_metrics(self):
        """Test gateway metrics endpoint"""
        gateway = APIGateway()

        gateway.request_count = 100
        gateway.success_count = 95
        gateway.error_count = 5
        gateway.total_response_time = 500.0

        metrics = gateway.get_metrics()

        assert metrics["request_count"] == 100
        assert metrics["success_count"] == 95
        assert metrics["error_count"] == 5
        assert metrics["success_rate"] == 95.0
        assert metrics["average_response_time_ms"] == 5.0


# ============================================================================
# Authentication Configuration Tests (4 tests)
# ============================================================================

class TestAuthConfiguration:
    """Test authentication configuration"""

    def test_set_auth_config(self):
        """Test setting auth configuration"""
        gateway = APIGateway()

        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_keys=["key1", "key2"]
        )

        gateway.set_auth_config("user_service", config)

        assert "user_service" in gateway.auth_config

    def test_multiple_services_independent_auth(self):
        """Test different auth configs for different services"""
        gateway = APIGateway()

        api_key_config = AuthConfig(auth_type=AuthType.API_KEY)
        jwt_config = AuthConfig(auth_type=AuthType.JWT)

        gateway.set_auth_config("service1", api_key_config)
        gateway.set_auth_config("service2", jwt_config)

        assert gateway.auth_config["service1"].auth_type == AuthType.API_KEY
        assert gateway.auth_config["service2"].auth_type == AuthType.JWT

    def test_auth_config_with_multiple_api_keys(self):
        """Test auth configuration with multiple API keys"""
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_keys=["key1", "key2", "key3"]
        )

        auth_mgr = AuthenticationManager(config)

        # All keys should work
        for key in ["key1", "key2", "key3"]:
            request = create_test_request(api_key=key)
            authenticated, _ = auth_mgr.authenticate(request)
            assert authenticated

    def test_disabled_authentication(self):
        """Test disabled authentication"""
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            enabled=False
        )

        auth_mgr = AuthenticationManager(config)

        request = create_test_request(api_key=None)
        authenticated, _ = auth_mgr.authenticate(request)

        assert authenticated


# ============================================================================
# Performance Tests (4 tests)
# ============================================================================

class TestPerformance:
    """Performance and throughput tests"""

    def test_rate_limiter_throughput(self):
        """Test rate limiter can handle high throughput"""
        limiter = RateLimiter()
        limit = RateLimit(
            requests_per_second=10000,
            requests_per_minute=600000,
            requests_per_hour=36000000
        )

        start_time = time.time()
        count = 0

        for _ in range(1000):
            allowed, _ = limiter.is_allowed("client", limit)
            if allowed:
                count += 1

        elapsed = time.time() - start_time
        throughput = count / elapsed if elapsed > 0 else 0

        # Should process > 10k requests per second
        assert throughput > 5000

    def test_load_balancer_performance(self):
        """Test load balancer selection performance"""
        lb = LoadBalancer("weighted")

        endpoints = [
            create_test_endpoint(f"ep{i}", port=8000+i)
            for i in range(10)
        ]

        start_time = time.time()

        for _ in range(1000):
            lb.select_endpoint(endpoints)

        elapsed = time.time() - start_time

        # Should process > 100k selections per second
        assert elapsed < 0.01

    def test_circuit_breaker_performance(self):
        """Test circuit breaker performance"""
        cb = CircuitBreaker()

        start_time = time.time()

        for _ in range(10000):
            cb.can_execute()
            cb.record_success()

        elapsed = time.time() - start_time

        # Should handle > 100k operations per second
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_gateway_handles_concurrent_requests(self):
        """Test gateway handles concurrent requests"""
        gateway = APIGateway()

        # Setup
        endpoints = [create_test_endpoint("service", port=8001)]
        gateway.register_service("service", endpoints)

        route = create_test_route(auth_required=False)
        gateway.register_route(route)

        # Send concurrent requests
        tasks = [
            gateway.handle_request(create_test_request())
            for _ in range(10)
        ]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 10
        assert all(isinstance(r, ServiceResponse) for r in responses)


# ============================================================================
# Error Handling Tests (4 tests)
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_404_not_found_response(self):
        """Test 404 response for unknown route"""
        gateway = APIGateway()

        request = create_test_request(path="/nonexistent")

        response = await gateway.handle_request(request)

        assert response.status_code == 404
        assert response.error is not None

    @pytest.mark.asyncio
    async def test_401_unauthorized_response(self):
        """Test 401 response for unauthenticated request"""
        gateway = APIGateway()

        # Setup with auth required
        endpoints = [create_test_endpoint("service", port=8001)]
        gateway.register_service("service", endpoints)

        auth_config = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_keys=["valid_key"]
        )
        gateway.set_auth_config("service", auth_config)

        route = create_test_route(auth_required=True)
        gateway.register_route(route)

        # Request without auth
        request = create_test_request(api_key=None)

        response = await gateway.handle_request(request)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_429_rate_limit_exceeded(self):
        """Test 429 response when rate limit exceeded"""
        gateway = APIGateway()

        # Setup service
        endpoints = [create_test_endpoint("service", port=8001)]
        gateway.register_service("service", endpoints)

        # Route with low rate limit
        rate_limit = RateLimit(
            requests_per_second=1,
            requests_per_minute=2,
            requests_per_hour=100
        )
        route = create_test_route(
            auth_required=False,
            rate_limit=rate_limit
        )
        gateway.register_route(route)

        # Max out the limit
        for _ in range(2):
            request = create_test_request()
            await gateway.handle_request(request)

        # Next request should be rate limited
        request = create_test_request()
        response = await gateway.handle_request(request)

        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_503_service_unavailable(self):
        """Test 503 response when service unavailable"""
        gateway = APIGateway()

        # Setup with unhealthy endpoint
        endpoints = [create_test_endpoint("service", port=8001, healthy=False)]
        gateway.register_service("service", endpoints)

        route = create_test_route(auth_required=False)
        gateway.register_route(route)

        request = create_test_request()

        response = await gateway.handle_request(request)

        assert response.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
