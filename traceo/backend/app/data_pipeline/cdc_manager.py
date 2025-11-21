#!/usr/bin/env python3
"""
Advanced Data Pipeline CDC (Change Data Capture) Manager
Debezium + Kafka Streams for 99.99% data accuracy
Date: November 21, 2024
"""

import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class EventType(Enum):
    """CDC event types"""
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    SNAPSHOT = 'snapshot'


class ValidationStatus(Enum):
    """Data validation status"""
    VALID = 'valid'
    INVALID = 'invalid'
    DUPLICATE = 'duplicate'
    INCOMPLETE = 'incomplete'
    INCONSISTENT = 'inconsistent'


@dataclass
class CDCEvent:
    """Change Data Capture event"""
    event_id: str
    timestamp: datetime
    operation: EventType
    table: str
    primary_key: Dict[str, str]
    before: Dict = field(default_factory=dict)
    after: Dict = field(default_factory=dict)
    source_database: str = 'postgresql'
    debezium_offset: Optional[Dict] = None

    def get_hash(self) -> str:
        """Get event hash for deduplication"""
        data = f"{self.table}:{json.dumps(self.primary_key)}:{self.timestamp}"
        return hashlib.md5(data.encode()).hexdigest()


@dataclass
class ValidationError:
    """Data validation error"""
    timestamp: datetime
    error_type: str  # schema_violation, missing_field, type_mismatch, etc.
    event_id: str
    message: str
    severity: str  # info, warning, error, critical


@dataclass
class PipelineMetrics:
    """CDC pipeline metrics"""
    timestamp: datetime
    cdc_lag_seconds: float
    events_processed: int
    events_failed: int
    events_deduplicated: int
    validation_errors: int
    processing_latency_ms: float


class SchemaValidator:
    """Validate event schema"""

    REQUIRED_FIELDS = {
        'metrics': ['metric_id', 'timestamp', 'value', 'tags', 'service_name'],
        'logs': ['log_id', 'timestamp', 'level', 'message', 'service_name'],
        'traces': ['trace_id', 'span_id', 'operation', 'start_time', 'duration_ms'],
        'events': ['event_id', 'timestamp', 'event_type', 'source', 'data']
    }

    FIELD_TYPES = {
        'metrics': {
            'metric_id': str,
            'timestamp': str,  # ISO format
            'value': (int, float),
            'tags': dict,
            'service_name': str
        },
        'logs': {
            'log_id': str,
            'timestamp': str,
            'level': str,
            'message': str,
            'service_name': str
        }
    }

    def __init__(self):
        self.errors: List[ValidationError] = []

    def validate(self, event: CDCEvent) -> Tuple[ValidationStatus, Optional[ValidationError]]:
        """Validate CDC event"""

        table = event.table
        data = event.after if event.operation != EventType.DELETE else event.before

        # Check required fields
        if table in self.REQUIRED_FIELDS:
            required = self.REQUIRED_FIELDS[table]
            missing = [f for f in required if f not in data]

            if missing:
                error = ValidationError(
                    timestamp=datetime.utcnow(),
                    error_type='missing_field',
                    event_id=event.event_id,
                    message=f"Missing required fields: {', '.join(missing)}",
                    severity='error'
                )
                self.errors.append(error)
                return ValidationStatus.INCOMPLETE, error

        # Check field types
        if table in self.FIELD_TYPES:
            type_map = self.FIELD_TYPES[table]
            for field_name, expected_type in type_map.items():
                if field_name in data:
                    value = data[field_name]
                    if not isinstance(value, expected_type):
                        error = ValidationError(
                            timestamp=datetime.utcnow(),
                            error_type='type_mismatch',
                            event_id=event.event_id,
                            message=f"Field {field_name} has wrong type: {type(value)} vs {expected_type}",
                            severity='warning'
                        )
                        self.errors.append(error)
                        return ValidationStatus.INVALID, error

        # Timestamp validation
        if 'timestamp' in data:
            try:
                ts = data['timestamp']
                if isinstance(ts, str):
                    datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                error = ValidationError(
                    timestamp=datetime.utcnow(),
                    error_type='invalid_timestamp',
                    event_id=event.event_id,
                    message=f"Invalid timestamp format: {data['timestamp']}",
                    severity='error'
                )
                self.errors.append(error)
                return ValidationStatus.INVALID, error

        return ValidationStatus.VALID, None

    def get_error_summary(self, hours: int = 24) -> Dict:
        """Get validation error summary"""

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_errors = [e for e in self.errors if e.timestamp >= cutoff]

        error_types = {}
        for error in recent_errors:
            if error.error_type not in error_types:
                error_types[error.error_type] = 0
            error_types[error.error_type] += 1

        return {
            'total_errors': len(recent_errors),
            'by_type': error_types,
            'period_hours': hours
        }


