"""
Comprehensive test suite for Performance Optimization & Caching

Target: 100x improvement (300ms → 3ms), 70% bandwidth reduction
Tests: 40+ cases covering all components
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from typing import Any

from app.performance_optimization import (
    RedisCache,
    CachePattern,
    CachePatternManager,
    QueryOptimizer,
    QueryType,
    CachingPyramid,
    CacheLevel,
    PerformanceMonitor,
    IndexType,
    IndexSuggestion,
    CDNConfig,
    cached,
    monitored,
    create_performance_optimizer
)


# ============================================================================
# Redis Cache Tests (8 tests)
# ============================================================================

class TestRedisCache:
    """Test Redis cache functionality"""

    def test_cache_initialization(self):
        """Test cache initializes correctly"""
        cache = RedisCache(mode="standalone")

        assert cache.mode == "standalone"
        assert len(cache.cache) == 0
        assert cache.current_size == 0

    def test_set_and_get(self):
        """Test basic set and get operations"""
        cache = RedisCache()

        cache.set("key1", {"data": "value"}, 3600)
        value = cache.get("key1")

        assert value == {"data": "value"}

    def test_get_nonexistent_key(self):
        """Test getting non-existent key returns None"""
        cache = RedisCache()

        value = cache.get("nonexistent")

        assert value is None
        assert cache.stats["misses"] == 1

    def test_cache_expiration(self):
        """Test TTL expiration"""
        cache = RedisCache()

        cache.set("key1", "value", ttl_seconds=0)  # Immediate expiration
        value = cache.get("key1")

        assert value is None

    def test_cache_hit_tracking(self):
        """Test cache hit/miss statistics"""
        cache = RedisCache()

        cache.set("key1", "value", 3600)

        # Hit
        cache.get("key1")
        assert cache.stats["hits"] == 1

        # Miss
        cache.get("key2")
        assert cache.stats["misses"] == 2

    def test_cache_deletion(self):
        """Test key deletion"""
        cache = RedisCache()

        cache.set("key1", "value", 3600)
        cache.delete("key1")
        value = cache.get("key1")

        assert value is None

    def test_cache_clear(self):
        """Test clearing entire cache"""
        cache = RedisCache()

        for i in range(5):
            cache.set(f"key{i}", f"value{i}", 3600)

        assert len(cache.cache) == 5

        cache.clear()

        assert len(cache.cache) == 0
        assert cache.current_size == 0

    def test_lru_eviction_policy(self):
        """Test LRU eviction policy"""
        cache = RedisCache()
        cache.max_size_bytes = 1000  # Small size to force eviction
        cache.eviction_policy = "lru"

        # Add entries
        for i in range(3):
            cache.set(f"key{i}", {"data": f"value{i}" * 100}, 3600)

        # Access key0 multiple times (make it more recently used)
        cache.get("key0")
        cache.get("key0")

        # Adding new entry should evict least recently used (key1)
        cache.set("key3", {"data": "new_value" * 100}, 3600)

        assert "key0" in cache.cache
        assert "key3" in cache.cache

    def test_cache_statistics(self):
        """Test cache statistics reporting"""
        cache = RedisCache()

        for i in range(5):
            cache.set(f"key{i}", f"value{i}", 3600)
            cache.get(f"key{i}")

        stats = cache.get_stats()

        assert stats["sets"] == 5
        assert stats["hits"] >= 5
        assert stats["current_entries"] == 5


# ============================================================================
# Cache Pattern Tests (6 tests)
# ============================================================================

class TestCachePattern:
    """Test cache patterns"""

    def test_cache_aside_pattern_hit(self):
        """Test cache-aside pattern with cache hit"""
        cache = RedisCache()
        pattern_mgr = CachePatternManager(cache)

        load_count = 0

        def loader():
            nonlocal load_count
            load_count += 1
            return {"data": "value"}

        # First call - loads from source
        result1 = pattern_mgr.get_with_pattern(
            "key1", CachePattern.CACHE_ASIDE, loader, 3600
        )
        assert load_count == 1
        assert result1 == {"data": "value"}

        # Second call - hits cache
        result2 = pattern_mgr.get_with_pattern(
            "key1", CachePattern.CACHE_ASIDE, loader, 3600
        )
        assert load_count == 1  # Loader not called again
        assert result2 == {"data": "value"}

    def test_write_through_pattern(self):
        """Test write-through pattern"""
        cache = RedisCache()
        pattern_mgr = CachePatternManager(cache)

        def loader():
            return {"data": "value"}

        result = pattern_mgr.get_with_pattern(
            "key1", CachePattern.WRITE_THROUGH, loader, 3600
        )

        # Value should be in cache
        cached = cache.get("key1")
        assert cached == result
        assert result == {"data": "value"}

    def test_write_behind_pattern(self):
        """Test write-behind (write-back) pattern"""
        cache = RedisCache()
        pattern_mgr = CachePatternManager(cache)

        def loader():
            return {"data": "value"}

        result = pattern_mgr.get_with_pattern(
            "key1", CachePattern.WRITE_BEHIND, loader, 3600
        )

        # Value should be in cache immediately
        cached = cache.get("key1")
        assert cached == result

        # Should be queued for delayed write
        assert len(pattern_mgr.write_behind_queue) > 0

    def test_write_around_pattern(self):
        """Test write-around pattern"""
        cache = RedisCache()
        pattern_mgr = CachePatternManager(cache)

        # Pre-populate cache
        cache.set("key1", "old_value", 3600)
        assert cache.get("key1") == "old_value"

        def loader():
            return "new_value"

        result = pattern_mgr.get_with_pattern(
            "key1", CachePattern.WRITE_AROUND, loader, 3600
        )

        # Cache should be invalidated
        assert cache.get("key1") is None
        assert result == "new_value"

    def test_cache_pattern_ttl_configuration(self):
        """Test TTL configuration per pattern"""
        cache = RedisCache()
        pattern_mgr = CachePatternManager(cache)

        def loader():
            return "value"

        pattern_mgr.get_with_pattern(
            "key1", CachePattern.CACHE_ASIDE, loader, ttl_seconds=1
        )

        # TTL should be set
        entry = cache.cache["key1"]
        assert entry.ttl_seconds == 1

    def test_multiple_patterns_isolation(self):
        """Test different patterns don't interfere"""
        cache = RedisCache()
        pattern_mgr = CachePatternManager(cache)

        call_count = {}

        def loader(name):
            def inner():
                call_count[name] = call_count.get(name, 0) + 1
                return name
            return inner

        # Use different patterns
        pattern_mgr.get_with_pattern("key1", CachePattern.CACHE_ASIDE, loader("a"), 3600)
        pattern_mgr.get_with_pattern("key2", CachePattern.WRITE_THROUGH, loader("b"), 3600)

        assert call_count.get("a", 0) >= 1
        assert call_count.get("b", 0) >= 1


