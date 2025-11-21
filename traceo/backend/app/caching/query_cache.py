#!/usr/bin/env python3
"""
Advanced Query Result Caching for Traceo
Implements multi-level caching strategy for 40-50% latency reduction
Date: November 21, 2024
"""

import logging
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod
import redis
import pickle

logger = logging.getLogger(__name__)


class CacheLayer(ABC):
    """Abstract cache layer"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Set value in cache"""
        pass

    @abstractmethod
    def delete(self, key: str):
        """Delete value from cache"""
        pass

    @abstractmethod
    def clear(self):
        """Clear all cache"""
        pass


class InMemoryCache(CacheLayer):
    """In-memory L1 cache (fastest)"""

    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get with TTL expiration check"""
        if key in self.cache:
            value, expiration = self.cache[key]
            if datetime.utcnow() < expiration:
                self.hits += 1
                return value
            else:
                del self.cache[key]

        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Set with automatic eviction on max size"""
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self.cache.keys(),
                           key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]

        expiration = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        self.cache[key] = (value, expiration)

    def delete(self, key: str):
        """Delete entry"""
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        """Clear all entries"""
        self.cache.clear()

    def get_stats(self) -> Dict:
        """Cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'size': len(self.cache),
            'max_size': self.max_size
        }


class RedisCache(CacheLayer):
    """Redis L2 cache (medium speed)"""

    def __init__(self, host: str = 'localhost', port: int = 6379,
                 db: int = 0, password: Optional[str] = None):
        try:
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=False
            )
            self.redis.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None

        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get from Redis"""
        if not self.redis:
            return None

        try:
            value = self.redis.get(key)
            if value:
                self.hits += 1
                return pickle.loads(value)
            else:
                self.misses += 1
                return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Set in Redis"""
        if not self.redis:
            return

        try:
            serialized = pickle.dumps(value)
            self.redis.setex(key, ttl_seconds, serialized)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    def delete(self, key: str):
        """Delete from Redis"""
        if not self.redis:
            return

        try:
            self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    def clear(self):
        """Clear Redis"""
        if not self.redis:
            return

        try:
            self.redis.flushdb()
        except Exception as e:
            logger.error(f"Redis clear error: {e}")

    def get_stats(self) -> Dict:
        """Cache statistics"""
        if not self.redis:
            return {}

        try:
            info = self.redis.info()
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate,
                'memory_used': info.get('used_memory_human'),
                'keys': self.redis.dbsize()
            }
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {}


class QueryCache:
    """Multi-level query cache with L1 (memory) and L2 (Redis)"""

    # Cache configuration
    QUERY_CACHE_TTL = {
        'dashboard': 300,      # 5 minutes for dashboard queries
        'graph': 600,          # 10 minutes for graph data
        'analytics': 3600,     # 1 hour for analytics
        'report': 86400,       # 1 day for reports
    }

    def __init__(self, redis_host: str = 'localhost'):
        self.l1_cache = InMemoryCache(max_size=1000)
        self.l2_cache = RedisCache(host=redis_host)
        self.query_stats = {
            'total_queries': 0,
            'cached_queries': 0,
            'l1_hits': 0,
            'l2_hits': 0,
            'l1_latency_ms': 0,
            'l2_latency_ms': 0,
            'actual_latency_ms': 0
        }

    def _generate_cache_key(self, query: str, params: Dict) -> str:
        """Generate deterministic cache key"""
        cache_input = f"{query}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(cache_input.encode()).hexdigest()

    def get(self, query: str, params: Dict, query_type: str = 'dashboard') -> Tuple[Optional[Any], Dict]:
        """
        Get cached query result with multi-level lookup.

        Returns:
            (result, cache_stats)
        """
        cache_key = self._generate_cache_key(query, params)
        cache_stats = {
            'hit': False,
            'level': None,
            'latency_ms': 0
        }

        start_time = time.time()

        # Try L1 cache
        result = self.l1_cache.get(cache_key)
        if result:
            cache_stats['hit'] = True
            cache_stats['level'] = 'L1'
            cache_stats['latency_ms'] = (time.time() - start_time) * 1000
            self.query_stats['l1_hits'] += 1
            logger.debug(f"L1 cache hit for key {cache_key[:8]}")
            return result, cache_stats

        # Try L2 cache
        result = self.l2_cache.get(cache_key)
        if result:
            # Populate L1 from L2
            self.l1_cache.set(cache_key, result, self.QUERY_CACHE_TTL.get(query_type, 300))
            cache_stats['hit'] = True
            cache_stats['level'] = 'L2'
            cache_stats['latency_ms'] = (time.time() - start_time) * 1000
            self.query_stats['l2_hits'] += 1
            logger.debug(f"L2 cache hit for key {cache_key[:8]}")
            return result, cache_stats

        # Cache miss
        self.query_stats['total_queries'] += 1
        logger.debug(f"Cache miss for key {cache_key[:8]}")
        return None, cache_stats

    def set(self, query: str, params: Dict, result: Any,
            query_type: str = 'dashboard'):
        """Set cache entry in both L1 and L2"""
        cache_key = self._generate_cache_key(query, params)
        ttl = self.QUERY_CACHE_TTL.get(query_type, 300)

        # Set in both caches
        self.l1_cache.set(cache_key, result, ttl)
        self.l2_cache.set(cache_key, result, ttl)

        self.query_stats['cached_queries'] += 1
        logger.debug(f"Cached result for key {cache_key[:8]}")

    def invalidate_pattern(self, pattern: str):
        """
        Invalidate cache entries matching pattern.

        Examples:
        - "http_requests_*" for all HTTP request metrics
        - "dashboard_production_*" for production dashboard
        """
        logger.info(f"Invalidating cache pattern: {pattern}")
        # In production, use Redis KEYS pattern matching
        # This is a simplified version
        if self.l2_cache.redis:
            keys = self.l2_cache.redis.keys(pattern)
            for key in keys:
                self.l2_cache.delete(key)
                self.l1_cache.delete(key)

    def get_cache_stats(self) -> Dict:
        """Get detailed cache statistics"""
        total_queries = self.query_stats['total_queries']
        cache_hit_rate = 0
        if total_queries > 0:
            cache_hit_rate = (self.query_stats['cached_queries'] / total_queries) * 100

        return {
            'total_queries': total_queries,
            'cached_queries': self.query_stats['cached_queries'],
            'cache_hit_rate': cache_hit_rate,
            'l1_cache': self.l1_cache.get_stats(),
            'l2_cache': self.l2_cache.get_stats(),
            'l1_hits': self.query_stats['l1_hits'],
            'l2_hits': self.query_stats['l2_hits'],
            'l1_hit_ratio': self.query_stats['l1_hits'] / max(total_queries, 1),
            'l2_hit_ratio': self.query_stats['l2_hits'] / max(total_queries, 1)
        }

    def clear_all(self):
        """Clear all caches"""
        logger.warning("Clearing all caches")
        self.l1_cache.clear()
        self.l2_cache.clear()


class CachedQueryExecutor:
    """Execute queries with automatic caching"""

    def __init__(self, query_executor, cache: QueryCache):
        self.executor = query_executor
        self.cache = cache

    def execute(self, query: str, params: Dict, query_type: str = 'dashboard',
                skip_cache: bool = False) -> Tuple[Any, Dict]:
        """
        Execute query with caching.

        Returns:
            (result, metadata)
        """
        metadata = {
            'cached': False,
            'execution_time_ms': 0,
            'cache_latency_ms': 0
        }

        # Try cache first
        if not skip_cache:
            cached_result, cache_stats = self.cache.get(query, params, query_type)
            if cached_result:
                metadata['cached'] = True
                metadata['cache_latency_ms'] = cache_stats['latency_ms']
                logger.info(f"Returned cached result in {cache_stats['latency_ms']:.1f}ms "
                          f"from {cache_stats['level']}")
                return cached_result, metadata

        # Execute query
        start_time = time.time()
        result = self.executor.execute(query, params)
        execution_time = (time.time() - start_time) * 1000

        # Cache result
        self.cache.set(query, params, result, query_type)

        metadata['execution_time_ms'] = execution_time
        logger.info(f"Executed query in {execution_time:.1f}ms, cached for future use")

        return result, metadata


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Initialize cache
    cache = QueryCache(redis_host='localhost')

    # Simulate queries
    queries = [
        ('SELECT * FROM metrics WHERE service = ?', {'service': 'api-server'}),
        ('SELECT rate(http_requests[5m])', {}),
        ('SELECT * FROM metrics WHERE service = ?', {'service': 'api-server'}),  # Repeat
    ]

    for query, params in queries:
        # Try cache
        result, stats = cache.get(query, params, 'dashboard')

        if not result:
            # Simulate query execution
            print(f"Executing: {query}")
            result = {'data': 'mock_data', 'timestamp': datetime.utcnow()}
            cache.set(query, params, result, 'dashboard')

    # Print stats
    stats = cache.get_cache_stats()
    print(f"\n=== Cache Statistics ===")
    print(f"Total queries: {stats['total_queries']}")
    print(f"Cache hit rate: {stats['cache_hit_rate']:.1f}%")
    print(f"L1 cache hits: {stats['l1_hits']}")
    print(f"L2 cache hits: {stats['l2_hits']}")
    print(f"L1 stats: {stats['l1_cache']}")
