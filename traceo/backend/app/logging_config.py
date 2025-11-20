"""
Logging configuration for Traceo backend.
Supports multiple logging outputs: file, console, JSON, and external services.
"""

import os
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for better parsing"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        return json.dumps(log_data)


class StructuredLogger(logging.Logger):
    """Logger with structured context support"""

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.context = {}

    def set_context(self, **kwargs):
        """Set context variables for logging"""
        self.context.update(kwargs)

    def clear_context(self):
        """Clear context variables"""
        self.context = {}

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=None):
        """Override _log to include context"""
        if extra is None:
            extra = {}

        for key, value in self.context.items():
            extra[key] = value

        super()._log(level, msg, args, exc_info, extra, stack_info)


def setup_logging(
    log_level: str = None,
    log_file: str = None,
    json_output: bool = False,
    sentry_dsn: str = None,
) -> logging.Logger:
    """
    Setup logging configuration for the application.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (if None, only console logging)
        json_output: Enable JSON formatting
        sentry_dsn: Sentry DSN for error tracking

    Returns:
        Configured logger instance
    """

    # Get configuration from environment
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    log_dir = os.getenv("LOG_DIR", "logs")
    json_output = json_output or os.getenv("LOG_JSON", "false").lower() == "true"
    sentry_dsn = sentry_dsn or os.getenv("SENTRY_DSN")

    # Create logs directory
    if log_file or log_dir:
        Path(log_dir).mkdir(exist_ok=True)
        if not log_file:
            log_file = os.path.join(log_dir, "traceo.log")

    # Configure root logger
    logging.setLoggerClass(StructuredLogger)
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if json_output:
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handler (if specified)
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))

        if json_output:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Sentry Handler (if configured)
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            )

            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[sentry_logging],
                traces_sample_rate=0.1,
                release=os.getenv("APP_VERSION", "1.0.0")
            )

            root_logger.info("Sentry error tracking configured")

        except ImportError:
            root_logger.warning("Sentry SDK not installed. Error tracking disabled.")

    return root_logger


def get_logger(name: str) -> StructuredLogger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


# Security event logging
def log_security_event(
    event_type: str,
    details: dict,
    severity: str = "INFO",
    request_id: str = None,
    user_id: str = None,
):
    """Log security event"""
    logger = get_logger("security")
    extra = {
        "event_type": event_type,
        "severity": severity,
    }

    if request_id:
        extra["request_id"] = request_id
    if user_id:
        extra["user_id"] = user_id

    logger.log(
        getattr(logging, severity),
        f"Security Event: {event_type} - {json.dumps(details)}",
        extra=extra
    )


# Performance logging
def log_performance(
    operation: str,
    duration_ms: float,
    status: str = "success",
    details: dict = None,
):
    """Log performance metrics"""
    logger = get_logger("performance")
    details = details or {}

    logger.info(
        f"Operation: {operation} - Duration: {duration_ms:.2f}ms - Status: {status}",
        extra={
            "operation": operation,
            "duration_ms": duration_ms,
            "status": status,
            **details
        }
    )


# API logging
def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: str = None,
    user_id: str = None,
):
    """Log API request"""
    logger = get_logger("api")
    extra = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }

    if client_ip:
        extra["client_ip"] = client_ip
    if user_id:
        extra["user_id"] = user_id

    logger.info(
        f"{method} {path} - {status_code} ({duration_ms:.2f}ms)",
        extra=extra
    )


# Error logging
def log_error(
    error_type: str,
    message: str,
    exc_info = None,
    context: dict = None,
):
    """Log error with context"""
    logger = get_logger("error")
    extra = {"error_type": error_type}

    if context:
        extra.update(context)

    logger.error(
        f"{error_type}: {message}",
        exc_info=exc_info,
        extra=extra
    )


# Initialize logging on module load
logger = setup_logging()
