#!/usr/bin/env python3
"""
Global Performance Optimizer
CDN integration, query caching, latency optimization (p95 <500ms)
Date: November 21, 2024
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class CacheTier(Enum):
    """Cache hierarchy tiers"""
    EDGE = 'edge'           # CDN edge (Cloudflare) - global
    REGIONAL = 'regional'   # Regional cache (Redis) - per region
    LOCAL = 'local'         # In-memory cache - per pod


class LatencySLO(Enum):
    """Latency SLOs by operation"""
    WRITE = 200         # milliseconds p95
    READ = 500          # milliseconds p95
    QUERY = 1000        # milliseconds p95
    DASHBOARD = 2000    # milliseconds p95


@dataclass
class LatencyMetric:
    """Latency measurement"""
    timestamp: datetime
    operation: str
    region: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    slo_met: bool


class GlobalCDNController:
    """Manage CDN integration with Cloudflare"""

    def __init__(self, cloudflare_api_client):
        self.cf = cloudflare_api_client
        self.cache_rules: Dict[str, Dict] = {}
        self.edge_stats: Dict[str, Dict] = {}

    async def configure_cdn_caching(self) -> Dict:
        """Configure CDN caching rules"""
        rules = {
            'default_ttl': 300,  # 5 minutes
            'cache_rules': [
                {
                    'path': '/api/v1/metrics',
                    'ttl': 60,  # 1 minute (mostly static metrics)
                    'methods': ['GET'],
                    'cache_on_cookie': None
                },
                {
                    'path': '/api/v1/dashboards',
                    'ttl': 300,  # 5 minutes
                    'methods': ['GET'],
                    'cache_on_cookie': 'session'  # Cache per user session
                },
                {
                    'path': '/api/v1/alerts',
                    'ttl': 30,  # 30 seconds (frequently updated)
                    'methods': ['GET'],
                    'cache_on_cookie': None
                },
                {
                    'path': '/api/v1/logs',
                    'ttl': 0,  # No caching (real-time)
                    'methods': ['GET'],
                    'cache_on_cookie': None
                }
            ],
            'purge_on_write': [
                '/api/v1/metrics',  # Purge metric cache on write
                '/api/v1/dashboards'
            ]
        }

        # Apply rules to Cloudflare
        for rule in rules['cache_rules']:
            await self.cf.create_cache_rule(
                path=rule['path'],
                ttl=rule['ttl'],
                methods=rule['methods']
            )

        self.cache_rules = rules
        logger.info("CDN cache rules configured")
        return rules

    async def purge_cache(self, paths: List[str]) -> bool:
        """Purge cache on write operations"""
        try:
            for path in paths:
                await self.cf.purge_cache_by_path(path)
            logger.debug(f"Cache purged for {len(paths)} paths")
            return True
        except Exception as e:
            logger.error(f"Cache purge failed: {str(e)}")
            return False

    async def get_cdn_stats(self, region: Optional[str] = None) -> Dict:
        """Get CDN performance statistics"""
        stats = await self.cf.get_analytics(
            metric='cacheStatus,requests,bandwidth,threat',
            time_range='1h'
        )

        return {
            'total_requests': stats.get('requests', 0),
            'cache_hit_rate': (
                stats.get('cache_hits', 0) / max(1, stats.get('requests', 1)) * 100
            ),
            'bandwidth_saved_gb': (
                stats.get('cached_bandwidth', 0) / (1024 ** 3)
            ),
            'avg_response_time_ms': stats.get('avg_response_time', 0),
            'threats_blocked': stats.get('threats', 0),
            'edge_locations': stats.get('edge_locations_count', 0)
        }


class QueryCachingStrategy:
    """Intelligent query result caching"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_stats: Dict[str, Dict] = {}

    async def cache_query_result(self, query_hash: str, result: Dict, ttl: int = 300) -> bool:
        """Cache query result with intelligent TTL"""
        try:
            # Determine TTL based on query type
            if 'aggregation' in str(result.keys()).lower():
                ttl = 60  # Aggregations: 1 minute (safe to cache)
            elif 'real_time' in str(result.keys()).lower():
                ttl = 10  # Real-time: 10 seconds
            else:
                ttl = 300  # Default: 5 minutes

            cache_key = f"query:{query_hash}"
            await self.redis.setex(cache_key, ttl, result)

            # Track cache stats
            if query_hash not in self.cache_stats:
                self.cache_stats[query_hash] = {'hits': 0, 'misses': 0}

            return True
        except Exception as e:
            logger.error(f"Query cache write failed: {str(e)}")
            return False

    async def get_cached_query_result(self, query_hash: str) -> Optional[Dict]:
        """Get cached query result"""
        try:
            cache_key = f"query:{query_hash}"
            result = await self.redis.get(cache_key)

            if result:
                if query_hash in self.cache_stats:
                    self.cache_stats[query_hash]['hits'] += 1
                return result
            else:
                if query_hash in self.cache_stats:
                    self.cache_stats[query_hash]['misses'] += 1
                return None

        except Exception as e:
            logger.error(f"Query cache read failed: {str(e)}")
            return None

    def hash_query(self, query_str: str, parameters: Dict) -> str:
        """Generate cache key for query"""
        query_with_params = f"{query_str}:{sorted(parameters.items())}"
        return hashlib.sha256(query_with_params.encode()).hexdigest()

    async def get_cache_hit_rate(self) -> Dict[str, Dict]:
        """Calculate cache hit rate by query type"""
        hit_rates = {}
        for query_hash, stats in self.cache_stats.items():
            total = stats['hits'] + stats['misses']
            if total > 0:
                hit_rate = (stats['hits'] / total) * 100
                hit_rates[query_hash] = {
                    'hit_rate': hit_rate,
                    'hits': stats['hits'],
                    'misses': stats['misses']
                }

        return hit_rates

    async def invalidate_cache_on_write(self, metric_name: str) -> bool:
        """Invalidate related cached queries on metric write"""
        try:
            # Find all cached queries that reference this metric
            pattern = f"query:*{metric_name}*"
            keys = await self.redis.keys(pattern)

            for key in keys:
                await self.redis.delete(key)

            logger.debug(f"Invalidated {len(keys)} cached queries for metric {metric_name}")
            return True
        except Exception as e:
            logger.error(f"Cache invalidation failed: {str(e)}")
            return False


