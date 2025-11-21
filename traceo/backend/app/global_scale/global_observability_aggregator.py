#!/usr/bin/env python3
"""
Global Observability Aggregator
Distributed tracing across 7 regions, cross-region correlation, global metrics
Date: November 21, 2024
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class Span:
    """Distributed trace span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service: str
    region: str
    operation: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: str  # success, error
    error_message: Optional[str] = None
    tags: Dict = field(default_factory=dict)


@dataclass
class Trace:
    """Complete distributed trace across regions"""
    trace_id: str
    spans: List[Span]
    root_service: str
    all_services: Set[str]
    all_regions: Set[str]
    start_time: datetime
    end_time: datetime
    total_duration_ms: float
    critical_path_duration_ms: float
    error: bool
    error_count: int


class DistributedTracingAggregator:
    """Aggregate traces from 7 global regions"""

    REGIONS = [
        'eu-frankfurt',
        'cn-beijing',
        'ap-mumbai',
        'ap-tokyo',
        'ap-singapore',
        'us-virginia',
        'sa-sao-paulo'
    ]

    def __init__(self, jaeger_client, db_client):
        self.jaeger = jaeger_client
        self.db = db_client
        self.local_spans: Dict[str, List[Span]] = {}  # trace_id -> spans
        self.assembled_traces: Dict[str, Trace] = {}

    async def collect_spans_from_regions(self, trace_id: str) -> List[Span]:
        """Collect spans for a trace from all regions"""
        all_spans = []

        # Collect from all regions in parallel
        collect_tasks = [
            self._collect_spans_from_region(trace_id, region)
            for region in self.REGIONS
        ]

        region_spans = await asyncio.gather(*collect_tasks, return_exceptions=True)

        for spans in region_spans:
            if isinstance(spans, list):
                all_spans.extend(spans)
            elif isinstance(spans, Exception):
                logger.warning(f"Failed to collect spans from region: {str(spans)}")

        # Store spans
        self.local_spans[trace_id] = all_spans

        return all_spans

    async def _collect_spans_from_region(self, trace_id: str, region: str) -> List[Span]:
        """Collect spans from specific region"""
        try:
            # Query Jaeger collector in region
            spans_data = await self.jaeger.get_trace_by_region(trace_id, region)

            spans = []
            for span_data in spans_data:
                span = Span(
                    trace_id=span_data['traceID'],
                    span_id=span_data['spanID'],
                    parent_span_id=span_data.get('parentSpanID'),
                    service=span_data['process']['serviceName'],
                    region=region,
                    operation=span_data['operationName'],
                    start_time=datetime.fromtimestamp(span_data['startTime'] / 1_000_000),
                    end_time=datetime.fromtimestamp(
                        (span_data['startTime'] + span_data['duration']) / 1_000_000
                    ),
                    duration_ms=(span_data['duration'] / 1000),
                    status='error' if any(tag['value'] == 'error' for tag in span_data.get('tags', [])
                                         if tag['key'] == 'error') else 'success',
                    error_message=next(
                        (tag['value'] for tag in span_data.get('tags', []) if tag['key'] == 'error.message'),
                        None
                    ),
                    tags={tag['key']: tag['value'] for tag in span_data.get('tags', [])}
                )
                spans.append(span)

            logger.debug(f"Collected {len(spans)} spans for trace {trace_id} from {region}")
            return spans

        except Exception as e:
            logger.error(f"Failed to collect spans from {region}: {str(e)}")
            return []

    async def correlate_cross_region_spans(self, trace_id: str) -> Trace:
        """Correlate spans across regions into single trace"""
        if trace_id not in self.local_spans:
            raise ValueError(f"Trace {trace_id} not found in local spans")

        spans = self.local_spans[trace_id]
        if not spans:
            raise ValueError(f"No spans collected for trace {trace_id}")

        # Sort spans by start time
        sorted_spans = sorted(spans, key=lambda s: s.start_time)

        # Build parent-child relationships
        span_map = {span.span_id: span for span in sorted_spans}
        for span in sorted_spans:
            if span.parent_span_id and span.parent_span_id in span_map:
                parent = span_map[span.parent_span_id]
                # Update parent span tags with child region info
                parent.tags['child_regions'] = parent.tags.get('child_regions', [])
                if span.region not in parent.tags['child_regions']:
                    parent.tags['child_regions'].append(span.region)

        # Calculate critical path (longest duration chain)
        critical_path_ms = await self._calculate_critical_path(sorted_spans)

        # Determine trace status
        has_error = any(span.status == 'error' for span in sorted_spans)
        error_count = sum(1 for span in sorted_spans if span.status == 'error')

        trace = Trace(
            trace_id=trace_id,
            spans=sorted_spans,
            root_service=sorted_spans[0].service if sorted_spans else 'unknown',
            all_services={span.service for span in sorted_spans},
            all_regions={span.region for span in sorted_spans},
            start_time=sorted_spans[0].start_time,
            end_time=sorted_spans[-1].end_time,
            total_duration_ms=sum(span.duration_ms for span in sorted_spans),
            critical_path_duration_ms=critical_path_ms,
            error=has_error,
            error_count=error_count
        )

        self.assembled_traces[trace_id] = trace

        # Store trace
        await self.db.insert('assembled_traces', {
            'trace_id': trace_id,
            'timestamp': datetime.utcnow(),
            'services': list(trace.all_services),
            'regions': list(trace.all_regions),
            'duration_ms': trace.total_duration_ms,
            'critical_path_ms': trace.critical_path_duration_ms,
            'error': trace.error,
            'span_count': len(trace.spans)
        })

        return trace

    async def _calculate_critical_path(self, spans: List[Span]) -> float:
        """Calculate longest chain duration (critical path)"""
        if not spans:
            return 0.0

        # Build span tree
        span_map = {span.span_id: span for span in spans}
        root_spans = [s for s in spans if s.parent_span_id not in span_map]

        max_duration = 0.0
        for root in root_spans:
            duration = await self._trace_critical_path(root, span_map)
            max_duration = max(max_duration, duration)

        return max_duration

    async def _trace_critical_path(self, span: Span, span_map: Dict[str, Span]) -> float:
        """Recursively trace longest path from span"""
        # Find children
        children = [s for s in span_map.values() if s.parent_span_id == span.span_id]

        if not children:
            return span.duration_ms

        # Get max path from children
        max_child_duration = 0.0
        for child in children:
            child_duration = await self._trace_critical_path(child, span_map)
            max_child_duration = max(max_child_duration, child_duration)

        return span.duration_ms + max_child_duration

    async def identify_latency_bottlenecks(self, trace_id: str) -> List[Dict]:
        """Identify spans causing latency"""
        if trace_id not in self.assembled_traces:
            raise ValueError(f"Trace {trace_id} not found")

        trace = self.assembled_traces[trace_id]

        # Sort by duration
        sorted_spans = sorted(trace.spans, key=lambda s: s.duration_ms, reverse=True)

        bottlenecks = []
        for span in sorted_spans[:10]:  # Top 10 slowest spans
            bottleneck = {
                'service': span.service,
                'region': span.region,
                'operation': span.operation,
                'duration_ms': span.duration_ms,
                'percentage_of_total': (span.duration_ms / trace.total_duration_ms) * 100,
                'status': span.status,
                'error': span.error_message if span.status == 'error' else None
            }
            bottlenecks.append(bottleneck)

        return bottlenecks


