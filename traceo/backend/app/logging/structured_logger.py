#!/usr/bin/env python3
"""
Advanced Structured Logging System
Semantic logging with automatic PII/secret detection and redaction
Date: November 21, 2024
"""

import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import traceback

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Structured log levels"""
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


class PIIType(Enum):
    """Types of personally identifiable information"""
    EMAIL = 'email'
    CREDIT_CARD = 'credit_card'
    SSN = 'ssn'
    PHONE = 'phone'
    API_KEY = 'api_key'
    JWT = 'jwt'
    PASSWORD = 'password'
    DATABASE_URL = 'database_url'
    PRIVATE_KEY = 'private_key'
    IP_ADDRESS = 'ip_address'
    OAUTH_TOKEN = 'oauth_token'


@dataclass
class PIIDetection:
    """Record of detected PII"""
    timestamp: datetime
    pii_type: PIIType
    field_name: str
    original_value: str
    redacted_value: str
    confidence: float  # 0-1
    context: str = ""


@dataclass
class LogRecord:
    """Structured log record"""
    timestamp: datetime
    level: LogLevel
    service: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Dict] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    pii_detections: List[PIIDetection] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'service': self.service,
            'message': self.message,
            'context': self.context,
            'error': self.error,
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'pii_detected': len(self.pii_detections) > 0,
            'pii_count': len(self.pii_detections)
        }


class PIIDetector:
    """Detect and redact PII and secrets"""

    # Patterns for various sensitive data
    PATTERNS = {
        PIIType.EMAIL: {
            'pattern': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'confidence': 0.95
        },
        PIIType.CREDIT_CARD: {
            'pattern': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            'confidence': 0.90
        },
        PIIType.SSN: {
            'pattern': r'\b\d{3}-\d{2}-\d{4}\b',
            'confidence': 0.99
        },
        PIIType.PHONE: {
            'pattern': r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
            'confidence': 0.85
        },
        PIIType.API_KEY: {
            'pattern': r'(?:api[_-]?key|apikey)["\']?[:=\s]+["\']?[a-zA-Z0-9_\-]{20,}["\']?',
            'confidence': 0.92
        },
        PIIType.JWT: {
            'pattern': r'eyJ[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*',
            'confidence': 0.98
        },
        PIIType.PASSWORD: {
            'pattern': r'(?:password|passwd|pwd)["\']?[:=\s]+["\']?[^\s"\']*["\']?',
            'confidence': 0.88
        },
        PIIType.DATABASE_URL: {
            'pattern': r'(?:postgresql|mysql|mongodb|postgres)://[^\s\'"`]+',
            'confidence': 0.95
        },
        PIIType.OAUTH_TOKEN: {
            'pattern': r'(?:access_token|refresh_token|bearer)["\']?[:=\s]+["\']?[a-zA-Z0-9_\-\.]+["\']?',
            'confidence': 0.90
        },
        PIIType.IP_ADDRESS: {
            'pattern': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            'confidence': 0.70
        }
    }

    def __init__(self):
        self.compiled_patterns = {
            pii_type: {
                'regex': re.compile(pattern['pattern'], re.IGNORECASE),
                'confidence': pattern['confidence']
            }
            for pii_type, pattern in self.PATTERNS.items()
        }
        self.detections: List[PIIDetection] = []

    def detect(self, text: str, field_name: str = 'unknown') -> List[PIIDetection]:
        """Detect PII in text"""
        detections = []

        for pii_type, compiled_info in self.compiled_patterns.items():
            pattern = compiled_info['regex']
            confidence = compiled_info['confidence']

            matches = pattern.finditer(str(text))

            for match in matches:
                detection = PIIDetection(
                    timestamp=datetime.utcnow(),
                    pii_type=pii_type,
                    field_name=field_name,
                    original_value=match.group(),
                    redacted_value=self._mask_value(match.group(), pii_type),
                    confidence=confidence,
                    context=text[:max(0, match.start()-20):match.start()+20]
                )

                detections.append(detection)

            self.detections.extend(detections)

        return detections

    def redact(self, text: str, field_name: str = 'unknown') -> Tuple[str, List[PIIDetection]]:
        """Redact PII from text"""
        if text is None:
            return None, []

        detections = self.detect(text, field_name)
        redacted = text

        # Sort by position (reverse) to maintain correct indices
        sorted_detections = sorted(detections, key=lambda d: d.original_value, reverse=True)

        for detection in sorted_detections:
            redacted = redacted.replace(detection.original_value, detection.redacted_value)

        return redacted, detections

    def _mask_value(self, value: str, pii_type: PIIType) -> str:
        """Generate masked value for PII"""
        if pii_type == PIIType.EMAIL:
            parts = value.split('@')
            return f"{parts[0][0]}***@{parts[1]}" if len(parts) > 1 else "***@***"

        elif pii_type == PIIType.CREDIT_CARD:
            return f"****-****-****-{value[-4:]}"

        elif pii_type == PIIType.SSN:
            return "***-**-****"

        elif pii_type == PIIType.PHONE:
            return "***-***-****"

        elif pii_type == PIIType.API_KEY:
            return f"{value[:6]}...{value[-4:]}" if len(value) > 10 else "[API_KEY]"

        elif pii_type == PIIType.JWT:
            return "[JWT_TOKEN]"

        elif pii_type == PIIType.PASSWORD:
            return "[PASSWORD]"

        elif pii_type == PIIType.DATABASE_URL:
            # Extract host part
            match = re.search(r'://([^:@/]+)', value)
            host = match.group(1) if match else "***"
            return f"[DATABASE_URL:{host}]"

        elif pii_type == PIIType.OAUTH_TOKEN:
            return "[OAUTH_TOKEN]"

        elif pii_type == PIIType.IP_ADDRESS:
            # Return partially masked IP
            parts = value.split('.')
            return f"{parts[0]}.{parts[1]}.***.***.***" if len(parts) == 4 else "[IP_ADDRESS]"

        elif pii_type == PIIType.PRIVATE_KEY:
            return "[PRIVATE_KEY]"

        else:
            return "[REDACTED]"

    def get_detection_summary(self, hours: int = 24) -> Dict:
        """Get PII detection summary"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [d for d in self.detections if d.timestamp >= cutoff]

        by_type = {}
        by_field = {}

        for detection in recent:
            pii_type = detection.pii_type.value
            field = detection.field_name

            if pii_type not in by_type:
                by_type[pii_type] = 0
            if field not in by_field:
                by_field[field] = 0

            by_type[pii_type] += 1
            by_field[field] += 1

        return {
            'period_hours': hours,
            'total_detections': len(recent),
            'by_type': by_type,
            'by_field': by_field,
            'high_confidence': sum(1 for d in recent if d.confidence > 0.90)
        }