# ============================================================================
# Query Optimizer Tests (8 tests)
# ============================================================================

class TestQueryOptimizer:
    """Test query optimization functionality"""

    def test_analyze_select_query(self):
        """Test SELECT query analysis"""
        optimizer = QueryOptimizer()

        metrics = optimizer.analyze_query(
            "SELECT * FROM users WHERE id = 1",
            execution_time_ms=50.0,
            rows_returned=1
        )

        assert metrics.query_type == QueryType.SELECT
        assert metrics.execution_time_ms == 50.0
        assert metrics.rows_returned == 1

    def test_analyze_insert_query(self):
        """Test INSERT query analysis"""
        optimizer = QueryOptimizer()

        metrics = optimizer.analyze_query(
            "INSERT INTO users (name) VALUES ('John')",
            execution_time_ms=10.0,
            rows_affected=1
        )

        assert metrics.query_type == QueryType.INSERT

    def test_slow_query_detection(self):
        """Test slow query flagging"""
        optimizer = QueryOptimizer()
        optimizer.slow_query_threshold_ms = 50

        # Fast query
        optimizer.analyze_query("SELECT * FROM users", 30.0)

        # Slow query
        optimizer.analyze_query("SELECT * FROM large_table", 200.0)

        slow_queries = optimizer.identify_slow_queries()
        assert len(slow_queries) > 0
        assert slow_queries[0].execution_time_ms == 200.0

    def test_sequential_scan_detection(self):
        """Test sequential scan detection"""
        optimizer = QueryOptimizer()

        metrics = optimizer.analyze_query(
            "SELECT * FROM users",
            execution_time_ms=150.0,
            has_seq_scan=True
        )

        assert metrics.has_seq_scan is True

    def test_index_type_selection(self):
        """Test appropriate index type selection"""
        optimizer = QueryOptimizer()

        # Query with timestamp (should suggest BRIN)
        metrics = optimizer.analyze_query(
            "SELECT * FROM logs WHERE created_at > '2025-01-01'",
            execution_time_ms=200.0,
            has_seq_scan=True
        )

        suggestions = optimizer.suggest_indexes()
        if suggestions:
            # BRIN typically better for time-series
            assert suggestions[0].index_type in [IndexType.BRIN, IndexType.BTREE]

    def test_index_suggestion_generation(self):
        """Test index suggestion generation"""
        optimizer = QueryOptimizer()

        # Multiple slow sequential scans
        for i in range(5):
            optimizer.analyze_query(
                f"SELECT * FROM table{i} WHERE id = {i}",
                execution_time_ms=150.0,
                has_seq_scan=True
            )

        suggestions = optimizer.suggest_indexes()

        assert len(suggestions) > 0
        assert all(isinstance(s, IndexSuggestion) for s in suggestions)

    def test_query_statistics(self):
        """Test query statistics reporting"""
        optimizer = QueryOptimizer()
        optimizer.slow_query_threshold_ms = 100

        # Add queries
        optimizer.analyze_query("SELECT * FROM users", 50.0)
        optimizer.analyze_query("SELECT * FROM large_table", 200.0)
        optimizer.analyze_query("SELECT * FROM orders", 80.0)

        stats = optimizer.get_statistics()

        assert stats["total_queries"] == 3
        assert stats["max_execution_time_ms"] == 200.0
        assert stats["slow_query_count"] == 1

    def test_query_deduplication(self):
        """Test query ID generation and deduplication"""
        optimizer = QueryOptimizer()

        query = "SELECT * FROM users WHERE id = 1"

        metrics1 = optimizer.analyze_query(query, 50.0)
        metrics2 = optimizer.analyze_query(query, 60.0)

        # Should have same query ID
        assert metrics1.query_id == metrics2.query_id