class GlobalMetricsAggregator:
    """Aggregate metrics from all regions in real-time"""

    def __init__(self, mimir_client, db_client):
        self.mimir = mimir_client
        self.db = db_client
        self.last_aggregation: Optional[datetime] = None

    async def aggregate_metrics(self) -> Dict:
        """Aggregate metrics from all regions"""
        start_time = datetime.utcnow()
        regions = [
            'eu-frankfurt',
            'cn-beijing',
            'ap-mumbai',
            'ap-tokyo',
            'ap-singapore',
            'us-virginia',
            'sa-sao-paulo'
        ]

        # Collect metrics from all regions in parallel
        collect_tasks = [
            self.mimir.query_range(
                query='up',  # Get all metrics
                start=start_time - timedelta(minutes=5),
                end=start_time,
                step='1m',
                matchers={'region': region}
            )
            for region in regions
        ]

        results = await asyncio.gather(*collect_tasks, return_exceptions=True)

        # Process and deduplicate
        aggregated_metrics = {}
        for region_idx, region_metrics in enumerate(results):
            if isinstance(region_metrics, Exception):
                logger.warning(f"Failed to collect metrics from region: {str(region_metrics)}")
                continue

            region = regions[region_idx]
            for metric in region_metrics:
                metric_key = metric.get('metric', {}).get('__name__', '')
                if metric_key not in aggregated_metrics:
                    aggregated_metrics[metric_key] = {
                        'values': [],
                        'regions': set()
                    }

                aggregated_metrics[metric_key]['values'].append({
                    'region': region,
                    'value': metric.get('value', 0),
                    'timestamp': metric.get('timestamp')
                })
                aggregated_metrics[metric_key]['regions'].add(region)

        self.last_aggregation = datetime.utcnow()
        aggregation_duration = (self.last_aggregation - start_time).total_seconds() * 1000

        logger.info(f"Aggregated metrics from {len(regions)} regions in {aggregation_duration:.1f}ms")

        return {
            'timestamp': self.last_aggregation.isoformat(),
            'aggregation_duration_ms': aggregation_duration,
            'metrics_count': len(aggregated_metrics),
            'regions_sampled': len(regions),
            'deduplication_rate': self._calculate_deduplication_rate(aggregated_metrics)
        }

    def _calculate_deduplication_rate(self, metrics: Dict) -> float:
        """Calculate deduplication rate (should be ~2x for 3-way replication)"""
        total_values = sum(len(m['values']) for m in metrics.values())
        unique_metrics = len(metrics) * 7  # 7 regions

        if unique_metrics == 0:
            return 0.0

        return (1 - (total_values / (unique_metrics * 3))) * 100  # 3-way replication expected

    async def get_global_dashboard_data(self, time_range: str = '1h') -> Dict:
        """Get global metrics dashboard data"""
        # Parse time range
        if time_range == '1h':
            start = datetime.utcnow() - timedelta(hours=1)
        elif time_range == '24h':
            start = datetime.utcnow() - timedelta(hours=24)
        else:
            start = datetime.utcnow() - timedelta(hours=1)

        end = datetime.utcnow()

        # Aggregate across all regions
        global_metrics = await self.mimir.query_range(
            query="""
                sum(rate(metrics_ingested_total[5m])) by (region)
            """,
            start=start,
            end=end,
            step='5m'
        )

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'time_range': time_range,
            'metrics_by_region': global_metrics,
            'total_mps': sum(m.get('value', 0) for m in global_metrics),
            'regions_reporting': len(set(m.get('region') for m in global_metrics if m.get('region')))
        }


