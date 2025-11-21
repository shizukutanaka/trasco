#!/usr/bin/env python3
"""
Global Performance Optimizer
CDN integration, query caching, latency optimization (p95 <500ms)
Simplified, production-ready implementation
Date: November 21, 2024
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


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

    async def configure_cdn_caching(self) -> Dict:
        """Configure CDN caching rules (minimal, essential only)"""
        rules = {
            'default_ttl': 300,  # 5 minutes
            'cache_rules': [
                {
                    'path': '/api/v1/metrics',
                    'ttl': 60,  # 1 minute
                    'methods': ['GET']
                },
                {
                    'path': '/api/v1/dashboards',
                    'ttl': 300,  # 5 minutes
                    'methods': ['GET']
                },
                {
                    'path': '/api/v1/alerts',
                    'ttl': 30,  # 30 seconds
                    'methods': ['GET']
                }
            ]
        }

        # Apply rules to Cloudflare
        for rule in rules['cache_rules']:
            await self.cf.create_cache_rule(
                path=rule['path'],
                ttl=rule['ttl'],
                methods=rule['methods']
            )

        logger.info("CDN cache rules configured")
        return rules

    async def purge_cache(self, paths: List[str]) -> bool:
        """Purge cache on write operations"""
        try:
            for path in paths:
                await self.cf.purge_cache_by_path(path)
            return True
        except Exception as e:
            logger.error(f"Cache purge failed: {str(e)}")
            return False

    async def get_cdn_stats(self) -> Dict:
        """Get CDN performance statistics"""
        stats = await self.cf.get_analytics(
            metric='cacheStatus,requests,bandwidth',
            time_range='1h'
        )

        total_requests = stats.get('requests', 1)
        cache_hits = stats.get('cache_hits', 0)

        return {
            'total_requests': total_requests,
            'cache_hit_rate': (cache_hits / total_requests * 100) if total_requests > 0 else 0,
            'bandwidth_saved_gb': (stats.get('cached_bandwidth', 0) / (1024 ** 3)),
            'avg_response_time_ms': stats.get('avg_response_time', 0)
        }


class QueryCachingStrategy:
    """Intelligent query result caching"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def cache_query_result(self, query_hash: str, result: Dict, ttl: int = 300) -> bool:
        """Cache query result with intelligent TTL"""
        try:
            # Simple TTL logic
            if 'aggregation' in str(result.keys()).lower():
                ttl = 60
            elif 'real_time' in str(result.keys()).lower():
                ttl = 10
            else:
                ttl = 300

            await self.redis.setex(f"query:{query_hash}", ttl, result)
            return True
        except Exception as e:
            logger.error(f"Query cache write failed: {str(e)}")
            return False

    async def get_cached_query_result(self, query_hash: str) -> Optional[Dict]:
        """Get cached query result"""
        try:
            return await self.redis.get(f"query:{query_hash}")
        except Exception as e:
            logger.error(f"Query cache read failed: {str(e)}")
            return None

    async def invalidate_cache_on_write(self, metric_name: str) -> bool:
        """Invalidate related cached queries on metric write"""
        try:
            pattern = f"query:*{metric_name}*"
            keys = await self.redis.keys(pattern)
            for key in keys:
                await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache invalidation failed: {str(e)}")
            return False