class GlobalLatencySLOController:
    """Monitor and enforce global latency SLOs"""

    LATENCY_TARGETS = {
        'write': LatencySLO.WRITE.value,      # 200ms p95
        'read': LatencySLO.READ.value,        # 500ms p95
        'query': LatencySLO.QUERY.value,      # 1000ms p95
        'dashboard': LatencySLO.DASHBOARD.value  # 2000ms p95
    }

    def __init__(self, db_client, monitoring_client):
        self.db = db_client
        self.monitoring = monitoring_client
        self.latency_metrics: List[LatencyMetric] = []
        self.slo_violations: Dict[str, List] = {}

    async def measure_latency(self, operation: str, region: str,
                            start_time: datetime, end_time: datetime) -> LatencyMetric:
        """Measure operation latency"""
        latency_ms = (end_time - start_time).total_seconds() * 1000

        # Get percentiles from monitoring
        percentiles = await self.monitoring.get_latency_percentiles(
            operation=operation,
            region=region,
            window='5m'
        )

        slo_target = self.LATENCY_TARGETS.get(operation, 500)
        slo_met = percentiles.get('p95', float('inf')) <= slo_target

        metric = LatencyMetric(
            timestamp=datetime.utcnow(),
            operation=operation,
            region=region,
            p50_ms=percentiles.get('p50', 0),
            p95_ms=percentiles.get('p95', 0),
            p99_ms=percentiles.get('p99', 0),
            slo_met=slo_met
        )

        self.latency_metrics.append(metric)

        # Log SLO violation
        if not slo_met:
            if operation not in self.slo_violations:
                self.slo_violations[operation] = []
            self.slo_violations[operation].append({
                'timestamp': datetime.utcnow(),
                'region': region,
                'p95_ms': metric.p95_ms,
                'slo_target': slo_target,
                'violation_percent': ((metric.p95_ms / slo_target) - 1) * 100
            })

            logger.warning(
                f"SLO violation: {operation} in {region}: p95={metric.p95_ms}ms "
                f"(target={slo_target}ms, violation={metric.p95_ms/slo_target:.1f}x)"
            )

        return metric

    async def get_slo_compliance(self, hours: int = 1) -> Dict:
        """Get SLO compliance statistics"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        metrics = await self.db.query(f"""
            SELECT
                operation,
                region,
                COUNT(*) as total_measurements,
                SUM(CASE WHEN slo_met = true THEN 1 ELSE 0 END) as slo_met_count,
                AVG(p50_ms) as avg_p50,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY p95_ms) as p95_p95,
                MAX(p99_ms) as max_p99
            FROM latency_metrics
            WHERE timestamp > '{cutoff.isoformat()}'
            GROUP BY operation, region
            ORDER BY operation, region
        """)

        compliance = {}
        for metric in metrics or []:
            operation = metric['operation']
            region = metric['region']

            if operation not in compliance:
                compliance[operation] = {}

            slo_compliance_rate = (
                (metric['slo_met_count'] / metric['total_measurements'] * 100)
                if metric['total_measurements'] > 0 else 0
            )

            compliance[operation][region] = {
                'slo_target_ms': self.LATENCY_TARGETS.get(operation, 0),
                'p95_ms': metric['p95_p95'],
                'compliance_percentage': slo_compliance_rate,
                'compliant': slo_compliance_rate >= 99.0  # 99% SLO target
            }

        return compliance

    async def get_worst_performing_operations(self, limit: int = 10) -> List[Dict]:
        """Identify operations with highest SLO violation rate"""
        violations = await self.db.query(f"""
            SELECT
                operation,
                region,
                COUNT(*) as violation_count,
                AVG(p95_ms) as avg_violation_ms,
                MAX(p95_ms) as max_violation_ms
            FROM slo_violations
            WHERE timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY operation, region
            ORDER BY violation_count DESC
            LIMIT {limit}
        """)

        return violations or []


class ConnectionPoolingOptimizer:
    """Optimize database connection pools"""

    def __init__(self, db_client):
        self.db = db_client
        self.pool_config = {}

    async def optimize_connection_pools(self) -> Dict:
        """Optimize connection pooling for latency"""
        config = {
            'regional_pools': {}
        }

        regions = [
            'eu-frankfurt',
            'cn-beijing',
            'ap-mumbai',
            'ap-tokyo',
            'ap-singapore',
            'us-virginia',
            'sa-sao-paulo'
        ]

        for region in regions:
            # Calculate optimal pool size based on region metrics
            metrics = await self.db.get_region_metrics(region)
            connections_needed = max(10, int(metrics.get('peak_mps', 1_000_000) / 100_000))

            config['regional_pools'][region] = {
                'min_size': max(5, connections_needed // 2),
                'max_size': connections_needed * 2,
                'idle_timeout_seconds': 300,
                'connection_timeout_ms': 2000,
                'validation_query': 'SELECT 1'
            }

        # Apply configuration
        await self.db.configure_connection_pools(config)
        self.pool_config = config
        logger.info(f"Connection pools optimized for {len(regions)} regions")

        return config


class CompressionOptimizer:
    """Optimize response compression"""

    def __init__(self):
        self.compression_stats: Dict = {}

    async def configure_compression(self) -> Dict:
        """Configure gzip and brotli compression"""
        config = {
            'default_algorithm': 'brotli',  # Better compression ratio
            'fallback_algorithm': 'gzip',
            'compression_level': 6,  # 1-11, balanced for speed/ratio
            'min_size_bytes': 1024,  # Only compress >1KB responses
            'enabled_for': [
                'application/json',
                'text/html',
                'text/plain',
                'application/javascript',
                'text/css'
            ],
            'exclude_content_types': [
                'image/*',  # Already compressed
                'video/*',
                'audio/*'
            ]
        }

        return config

    async def measure_compression_efficiency(self) -> Dict:
        """Measure compression efficiency"""
        stats = await self._calculate_compression_stats()

        return {
            'total_responses': stats['total_responses'],
            'compressed_responses': stats['compressed_count'],
            'original_bytes': stats['original_bytes'],
            'compressed_bytes': stats['compressed_bytes'],
            'compression_ratio': (
                stats['compressed_bytes'] / max(1, stats['original_bytes'])
            ),
            'bandwidth_saved_percent': (
                (1 - stats['compressed_bytes'] / max(1, stats['original_bytes'])) * 100
            ),
            'avg_compression_time_ms': stats['avg_compression_ms']
        }

    async def _calculate_compression_stats(self) -> Dict:
        """Calculate compression statistics"""
        # Placeholder implementation
        return {
            'total_responses': 1_000_000,
            'compressed_count': 950_000,
            'original_bytes': 5_000_000_000,  # 5GB
            'compressed_bytes': 1_000_000_000,  # 1GB (80% reduction)
            'avg_compression_ms': 2
        }


class HTTP2Optimizer:
    """Optimize HTTP/2 protocol"""

    async def configure_http2(self) -> Dict:
        """Configure HTTP/2 settings"""
        config = {
            'enabled': True,
            'server_push': True,
            'push_resources': [
                '/static/index.js',
                '/static/styles.css'
            ],
            'header_compression': True,  # HPACK
            'max_concurrent_streams': 100,
            'initial_window_size': 65535,  # 64KB
            'max_frame_size': 16384
        }

        return config


class GlobalPerformanceOptimizer:
    """Orchestrate all performance optimizations"""

    def __init__(self, cdn_client, redis_client, db_client, monitoring_client):
        self.cdn = GlobalCDNController(cdn_client)
        self.query_cache = QueryCachingStrategy(redis_client)
        self.latency_slo = GlobalLatencySLOController(db_client, monitoring_client)
        self.connection_pool = ConnectionPoolingOptimizer(db_client)
        self.compression = CompressionOptimizer()
        self.http2 = HTTP2Optimizer()

    async def optimize_all(self) -> Dict:
        """Execute all performance optimizations"""
        logger.info("Executing global performance optimization")

        results = await asyncio.gather(
            self.cdn.configure_cdn_caching(),
            self.connection_pool.optimize_connection_pools(),
            self.compression.configure_compression(),
            self.http2.configure_http2(),
            return_exceptions=True
        )

        optimization_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'optimizations': {
                'cdn_caching': 'success' if not isinstance(results[0], Exception) else f'failed: {results[0]}',
                'connection_pooling': 'success' if not isinstance(results[1], Exception) else f'failed: {results[1]}',
                'compression': 'success' if not isinstance(results[2], Exception) else f'failed: {results[2]}',
                'http2': 'success' if not isinstance(results[3], Exception) else f'failed: {results[3]}'
            }
        }

        logger.info(f"Performance optimization completed: {optimization_status}")
        return optimization_status

    async def get_performance_dashboard(self) -> Dict:
        """Get comprehensive performance dashboard"""
        slo_compliance = await self.latency_slo.get_slo_compliance()
        cache_hit_rate = await self.query_cache.get_cache_hit_rate()
        cdn_stats = await self.cdn.get_cdn_stats()
        compression_stats = await self.compression.measure_compression_efficiency()

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'latency_slo_compliance': slo_compliance,
            'cache_hit_rates': cache_hit_rate,
            'cdn_performance': cdn_stats,
            'compression_efficiency': compression_stats,
            'global_status': 'optimized' if all([
                slo_compliance,
                cache_hit_rate,
                cdn_stats
            ]) else 'degraded'
        }