class MultiRegionAlertingController:
    """Manage alerting across global regions"""

    def __init__(self, alertmanager_client, db_client):
        self.alertmanager = alertmanager_client
        self.db = db_client

    async def route_alerts_by_region(self, alert: Dict) -> Dict:
        """Route alert to appropriate region handlers"""
        alert_region = alert.get('labels', {}).get('region')
        alert_severity = alert.get('labels', {}).get('severity', 'warning')

        routing_config = {
            'eu-frankfurt': {
                'receiver': 'eu-on-call',
                'group_wait': '30s',
                'group_interval': '5m',
                'repeat_interval': '4h'
            },
            'cn-beijing': {
                'receiver': 'cn-on-call',
                'group_wait': '30s',
                'group_interval': '5m',
                'repeat_interval': '4h'
            },
            'us-virginia': {
                'receiver': 'us-on-call',
                'group_wait': '30s',
                'group_interval': '5m',
                'repeat_interval': '4h'
            }
        }

        # Critical alerts escalate immediately
        if alert_severity == 'critical':
            routing_config[alert_region]['group_wait'] = '0s'
            routing_config[alert_region]['escalation'] = True

        return routing_config.get(alert_region, routing_config['us-virginia'])

    async def create_alerting_policy(self) -> Dict:
        """Create global alerting policy"""
        return {
            'apiVersion': 'monitoring.coreos.com/v1',
            'kind': 'PrometheusRule',
            'metadata': {
                'name': 'global-sla-alerts',
                'namespace': 'monitoring'
            },
            'spec': {
                'groups': [
                    {
                        'name': 'regional.rules',
                        'interval': '30s',
                        'rules': [
                            {
                                'alert': 'RegionalAvailabilityLow',
                                'expr': 'up{region="us-virginia"} == 0',
                                'for': '1m',
                                'annotations': {
                                    'summary': 'US Virginia region unavailable'
                                }
                            },
                            {
                                'alert': 'ReplicationLagHigh',
                                'expr': 'replication_lag_seconds > 60',
                                'for': '5m',
                                'annotations': {
                                    'summary': 'Replication lag exceeds SLO'
                                }
                            },
                            {
                                'alert': 'LatencySLOViolation',
                                'expr': 'histogram_quantile(0.95, request_duration_ms) > 500',
                                'for': '2m',
                                'annotations': {
                                    'summary': 'Global latency SLO violated'
                                }
                            }
                        ]
                    }
                ]
            }
        }