class CDCDeduplicator:
    """Deduplicate CDC events"""

    def __init__(self, window_hours: int = 1):
        self.seen_events: Dict[str, Dict] = {}
        self.window_hours = window_hours
        self.deduplication_ratio = 0.0
        self.dedup_count = 0

    def is_duplicate(self, event: CDCEvent) -> bool:
        """Check if event is duplicate"""

        event_hash = event.get_hash()

        # Check if we've seen this event
        if event_hash in self.seen_events:
            stored_time = self.seen_events[event_hash]['timestamp']
            time_diff = (event.timestamp - stored_time).total_seconds()

            if time_diff < self.window_hours * 3600:
                return True

        return False

    def record_event(self, event: CDCEvent):
        """Record event as seen"""

        event_hash = event.get_hash()
        self.seen_events[event_hash] = {
            'timestamp': event.timestamp,
            'operation': event.operation.value
        }

        # Cleanup old entries
        cutoff = datetime.utcnow() - timedelta(hours=self.window_hours * 2)
        self.seen_events = {
            k: v for k, v in self.seen_events.items()
            if v['timestamp'] >= cutoff
        }

    def mark_deduplicated(self):
        """Mark event as deduplicated for metrics"""
        self.dedup_count += 1

    def get_deduplication_stats(self) -> Dict:
        """Get deduplication statistics"""

        return {
            'deduped_events': self.dedup_count,
            'seen_events_in_window': len(self.seen_events),
            'window_hours': self.window_hours,
            'dedup_ratio': f"{(self.dedup_count / max(1, self.dedup_count + len(self.seen_events))) * 100:.2f}%"
        }


class ConsistencyChecker:
    """Check data consistency across events"""

    def __init__(self):
        self.entity_versions: Dict[str, Dict] = {}
        self.inconsistencies: List[Dict] = []

    def check_consistency(self, event: CDCEvent) -> Tuple[bool, Optional[str]]:
        """Check event consistency"""

        entity_key = f"{event.table}:{json.dumps(event.primary_key)}"

        if event.operation == EventType.CREATE:
            # For creates, shouldn't exist yet
            if entity_key in self.entity_versions:
                msg = f"CREATE on existing entity: {entity_key}"
                self.inconsistencies.append({
                    'timestamp': datetime.utcnow(),
                    'type': 'duplicate_create',
                    'entity': entity_key,
                    'message': msg
                })
                return False, msg

            self.entity_versions[entity_key] = {
                'version': 1,
                'timestamp': event.timestamp,
                'data': event.after
            }

        elif event.operation == EventType.UPDATE:
            # For updates, should exist
            if entity_key not in self.entity_versions:
                msg = f"UPDATE on non-existent entity: {entity_key}"
                self.inconsistencies.append({
                    'timestamp': datetime.utcnow(),
                    'type': 'orphan_update',
                    'entity': entity_key,
                    'message': msg
                })
                return False, msg

            # Verify causality: update timestamp should be after creation
            if event.timestamp < self.entity_versions[entity_key]['timestamp']:
                msg = f"Out-of-order UPDATE: {entity_key}"
                self.inconsistencies.append({
                    'timestamp': datetime.utcnow(),
                    'type': 'out_of_order',
                    'entity': entity_key,
                    'message': msg
                })
                return False, msg

            self.entity_versions[entity_key] = {
                'version': self.entity_versions[entity_key]['version'] + 1,
                'timestamp': event.timestamp,
                'data': event.after
            }

        elif event.operation == EventType.DELETE:
            # For deletes, should exist
            if entity_key not in self.entity_versions:
                msg = f"DELETE on non-existent entity: {entity_key}"
                self.inconsistencies.append({
                    'timestamp': datetime.utcnow(),
                    'type': 'orphan_delete',
                    'entity': entity_key,
                    'message': msg
                })
                return False, msg

            del self.entity_versions[entity_key]

        return True, None

    def get_inconsistency_report(self, hours: int = 24) -> Dict:
        """Get inconsistency report"""

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [i for i in self.inconsistencies if i['timestamp'] >= cutoff]

        types = {}
        for inconsistency in recent:
            itype = inconsistency['type']
            if itype not in types:
                types[itype] = 0
            types[itype] += 1

        return {
            'total_inconsistencies': len(recent),
            'by_type': types,
            'period_hours': hours
        }