class StructuredLogger:
    """Advanced structured logging with PII detection"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.detector = PIIDetector()
        self.log_buffer: List[LogRecord] = []
        self.handler = logging.StreamHandler()
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger = logging.getLogger(f'{service_name}')
        self.logger.addHandler(self.handler)

    def _build_log_record(self, level: LogLevel, message: str,
                         context: Dict[str, Any] = None,
                         trace_id: Optional[str] = None,
                         span_id: Optional[str] = None) -> LogRecord:
        """Build structured log record"""
        context = context or {}

        # Redact context values
        redacted_context = {}
        pii_detections = []

        for key, value in context.items():
            if isinstance(value, str):
                redacted_value, detections = self.detector.redact(value, field_name=key)
                redacted_context[key] = redacted_value
                pii_detections.extend(detections)
            else:
                redacted_context[key] = value

        # Redact message
        redacted_message, msg_detections = self.detector.redact(message)
        pii_detections.extend(msg_detections)

        record = LogRecord(
            timestamp=datetime.utcnow(),
            level=level,
            service=self.service_name,
            message=redacted_message,
            context=redacted_context,
            trace_id=trace_id,
            span_id=span_id,
            pii_detections=pii_detections
        )

        return record

    def info(self, message: str, **kwargs):
        """Log info level"""
        record = self._build_log_record(LogLevel.INFO, message, kwargs)
        self._emit(record)

    def warning(self, message: str, **kwargs):
        """Log warning level"""
        record = self._build_log_record(LogLevel.WARNING, message, kwargs)
        self._emit(record)

    def error(self, message: str, exception: Exception = None, **kwargs):
        """Log error level"""
        error_dict = None

        if exception:
            error_dict = {
                'type': type(exception).__name__,
                'message': str(exception),
                'traceback': traceback.format_exc()
            }

        record = self._build_log_record(LogLevel.ERROR, message, kwargs)
        record.error = error_dict
        self._emit(record)

    def debug(self, message: str, **kwargs):
        """Log debug level"""
        record = self._build_log_record(LogLevel.DEBUG, message, kwargs)
        self._emit(record)

    def critical(self, message: str, exception: Exception = None, **kwargs):
        """Log critical level"""
        error_dict = None

        if exception:
            error_dict = {
                'type': type(exception).__name__,
                'message': str(exception)
            }

        record = self._build_log_record(LogLevel.CRITICAL, message, kwargs)
        record.error = error_dict
        self._emit(record)

    def _emit(self, record: LogRecord):
        """Emit log record"""
        self.log_buffer.append(record)

        # Convert to JSON
        json_output = json.dumps(record.to_dict())
        self.logger.log(getattr(logging, record.level.value), json_output)

    def get_logs(self, hours: int = 24, level: Optional[LogLevel] = None) -> List[LogRecord]:
        """Get logs from buffer"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        logs = [r for r in self.log_buffer if r.timestamp >= cutoff]

        if level:
            logs = [r for r in logs if r.level == level]

        return logs

    def get_statistics(self, hours: int = 24) -> Dict:
        """Get logging statistics"""
        logs = self.get_logs(hours)

        if not logs:
            return {'period_hours': hours, 'total_logs': 0}

        by_level = {}
        for log in logs:
            level = log.level.value
            if level not in by_level:
                by_level[level] = 0
            by_level[level] += 1

        errors_with_exceptions = sum(1 for log in logs if log.error is not None)
        logs_with_pii = sum(1 for log in logs if log.pii_detections)

        return {
            'period_hours': hours,
            'total_logs': len(logs),
            'by_level': by_level,
            'errors_with_exceptions': errors_with_exceptions,
            'logs_with_pii_detected': logs_with_pii,
            'pii_summary': self.detector.get_detection_summary(hours)
        }


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Create structured logger
    logger = StructuredLogger('api-server')

    # Log with automatic PII detection and redaction
    logger.info(
        'User registration completed',
        user_email='user@example.com',
        phone_number='555-123-4567'
    )

    # Log with error
    try:
        # Simulate error
        raise ValueError("Database connection failed")
    except Exception as e:
        logger.error(
            'Database operation failed',
            exception=e,
            host='db.example.com'
        )

    # Get statistics
    stats = logger.get_statistics()
    print("\n=== Logging Statistics ===")
    print(json.dumps(stats, indent=2))