class GlobalObservabilityAggregator:
    """Orchestrate global observability"""

    def __init__(self, jaeger_client, mimir_client, alertmanager_client, db_client):
        self.tracing = DistributedTracingAggregator(jaeger_client, db_client)
        self.metrics = GlobalMetricsAggregator(mimir_client, db_client)
        self.alerting = MultiRegionAlertingController(alertmanager_client, db_client)
        self.db = db_client

    async def analyze_request_flow(self, trace_id: str) -> Dict:
        """Analyze complete request flow across regions"""
        # Collect spans from all regions
        spans = await self.tracing.collect_spans_from_regions(trace_id)

        # Correlate spans
        trace = await self.tracing.correlate_cross_region_spans(trace_id)

        # Identify bottlenecks
        bottlenecks = await self.tracing.identify_latency_bottlenecks(trace_id)

        # Get metrics for same period
        metrics = await self.metrics.get_global_dashboard_data('1h')

        return {
            'trace_id': trace_id,
            'services': list(trace.all_services),
            'regions': list(trace.all_regions),
            'total_duration_ms': trace.total_duration_ms,
            'critical_path_ms': trace.critical_path_duration_ms,
            'error': trace.error,
            'error_count': trace.error_count,
            'bottlenecks': bottlenecks[:5],  # Top 5 bottlenecks
            'span_count': len(trace.spans)
        }

    async def get_global_observability_dashboard(self) -> Dict:
        """Comprehensive global observability dashboard"""
        # Get metrics
        metrics = await self.metrics.get_global_dashboard_data()

        # Get trace statistics
        trace_stats = await self.db.query(f"""
            SELECT
                COUNT(*) as total_traces,
                SUM(CASE WHEN error = true THEN 1 ELSE 0 END) as error_traces,
                AVG(duration_ms) as avg_duration_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
                COUNT(DISTINCT services) as service_count,
                COUNT(DISTINCT regions) as region_count
            FROM assembled_traces
            WHERE timestamp > NOW() - INTERVAL '1 hour'
        """)

        dashboard = {
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': metrics,
            'traces': {
                'total_1h': trace_stats[0]['total_traces'] if trace_stats else 0,
                'error_traces_1h': trace_stats[0]['error_traces'] if trace_stats else 0,
                'error_rate_percent': (
                    (trace_stats[0]['error_traces'] / max(1, trace_stats[0]['total_traces']) * 100)
                    if trace_stats else 0
                ),
                'avg_duration_ms': trace_stats[0]['avg_duration_ms'] if trace_stats else 0,
                'p95_duration_ms': trace_stats[0]['p95_duration_ms'] if trace_stats else 0,
                'services': trace_stats[0]['service_count'] if trace_stats else 0,
                'regions': trace_stats[0]['region_count'] if trace_stats else 0
            },
            'health_status': 'healthy' if trace_stats and trace_stats[0]['error_traces'] < (trace_stats[0]['total_traces'] * 0.01) else 'degraded'
        }

        return dashboard