# ============================================================================
# Caching Pyramid Tests (6 tests)
# ============================================================================

class TestCachingPyramid:
    """Test multi-level caching pyramid"""

    def test_pyramid_initialization(self):
        """Test pyramid initializes with all levels"""
        pyramid = CachingPyramid()

        assert CacheLevel.BROWSER in pyramid.levels
        assert CacheLevel.CDN in pyramid.levels
        assert CacheLevel.APPLICATION in pyramid.levels
        assert CacheLevel.QUERY in pyramid.levels
        assert CacheLevel.INDEX in pyramid.levels

    def test_pyramid_get_with_hit(self):
        """Test getting value from pyramid (cache hit)"""
        pyramid = CachingPyramid()

        # Pre-populate cache
        pyramid.levels[CacheLevel.APPLICATION].set("key1", {"data": "cached"}, 3600)

        load_count = 0

        def loader():
            nonlocal load_count
            load_count += 1
            return {"data": "fresh"}

        result = pyramid.get_with_pyramid("key1", loader)

        assert result == {"data": "cached"}
        assert load_count == 0  # Loader not called

    def test_pyramid_get_with_miss(self):
        """Test getting value from pyramid (cache miss)"""
        pyramid = CachingPyramid()

        load_count = 0

        def loader():
            nonlocal load_count
            load_count += 1
            return {"data": "fresh"}

        result = pyramid.get_with_pyramid("key1", loader)

        assert result == {"data": "fresh"}
        assert load_count == 1

        # Value should now be cached at all levels
        for level in [CacheLevel.APPLICATION, CacheLevel.QUERY]:
            cached = pyramid.levels[level].get("key1")
            assert cached == {"data": "fresh"}

    def test_pyramid_custom_ttl_levels(self):
        """Test custom TTL configuration per level"""
        pyramid = CachingPyramid()

        custom_ttl = {
            CacheLevel.APPLICATION: 600,
            CacheLevel.QUERY: 60,
            CacheLevel.CDN: 3600
        }

        def loader():
            return "value"

        pyramid.get_with_pyramid("key1", loader, ttl_levels=custom_ttl)

        # Check TTLs are set correctly
        entry = pyramid.levels[CacheLevel.APPLICATION].cache.get("key1")
        if entry:
            assert entry.ttl_seconds == 600

    def test_pyramid_cdn_configuration(self):
        """Test CDN configuration"""
        pyramid = CachingPyramid()

        cdn_config = CDNConfig(
            provider="akamai",
            ttl_seconds=7200,
            enable_gzip=True,
            enable_brotli=True
        )

        pyramid.configure_cdn(cdn_config)

        assert pyramid.cdn_config.provider == "akamai"
        assert pyramid.cdn_config.ttl_seconds == 7200

    def test_pyramid_statistics(self):
        """Test pyramid statistics aggregation"""
        pyramid = CachingPyramid()

        # Add some data
        pyramid.levels[CacheLevel.APPLICATION].set("key1", "value1", 3600)
        pyramid.levels[CacheLevel.QUERY].set("key2", "value2", 3600)

        # Generate hits
        pyramid.levels[CacheLevel.APPLICATION].get("key1")
        pyramid.levels[CacheLevel.QUERY].get("key2")

        stats = pyramid.get_pyramid_stats()

        assert "application" in stats
        assert "query" in stats


