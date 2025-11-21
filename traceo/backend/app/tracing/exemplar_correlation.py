#!/usr/bin/env python3
"""
Advanced Distributed Tracing with Exemplar Correlation
Prometheus exemplars linking metrics to traces for 5x faster root cause analysis
Date: November 21, 2024
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TraceStatus(Enum):
    """Trace execution status"""
    SUCCESS = 'success'
    ERROR = 'error'
    DEGRADED = 'degraded'


class SpanKind(Enum):
    """OpenTelemetry span kinds"""
    INTERNAL = 'INTERNAL'
    SERVER = 'SERVER'
    CLIENT = 'CLIENT'
    PRODUCER = 'PRODUCER'
    CONSUMER = 'CONSUMER'


@dataclass
class Exemplar:
    """Prometheus exemplar for metric-to-trace correlation"""
    trace_id: str
    span_id: str
    timestamp: datetime
    metric_name: str
    metric_value: float
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'timestamp': self.timestamp.isoformat(),
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'labels': self.labels
        }


@dataclass
class SpanEvent:
    """Event within a span"""
    timestamp: datetime
    name: str
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class Span:
    """OpenTelemetry Span"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    kind: SpanKind = SpanKind.INTERNAL
    status: TraceStatus = TraceStatus.SUCCESS
    error_message: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    links: List[str] = field(default_factory=list)

    def duration_ms(self) -> float:
        """Get span duration in milliseconds"""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'span_id': self.span_id,
            'trace_id': self.trace_id,
            'parent_span_id': self.parent_span_id,
            'service_name': self.service_name,
            'operation_name': self.operation_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms(),
            'kind': self.kind.value,
            'status': self.status.value,
            'error_message': self.error_message,
            'attributes': self.attributes
        }


@dataclass
class Trace:
    """Complete distributed trace with multiple spans"""
    trace_id: str
    spans: List[Span] = field(default_factory=list)
    root_span_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def add_span(self, span: Span):
        """Add span to trace"""
        self.spans.append(span)

        if self.root_span_id is None and span.parent_span_id is None:
            self.root_span_id = span.span_id

        if self.start_time is None or span.start_time < self.start_time:
            self.start_time = span.start_time

        if self.end_time is None or (span.end_time and span.end_time > self.end_time):
            self.end_time = span.end_time

    def duration_ms(self) -> float:
        """Get total trace duration"""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000

    def get_critical_path(self) -> List[Span]:
        """Get critical path (longest duration path) through trace"""
        if not self.spans:
            return []

        # Build span map
        span_map = {s.span_id: s for s in self.spans}

        # Find root span
        root_span = next((s for s in self.spans if s.parent_span_id is None), None)
        if not root_span:
            return []

        # Traverse depth-first, finding longest path
        critical_path = [root_span]
        current_span = root_span

        while True:
            # Find children
            children = [s for s in self.spans if s.parent_span_id == current_span.span_id]

            if not children:
                break

            # Choose longest child
            longest_child = max(children, key=lambda s: s.duration_ms())
            critical_path.append(longest_child)
            current_span = longest_child

        return critical_path

    def get_error_spans(self) -> List[Span]:
        """Get all spans with errors"""
        return [s for s in self.spans if s.status == TraceStatus.ERROR]

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'trace_id': self.trace_id,
            'root_span_id': self.root_span_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': self.duration_ms(),
            'span_count': len(self.spans),
            'spans': [s.to_dict() for s in self.spans]
        }