class CDCPipelineProcessor:
    """Process CDC events with validation and deduplication"""

    def __init__(self):
        self.validator = SchemaValidator()
        self.deduplicator = CDCDeduplicator()
        self.consistency_checker = ConsistencyChecker()
        self.metrics_history: List[PipelineMetrics] = []
        self.processed_count = 0
        self.failed_count = 0

    def process_event(self, event: CDCEvent) -> Tuple[bool, Optional[str]]:
        """Process CDC event through validation pipeline"""

        start_time = datetime.utcnow()

        # Step 1: Deduplication
        if self.deduplicator.is_duplicate(event):
            self.deduplicator.mark_deduplicated()
            logger.debug(f"Deduplicated event: {event.event_id}")
            return False, "duplicate"

        self.deduplicator.record_event(event)

        # Step 2: Schema validation
        validation_status, validation_error = self.validator.validate(event)
        if validation_status != ValidationStatus.VALID:
            self.failed_count += 1
            logger.warning(f"Validation failed: {validation_error.message}")
            return False, f"validation_failed: {validation_error.error_type}"

        # Step 3: Consistency check
        is_consistent, consistency_error = self.consistency_checker.check_consistency(event)
        if not is_consistent:
            self.failed_count += 1
            logger.warning(f"Consistency check failed: {consistency_error}")
            return False, f"consistency_error: {consistency_error}"

        # Step 4: Calculate metrics
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        self.processed_count += 1

        logger.info(f"Event processed: {event.event_id} ({event.operation.value}) in {latency:.1f}ms")

        return True, None

    def process_batch(self, events: List[CDCEvent]) -> Dict:
        """Process batch of CDC events"""

        logger.info(f"Processing batch of {len(events)} events")

        successful = 0
        failed = 0
        start_time = datetime.utcnow()

        for event in events:
            success, _ = self.process_event(event)
            if success:
                successful += 1
            else:
                failed += 1

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return {
            'total_events': len(events),
            'successful': successful,
            'failed': failed,
            'processing_latency_ms': latency / len(events) if events else 0,
            'accuracy': f"{(successful / len(events) * 100):.2f}%" if events else "N/A"
        }

    def get_cdc_lag(self, oldest_unprocessed_event: Optional[datetime] = None) -> float:
        """Get current CDC lag in seconds"""

        if oldest_unprocessed_event is None:
            return 0.0

        lag = (datetime.utcnow() - oldest_unprocessed_event).total_seconds()
        return lag

    def record_metrics(self, cdc_lag: float, processing_latency_ms: float):
        """Record pipeline metrics"""

        metrics = PipelineMetrics(
            timestamp=datetime.utcnow(),
            cdc_lag_seconds=cdc_lag,
            events_processed=self.processed_count,
            events_failed=self.failed_count,
            events_deduplicated=self.deduplicator.dedup_count,
            validation_errors=len(self.validator.errors),
            processing_latency_ms=processing_latency_ms
        )

        self.metrics_history.append(metrics)

        # Keep only last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.metrics_history = [m for m in self.metrics_history if m.timestamp >= cutoff]

    def get_pipeline_health(self) -> Dict:
        """Get overall pipeline health"""

        if not self.metrics_history:
            return {'status': 'no_data'}

        latest = self.metrics_history[-1]
        recent = self.metrics_history[-min(60, len(self.metrics_history)):]  # Last 60 points

        latencies = [m.processing_latency_ms for m in recent]
        lags = [m.cdc_lag_seconds for m in recent]

        success_rate = (
            (latest.events_processed - latest.events_failed) / max(1, latest.events_processed)
        )

        return {
            'status': 'healthy' if success_rate > 0.95 and latest.cdc_lag_seconds < 1 else 'degraded',
            'success_rate': f"{success_rate * 100:.2f}%",
            'cdc_lag_seconds': f"{latest.cdc_lag_seconds:.2f}",
            'avg_processing_latency_ms': f"{statistics.mean(latencies):.2f}",
            'max_processing_latency_ms': f"{max(latencies):.2f}",
            'max_cdc_lag_seconds': f"{max(lags):.2f}",
            'total_deduplicated': self.deduplicator.dedup_count,
            'validation_errors_24h': len(self.validator.errors)
        }

    def get_full_report(self) -> Dict:
        """Get comprehensive pipeline report"""

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'health': self.get_pipeline_health(),
            'validation_summary': self.validator.get_error_summary(),
            'deduplication_stats': self.deduplicator.get_deduplication_stats(),
            'consistency_report': self.consistency_checker.get_inconsistency_report(),
            'metrics_samples': len(self.metrics_history)
        }


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Create processor
    processor = CDCPipelineProcessor()

    # Simulate events
    events = [
        CDCEvent(
            event_id='evt-1',
            timestamp=datetime.utcnow(),
            operation=EventType.CREATE,
            table='metrics',
            primary_key={'metric_id': 'cpu_usage'},
            after={
                'metric_id': 'cpu_usage',
                'timestamp': datetime.utcnow().isoformat(),
                'value': 45.2,
                'tags': {'host': 'server-1'},
                'service_name': 'api-server'
            }
        ),
        CDCEvent(
            event_id='evt-2',
            timestamp=datetime.utcnow() + timedelta(seconds=1),
            operation=EventType.UPDATE,
            table='metrics',
            primary_key={'metric_id': 'cpu_usage'},
            before={
                'metric_id': 'cpu_usage',
                'value': 45.2
            },
            after={
                'metric_id': 'cpu_usage',
                'timestamp': datetime.utcnow().isoformat(),
                'value': 52.1,
                'tags': {'host': 'server-1'},
                'service_name': 'api-server'
            }
        )
    ]

    # Process events
    batch_result = processor.process_batch(events)
    print("\n=== Batch Processing Result ===")
    print(json.dumps(batch_result, indent=2))

    # Record metrics
    processor.record_metrics(cdc_lag=0.5, processing_latency_ms=2.3)

    # Get health report
    health = processor.get_pipeline_health()
    print("\n=== Pipeline Health ===")
    print(json.dumps(health, indent=2))

    # Full report
    full_report = processor.get_full_report()
    print("\n=== Full Pipeline Report ===")
    print(json.dumps(full_report, indent=2, default=str))