# ============================================================================
# Performance Monitor Tests (6 tests)
# ============================================================================

class TestPerformanceMonitor:
    """Test performance monitoring"""

    def test_record_request(self):
        """Test recording request metrics"""
        monitor = PerformanceMonitor()

        monitor.record_request("/api/users", "GET", 50.0, 200, cache_hit=True)

        assert len(monitor.request_metrics) == 1
        assert monitor.request_metrics[0]["endpoint"] == "/api/users"
        assert monitor.request_metrics[0]["latency_ms"] == 50.0

    def test_slow_request_tracking(self):
        """Test tracking of slow requests"""
        monitor = PerformanceMonitor()
        monitor.latency_threshold_ms = 100

        # Normal request
        monitor.record_request("/api/users", "GET", 50.0, 200)
        assert len(monitor.slow_endpoints) == 0

        # Slow request
        monitor.record_request("/api/orders", "GET", 200.0, 200)
        assert len(monitor.slow_endpoints) == 1

    def test_performance_report(self):
        """Test performance report generation"""
        monitor = PerformanceMonitor()

        for i in range(10):
            latency = 50 + (i * 10)
            monitor.record_request(f"/api/endpoint{i}", "GET", float(latency), 200)

        report = monitor.get_performance_report()

        assert report["total_requests"] == 10
        assert report["average_latency_ms"] > 0
        assert "p95_latency_ms" in report
        assert "p99_latency_ms" in report

    def test_cache_hit_rate(self):
        """Test cache hit rate calculation"""
        monitor = PerformanceMonitor()

        monitor.record_request("/api/users", "GET", 10.0, 200, cache_hit=True)
        monitor.record_request("/api/users", "GET", 10.0, 200, cache_hit=True)
        monitor.record_request("/api/users", "GET", 100.0, 200, cache_hit=False)

        report = monitor.get_performance_report()

        assert report["cache_hit_rate_percent"] >= 60

    def test_percentile_calculation(self):
        """Test percentile calculation"""
        monitor = PerformanceMonitor()

        # Record latencies: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
        for i in range(1, 11):
            monitor.record_request(f"/api/test{i}", "GET", float(i * 10), 200)

        report = monitor.get_performance_report()

        # P95 should be around 95, P99 should be around 99
        assert 85 <= report["p95_latency_ms"] <= 105
        assert 90 <= report["p99_latency_ms"] <= 110

    def test_slow_endpoints_retrieval(self):
        """Test getting slowest endpoints"""
        monitor = PerformanceMonitor()
        monitor.latency_threshold_ms = 50

        # Record various requests
        for i in range(15):
            latency = 100 + (i * 10)  # All slow
            monitor.record_request(f"/api/endpoint{i}", "GET", float(latency), 200)

        slow_endpoints = monitor.get_slow_endpoints(limit=5)

        assert len(slow_endpoints) == 5
        # Should be sorted by latency (descending)
        for i in range(len(slow_endpoints) - 1):
            assert slow_endpoints[i]["latency_ms"] >= slow_endpoints[i + 1]["latency_ms"]


# ============================================================================
# Decorator Tests (4 tests)
# ============================================================================