class GlobalLatencySLOController:
    """Monitor and enforce global latency SLOs"""

    LATENCY_TARGETS = {
        'write': LatencySLO.WRITE.value,
        'read': LatencySLO.READ.value,
        'query': LatencySLO.QUERY.value,
        'dashboard': LatencySLO.DASHBOARD.value
    }

    def __init__(self, db_client, monitoring_client):
        self.db = db_client
        self.monitoring = monitoring_client
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

        # Log SLO violation
        if not slo_met:
            if operation not in self.slo_violations:
                self.slo_violations[operation] = []
            self.slo_violations[operation].append({
                'timestamp': datetime.utcnow(),
                'region': region,
                'p95_ms': metric.p95_ms,
                'slo_target': slo_target
            })

            logger.warning(
                f"SLO violation: {operation} in {region}: p95={metric.p95_ms}ms "
                f"(target={slo_target}ms)"
            )

        return metric

    async def get_slo_compliance(self, hours: int = 1) -> Dict:
        """Get SLO compliance statistics"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        metrics = await self.db.query(f"""
            SELECT operation, region,
                   COUNT(*) as total,
                   SUM(CASE WHEN slo_met = true THEN 1 ELSE 0 END) as met,
                   PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY p95_ms) as p95
            FROM latency_metrics
            WHERE timestamp > '{cutoff.isoformat()}'
            GROUP BY operation, region
        """)

        compliance = {}
        for m in metrics or []:
            op = m['operation']
            region = m['region']
            if op not in compliance:
                compliance[op] = {}

            compliance_rate = (m['met'] / max(1, m['total']) * 100) if m['total'] > 0 else 0
            compliance[op][region] = {
                'slo_target_ms': self.LATENCY_TARGETS.get(op, 0),
                'p95_ms': m['p95'],
                'compliance_percentage': compliance_rate,
                'compliant': compliance_rate >= 99.0
            }

        return compliance


class CapacityPlanner:
    """Simple capacity planning using exponential smoothing"""

    def __init__(self, db_client):
        self.db = db_client

    async def forecast_capacity(self, region: str, days_ahead: int = 30) -> List[Dict]:
        """Forecast capacity using simple exponential smoothing"""
        # Get historical data (30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        history = await self.db.query(f"""
            SELECT timestamp, metrics_per_sec
            FROM regional_capacity_metrics
            WHERE region = '{region}' AND timestamp > '{cutoff.isoformat()}'
            ORDER BY timestamp
        """)

        if not history or len(history) < 10:
            logger.warning(f"Insufficient data for {region}")
            return []

        values = [h['metrics_per_sec'] for h in history]
        current = values[-1]
        avg = sum(values) / len(values)

        # Simple exponential smoothing
        alpha = 0.3  # Smoothing factor
        forecast = []

        for day in range(1, days_ahead + 1):
            # Trend from last 7 days
            recent_trend = (values[-1] - values[-7]) / 7 if len(values) >= 7 else 0

            # Simple forecast
            predicted = current + (recent_trend * day)

            # Add 20% buffer for safety
            upper_bound = predicted * 1.2

            forecast.append({
                'day': day,
                'forecasted_mps': predicted,
                'upper_bound': upper_bound,
                'scaling_needed': predicted > current * 1.2
            })

        return forecast

    async def generate_hpa_config(self) -> Dict:
        """Generate Kubernetes HPA scaling policy"""
        return {
            'apiVersion': 'autoscaling/v2',
            'kind': 'HorizontalPodAutoscaler',
            'spec': {
                'minReplicas': 50,
                'maxReplicas': 500,
                'metrics': [
                    {
                        'type': 'Resource',
                        'resource': {
                            'name': 'cpu',
                            'target': {'type': 'Utilization', 'averageUtilization': 70}
                        }
                    },
                    {
                        'type': 'Resource',
                        'resource': {
                            'name': 'memory',
                            'target': {'type': 'Utilization', 'averageUtilization': 80}
                        }
                    }
                ],
                'behavior': {
                    'scaleUp': {
                        'stabilizationWindowSeconds': 60,
                        'policies': [
                            {'type': 'Percent', 'value': 100, 'periodSeconds': 60},
                            {'type': 'Pods', 'value': 10, 'periodSeconds': 60}
                        ],
                        'selectPolicy': 'Max'
                    },
                    'scaleDown': {
                        'stabilizationWindowSeconds': 300,
                        'policies': [
                            {'type': 'Percent', 'value': 50, 'periodSeconds': 300}
                        ],
                        'selectPolicy': 'Min'
                    }
                }
            }
        }


class GlobalPerformanceOptimizer:
    """Orchestrate all performance optimizations"""

    def __init__(self, cdn_client, redis_client, db_client, monitoring_client):
        self.cdn = GlobalCDNController(cdn_client)
        self.query_cache = QueryCachingStrategy(redis_client)
        self.latency_slo = GlobalLatencySLOController(db_client, monitoring_client)
        self.capacity = CapacityPlanner(db_client)

    async def optimize_all(self) -> Dict:
        """Execute all performance optimizations"""
        logger.info("Executing global performance optimization")

        results = await asyncio.gather(
            self.cdn.configure_cdn_caching(),
            self.capacity.generate_hpa_config(),
            return_exceptions=True
        )

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'optimizations': {
                'cdn_caching': 'success' if not isinstance(results[0], Exception) else 'failed',
                'capacity_planning': 'success' if not isinstance(results[1], Exception) else 'failed'
            }
        }

    async def get_performance_dashboard(self) -> Dict:
        """Get comprehensive performance dashboard"""
        slo_compliance = await self.latency_slo.get_slo_compliance()
        cdn_stats = await self.cdn.get_cdn_stats()

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'latency_slo_compliance': slo_compliance,
            'cdn_performance': cdn_stats,
            'status': 'optimized' if slo_compliance and cdn_stats else 'degraded'
        }