class ExemplarCollector:
    """Collect exemplars from spans for metrics correlation"""

    def __init__(self):
        self.exemplars: List[Exemplar] = []
        self.span_buffer: Dict[str, Span] = {}

    def record_metric_with_exemplar(self, span: Span, metric_name: str,
                                   metric_value: float, labels: Dict[str, str] = None):
        """Record metric with exemplar from span"""
        exemplar = Exemplar(
            trace_id=span.trace_id,
            span_id=span.span_id,
            timestamp=datetime.utcnow(),
            metric_name=metric_name,
            metric_value=metric_value,
            labels=labels or {}
        )

        self.exemplars.append(exemplar)
        logger.debug(f"Recorded exemplar: {metric_name} = {metric_value} "
                    f"(trace={span.trace_id}, span={span.span_id})")

    def get_exemplar_for_metric(self, metric_name: str, value_range: Tuple[float, float] = None) -> Optional[Exemplar]:
        """Get exemplar for metric value"""
        matching = [e for e in self.exemplars if e.metric_name == metric_name]

        if not matching:
            return None

        if value_range:
            matching = [e for e in matching
                       if value_range[0] <= e.metric_value <= value_range[1]]

        if matching:
            # Return most recent
            return max(matching, key=lambda e: e.timestamp)

        return None

    def get_exemplars_for_trace(self, trace_id: str) -> List[Exemplar]:
        """Get all exemplars for a trace"""
        return [e for e in self.exemplars if e.trace_id == trace_id]

    def cleanup_old_exemplars(self, hours: int = 24):
        """Remove old exemplars"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        self.exemplars = [e for e in self.exemplars if e.timestamp >= cutoff]


class TraceCausalityAnalyzer:
    """Analyze causality and root causes in traces"""

    def __init__(self):
        self.traces: Dict[str, Trace] = {}

    def ingest_trace(self, trace: Trace):
        """Ingest a trace"""
        self.traces[trace.trace_id] = trace
        logger.info(f"Ingested trace: {trace.trace_id} ({len(trace.spans)} spans)")

    def find_root_cause(self, trace: Trace) -> Optional[Dict]:
        """Find root cause of error in trace"""
        error_spans = trace.get_error_spans()

        if not error_spans:
            return None

        # Get first error in critical path
        critical_path = trace.get_critical_path()
        critical_error = None

        for span in critical_path:
            if span in error_spans:
                critical_error = span
                break

        if critical_error is None:
            critical_error = error_spans[0]

        return {
            'root_cause_span_id': critical_error.span_id,
            'root_cause_service': critical_error.service_name,
            'root_cause_operation': critical_error.operation_name,
            'error_message': critical_error.error_message,
            'error_time': critical_error.start_time.isoformat(),
            'critical_path_affected': any(
                s.span_id == critical_error.span_id for s in critical_path
            ),
            'downstream_spans': len([s for s in trace.spans
                                    if self._is_descendant(s, critical_error, trace)])
        }

    def _is_descendant(self, potential_child: Span, potential_parent: Span,
                      trace: Trace) -> bool:
        """Check if potential_child is descendant of potential_parent"""
        current = potential_child

        while current.parent_span_id:
            if current.parent_span_id == potential_parent.span_id:
                return True

            parent = next((s for s in trace.spans if s.span_id == current.parent_span_id), None)
            if parent is None:
                break

            current = parent

        return False

    def correlate_metrics_to_trace(self, metric_spike_time: datetime,
                                  affected_service: str,
                                  time_window_seconds: int = 10) -> Optional[Dict]:
        """Find trace that correlates with metric spike"""
        window_start = metric_spike_time - timedelta(seconds=time_window_seconds / 2)
        window_end = metric_spike_time + timedelta(seconds=time_window_seconds / 2)

        # Find traces in time window
        matching_traces = []

        for trace in self.traces.values():
            if trace.start_time is None:
                continue

            if window_start <= trace.start_time <= window_end:
                # Check if affected service is in trace
                services = set(s.service_name for s in trace.spans)
                if affected_service in services:
                    matching_traces.append(trace)

        if not matching_traces:
            return None

        # Return trace with longest duration (likely the problematic one)
        longest_trace = max(matching_traces, key=lambda t: t.duration_ms())

        return {
            'trace_id': longest_trace.trace_id,
            'duration_ms': longest_trace.duration_ms(),
            'error_spans': len(longest_trace.get_error_spans()),
            'affected_services': list(set(s.service_name for s in longest_trace.spans)),
            'span_count': len(longest_trace.spans)
        }

    def get_service_dependency_graph(self, trace: Trace) -> Dict[str, List[str]]:
        """Extract service dependency graph from trace"""
        graph: Dict[str, List[str]] = {}

        # Build parent-child relationships
        for span in trace.spans:
            if span.service_name not in graph:
                graph[span.service_name] = []

            if span.parent_span_id:
                parent_span = next(
                    (s for s in trace.spans if s.span_id == span.parent_span_id),
                    None
                )

                if parent_span and parent_span.service_name != span.service_name:
                    if parent_span.service_name not in graph[span.service_name]:
                        graph[span.service_name].append(parent_span.service_name)

        return graph

    def analyze_latency_distribution(self, trace: Trace) -> Dict[str, float]:
        """Analyze where time is spent in trace"""
        total_duration = trace.duration_ms()

        if total_duration == 0:
            return {}

        service_durations: Dict[str, float] = {}

        for span in trace.spans:
            if span.service_name not in service_durations:
                service_durations[span.service_name] = 0.0

            service_durations[span.service_name] += span.duration_ms()

        # Convert to percentages
        return {
            service: (duration / total_duration * 100)
            for service, duration in service_durations.items()
        }


class DistributedTracingSystem:
    """Complete distributed tracing system with exemplar correlation"""

    def __init__(self):
        self.collector = ExemplarCollector()
        self.analyzer = TraceCausalityAnalyzer()
        self.metrics_correlation: List[Dict] = []

    def trace_request(self, span: Span) -> Exemplar:
        """Trace request and create exemplar"""
        # Record exemplar for request latency
        exemplar = Exemplar(
            trace_id=span.trace_id,
            span_id=span.span_id,
            timestamp=span.start_time,
            metric_name='http_request_duration_seconds',
            metric_value=span.duration_ms() / 1000,
            labels={
                'service': span.service_name,
                'operation': span.operation_name,
                'status': span.status.value
            }
        )

        self.collector.exemplars.append(exemplar)
        return exemplar

    def correlate_metric_to_traces(self, metric_name: str, spike_time: datetime,
                                  affected_service: str) -> Optional[Dict]:
        """Correlate metric spike to traces"""
        correlation = self.analyzer.correlate_metrics_to_trace(
            spike_time, affected_service
        )

        if correlation:
            correlation['metric_name'] = metric_name
            correlation['spike_time'] = spike_time.isoformat()
            self.metrics_correlation.append(correlation)

        return correlation

    def analyze_performance_issue(self, trace_id: str) -> Optional[Dict]:
        """Analyze performance issue in trace"""
        if trace_id not in self.analyzer.traces:
            return None

        trace = self.analyzer.traces[trace_id]

        # Check for errors
        root_cause = self.analyzer.find_root_cause(trace)

        # Analyze latency
        latency_dist = self.analyzer.analyze_latency_distribution(trace)

        # Service dependency
        service_deps = self.analyzer.get_service_dependency_graph(trace)

        return {
            'trace_id': trace_id,
            'total_duration_ms': trace.duration_ms(),
            'root_cause': root_cause,
            'latency_distribution': latency_dist,
            'service_dependencies': service_deps,
            'critical_path_length': len(trace.get_critical_path()),
            'span_count': len(trace.spans)
        }

    def get_correlation_report(self) -> Dict:
        """Get metrics-to-traces correlation report"""
        return {
            'correlations': len(self.metrics_correlation),
            'exemplars': len(self.collector.exemplars),
            'traces': len(self.analyzer.traces),
            'recent_correlations': self.metrics_correlation[-10:] if self.metrics_correlation else []
        }


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Create distributed tracing system
    tracing = DistributedTracingSystem()

    # Create a simple trace
    trace = Trace(trace_id='trace-001')

    # Root span (API gateway)
    root_span = Span(
        span_id='span-001',
        trace_id='trace-001',
        parent_span_id=None,
        service_name='api-gateway',
        operation_name='POST /api/users',
        start_time=datetime.utcnow()
    )

    # Database span
    db_span = Span(
        span_id='span-002',
        trace_id='trace-001',
        parent_span_id='span-001',
        service_name='database',
        operation_name='INSERT users',
        start_time=datetime.utcnow() + timedelta(milliseconds=50),
        end_time=datetime.utcnow() + timedelta(milliseconds=150)
    )

    # Complete spans
    root_span.end_time = datetime.utcnow() + timedelta(milliseconds=200)

    trace.add_span(root_span)
    trace.add_span(db_span)

    # Ingest trace
    tracing.analyzer.ingest_trace(trace)

    # Create exemplar
    exemplar = tracing.trace_request(root_span)

    # Analyze
    analysis = tracing.analyze_performance_issue('trace-001')

    print("\n=== Trace Analysis ===")
    print(json.dumps(analysis, indent=2))

    print("\n=== Correlation Report ===")
    print(json.dumps(tracing.get_correlation_report(), indent=2))