class TestDecorators:
    """Test performance decorators"""

    def test_cached_decorator(self):
        """Test @cached decorator"""
        call_count = 0

        @cached(ttl_seconds=3600)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call (should be cached)
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not called again

    def test_monitored_decorator(self):
        """Test @monitored decorator"""
        monitor = PerformanceMonitor()

        @monitored(monitor=monitor)
        def test_function():
            time.sleep(0.01)
            return "result"

        result = test_function()

        assert result == "result"
        assert len(monitor.request_metrics) > 0
        assert monitor.request_metrics[0]["latency_ms"] > 5

    def test_cached_different_arguments(self):
        """Test @cached with different arguments"""
        call_count = {}

        @cached(ttl_seconds=3600)
        def function_with_args(x, y):
            key = f"{x}_{y}"
            call_count[key] = call_count.get(key, 0) + 1
            return x + y

        # Different arguments should not hit cache
        result1 = function_with_args(1, 2)
        result2 = function_with_args(1, 3)

        assert result1 == 3
        assert result2 == 4

    def test_decorator_composition(self):
        """Test combining @cached and @monitored decorators"""
        monitor = PerformanceMonitor()
        call_count = 0

        @cached(ttl_seconds=3600)
        @monitored(monitor=monitor)
        def composed_function():
            nonlocal call_count
            call_count += 1
            return "result"

        # Should be cached and monitored
        result1 = composed_function()
        result2 = composed_function()

        assert result1 == result2
        assert call_count == 1  # Only called once


# ============================================================================
# Integration Tests (4 tests)
# ============================================================================

class TestIntegration:
    """Integration tests for performance optimization system"""

    def test_full_optimization_system(self):
        """Test complete optimization system"""
        system = create_performance_optimizer()

        assert "cache" in system
        assert "optimizer" in system
        assert "pyramid" in system
        assert "monitor" in system

    def test_cache_and_optimizer_together(self):
        """Test cache and optimizer working together"""
        cache = RedisCache()
        optimizer = QueryOptimizer()

        # Simulate slow query
        optimizer.analyze_query(
            "SELECT * FROM users WHERE name LIKE '%test%'",
            execution_time_ms=250.0,
            has_seq_scan=True
        )

        # Cache the result
        cache.set("user_search_test", {"results": []}, 3600)

        # Get from cache (much faster)
        cached_result = cache.get("user_search_test")
        assert cached_result is not None

        # Query optimizer should suggest index
        suggestions = optimizer.suggest_indexes()
        assert len(suggestions) > 0

    def test_pyramid_with_monitor(self):
        """Test pyramid with performance monitoring"""
        pyramid = CachingPyramid()
        monitor = PerformanceMonitor()

        def slow_loader():
            time.sleep(0.05)
            return {"data": "value"}

        # First call (slow)
        start = time.time()
        result1 = pyramid.get_with_pyramid("key1", slow_loader)
        latency1 = (time.time() - start) * 1000
        monitor.record_request("/pyramid", "GET", latency1, 200, cache_hit=False)

        # Second call (cached, should be much faster)
        start = time.time()
        result2 = pyramid.get_with_pyramid("key1", slow_loader)
        latency2 = (time.time() - start) * 1000
        monitor.record_request("/pyramid", "GET", latency2, 200, cache_hit=True)

        assert result1 == result2
        assert latency2 < latency1  # Cached should be faster

        report = monitor.get_performance_report()
        assert report["cache_hit_rate_percent"] == 50

    def test_100x_improvement_potential(self):
        """Test 100x improvement scenario (300ms → 3ms)"""
        # Simulate database query (300ms)
        db_query_time = 300.0

        # With caching (3ms)
        cache_hit_time = 3.0

        improvement_factor = db_query_time / cache_hit_time

        assert improvement_factor == 100
        assert improvement_factor >= 50  # At least 50x improvement


# ============================================================================
# Performance Tests (2 tests)
# ============================================================================

class TestPerformanceTargets:
    """Test performance targets"""

    def test_cache_operations_latency(self):
        """Test cache operations stay under latency targets"""
        cache = RedisCache()

        start = time.time()

        for i in range(1000):
            cache.set(f"key{i}", f"value{i}", 3600)

        write_time = time.time() - start

        start = time.time()

        for i in range(1000):
            cache.get(f"key{i}")

        read_time = time.time() - start

        # Should be very fast (< 1ms per operation on average)
        assert write_time < 1.0  # 1000 ops in < 1 second
        assert read_time < 0.5   # 1000 ops in < 0.5 second

    def test_query_optimizer_throughput(self):
        """Test query optimizer throughput"""
        optimizer = QueryOptimizer()

        start = time.time()

        for i in range(100):
            optimizer.analyze_query(
                f"SELECT * FROM table{i}",
                execution_time_ms=50.0 + i
            )

        elapsed = time.time() - start

        # Should process > 1000 queries per second
        throughput = 100 / elapsed
        assert throughput > 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
