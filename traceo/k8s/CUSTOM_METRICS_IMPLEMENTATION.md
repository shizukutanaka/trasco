# Custom Metrics Implementation Guide for Prometheus

**Date**: November 20, 2024
**Version**: 2.0 (Advanced Applications)
**Target Audience**: Application developers, DevOps engineers

---

## Overview

This guide covers implementing application-specific custom metrics with Prometheus, including:
- OpenMetrics format standards
- Histogram & quantile optimization
- Exemplar implementation for distributed tracing
- High-cardinality metric handling
- Recording rules for custom metrics

---

## Part 1: Application Instrumentation

### 1.1 Language-Specific Prometheus Clients

#### Go Client (Production-Ready)

```go
package main

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"net/http"
	"time"
)

// Define custom metrics
var (
	// Counter: Total requests
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests",
		},
		[]string{"method", "endpoint", "status"},
	)

	// Gauge: Currently active connections
	activeConnections = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "active_connections",
			Help: "Currently active connections",
		},
	)

	// Histogram: Request duration with exemplars
	requestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request latency",
			Buckets: prometheus.ExponentialBuckets(0.001, 2, 10), // 1ms to 512ms
		},
		[]string{"method", "endpoint"},
	)

	// Histogram: Response size
	responseSize = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_response_size_bytes",
			Help:    "HTTP response size",
			Buckets: []float64{100, 1000, 10000, 100000, 1000000},
		},
		[]string{"method", "endpoint"},
	)

	// Summary: Request latency (deprecated in favor of histogram)
	requestLatency = prometheus.NewSummaryVec(
		prometheus.SummaryOpts{
			Name:       "request_latency_summary",
			Help:       "Request latency summary",
			Objectives: map[float64]float64{0.5: 0.05, 0.9: 0.01, 0.99: 0.001},
		},
		[]string{"method"},
	)
)

func init() {
	prometheus.MustRegister(
		httpRequestsTotal,
		activeConnections,
		requestDuration,
		responseSize,
		requestLatency,
	)
}

// Middleware for automatic instrumentation
func instrumentHTTPHandler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Track active connections
		activeConnections.Inc()
		defer activeConnections.Dec()

		// Measure request duration
		start := time.Now()

		// Wrap response writer to capture status and size
		wrapped := &responseWriterWrapper{ResponseWriter: w, statusCode: 200}

		// Call handler
		next.ServeHTTP(wrapped, r)

		// Record metrics
		duration := time.Since(start).Seconds()

		// With exemplar (trace ID from context)
		traceID, _ := r.Context().Value("trace_id").(string)
		obs := requestDuration.WithLabelValues(r.Method, r.RequestURI)
		if exemplar, ok := obs.(prometheus.ExemplarObserver); ok && traceID != "" {
			exemplar.ObserveWithExemplar(duration, prometheus.Labels{"trace_id": traceID})
		} else {
			obs.Observe(duration)
		}

		// Record other metrics
		httpRequestsTotal.WithLabelValues(
			r.Method,
			r.RequestURI,
			http.StatusText(wrapped.statusCode),
		).Inc()

		responseSize.WithLabelValues(r.Method, r.RequestURI).
			Observe(float64(wrapped.bytesWritten))

		requestLatency.WithLabelValues(r.Method).Observe(duration)
	})
}

// Response wrapper to track status and size
type responseWriterWrapper struct {
	http.ResponseWriter
	statusCode   int
	bytesWritten int
}

func (w *responseWriterWrapper) WriteHeader(statusCode int) {
	w.statusCode = statusCode
	w.ResponseWriter.WriteHeader(statusCode)
}

func (w *responseWriterWrapper) Write(data []byte) (int, error) {
	w.bytesWritten += len(data)
	return w.ResponseWriter.Write(data)
}

func main() {
	// Register middleware
	http.Handle("/", instrumentHTTPHandler(http.DefaultServeMux))

	// Expose metrics
	http.Handle("/metrics", promhttp.Handler())

	// Start server
	http.ListenAndServe(":8080", nil)
}
```

#### Python Client

```python
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST
from flask import Flask, request, Response
import time

app = Flask(__name__)

# Define metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

active_connections = Gauge(
    'active_connections',
    'Currently active connections'
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=(0.001, 0.01, 0.1, 0.5, 1.0, 5.0)
)

response_size = Histogram(
    'http_response_size_bytes',
    'HTTP response size',
    ['method', 'endpoint'],
    buckets=(100, 1000, 10000, 100000)
)

# Middleware for instrumentation
@app.before_request
def before_request():
    request.start_time = time.time()
    active_connections.inc()

@app.after_request
def after_request(response):
    # Record metrics
    duration = time.time() - request.start_time

    http_requests_total.labels(
        method=request.method,
        endpoint=request.path,
        status=response.status_code
    ).inc()

    request_duration.labels(
        method=request.method,
        endpoint=request.path
    ).observe(duration)

    response_size.labels(
        method=request.method,
        endpoint=request.path
    ).observe(len(response.get_data()))

    active_connections.dec()
    return response

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route('/api/users')
def get_users():
    # Business logic
    return {'users': []}

if __name__ == '__main__':
    app.run(port=8080)
```

#### Java Client

```java
import io.micrometer.prometheus.PrometheusConfig;
import io.micrometer.prometheus.PrometheusMeterRegistry;
import io.prometheus.client.exporter.HTTPServer;

public class MetricsExample {
    private static final PrometheusMeterRegistry meterRegistry =
        new PrometheusMeterRegistry(PrometheusConfig.DEFAULT);

    public static void main(String[] args) throws Exception {
        // Create meters
        var httpRequestsTotal = io.micrometer.core.instrument.Counter.builder("http_requests_total")
            .description("Total HTTP requests")
            .tag("service", "backend")
            .register(meterRegistry);

        var requestDuration = io.micrometer.core.instrument.Timer.builder("http_request_duration_seconds")
            .description("HTTP request latency")
            .publishPercentiles(0.5, 0.95, 0.99)
            .register(meterRegistry);

        var activeConnections = io.micrometer.core.instrument.Gauge.builder("active_connections",
            AtomicInteger::new, AtomicInteger::get)
            .description("Currently active connections")
            .register(meterRegistry);

        // Use in application
        httpRequestsTotal.increment();
        requestDuration.recordCallable(() -> {
            // Business logic
            return "result";
        });

        // Expose metrics on port 8081
        HTTPServer server = new HTTPServer(8081);
    }
}
```

---

## Part 2: Custom Metric Patterns

### 2.1 Business Metrics (SLI/SLO Tracking)

```go
// Feature usage tracking
var featureUsageCounter = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "feature_usage_total",
        Help: "Feature usage count",
    },
    []string{"feature", "user_tier", "result"},
)

// Track feature adoption
featureUsageCounter.WithLabelValues("dark_mode", "premium", "enabled").Inc()
featureUsageCounter.WithLabelValues("api_v2", "free", "error").Inc()

// Conversion funnel metrics
var conversionStageGauge = prometheus.NewGaugeVec(
    prometheus.GaugeOpts{
        Name: "conversion_funnel_stage",
        Help: "Users at each conversion stage",
    },
    []string{"stage"},
)

conversionStageGauge.WithLabelValues("signup").Set(10000)
conversionStageGauge.WithLabelValues("trial").Set(5000)
conversionStageGauge.WithLabelValues("paid").Set(500)

// SLI: Success rate for critical operations
var criticalOperationSuccess = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "critical_operation_success_total",
        Help: "Successful critical operations",
    },
    []string{"operation", "user_id"},  // ⚠️ WARNING: User ID causes cardinality explosion!
)

// Better approach: aggregate user IDs
var criticalOperationSuccess = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "critical_operation_success_total",
        Help: "Successful critical operations",
    },
    []string{"operation", "user_tier"},  // ✅ GOOD: Limited cardinality
)
```

### 2.2 OpenMetrics Format with Exemplars

```go
// Go client with exemplar support (Prometheus 2.49+)
import "github.com/prometheus/client_golang/prometheus/promhttp"

// Create histogram with exemplars enabled
requestDuration := prometheus.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "HTTP request latency",
        Buckets: prometheus.ExponentialBuckets(0.001, 2, 10),
    },
    []string{"method", "endpoint"},
)

// Record with exemplar
func recordRequest(traceID string, duration float64) {
    obs := requestDuration.WithLabelValues(method, endpoint)

    // Check if exemplar observer (requires promhttp.HandlerOpts{DisableCompression: true})
    if exemplarObs, ok := obs.(prometheus.ExemplarObserver); ok {
        exemplarObs.ObserveWithExemplar(duration, prometheus.Labels{
            "trace_id": traceID,
        })
    } else {
        obs.Observe(duration)
    }
}

// Handler with exemplar support
promHandler := promhttp.HandlerOpts{
    DisableCompression: false,  // Keep enabled for performance
}.Handler()

http.Handle("/metrics", promHandler)
```

### 2.3 High-Cardinality Metric Handling

```go
// ❌ WRONG: High-cardinality labels
var userMetrics = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "user_actions_total",
        Help: "User actions",
    },
    []string{"user_id", "action_id", "session_id"},  // 1M users × 1K actions = HIGH CARDINALITY
)

// ✅ CORRECT: Low-cardinality labels with aggregation
var actionMetrics = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "action_total",
        Help: "Actions performed",
    },
    []string{"action_type", "user_tier"},  // Low cardinality
)

// Record metrics in application
func trackUserAction(userID string, action string, userTier string) {
    // Don't include user_id in label - causes cardinality explosion
    actionMetrics.WithLabelValues(action, userTier).Inc()

    // If user-specific tracking is needed, use structured logging instead
    // or send to separate analytics system
    logger.WithFields(logrus.Fields{
        "user_id": userID,
        "action": action,
    }).Info("User action performed")
}
```

### 2.4 Recording Rules for Custom Metrics

```yaml
groups:
  - name: business_metrics
    interval: 30s
    rules:
      # Hourly conversion rate
      - record: conversion:hourly_rate
        expr: |
          rate(conversion_funnel_stage{stage="paid"}[1h])
          /
          rate(conversion_funnel_stage{stage="signup"}[1h])

      # Feature adoption rate
      - record: feature:adoption_percent
        expr: |
          (feature_usage_total{result="enabled"} / feature_usage_total) * 100

      # User retention
      - record: user:retention_rate
        expr: |
          rate(active_users_total[7d])
          /
          rate(active_users_total offset 7d [7d])

      # Revenue-weighted metrics
      - record: revenue:weighted_latency
        expr: |
          sum(
            http_request_duration_seconds_sum{user_tier="premium"}
            / http_request_duration_seconds_count{user_tier="premium"}
          ) by (endpoint)
```

---

## Part 3: Advanced Metric Implementations

### 3.1 Distributed Tracing Integration

```go
import (
    "context"
    "github.com/prometheus/client_golang/prometheus"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
)

// Extract trace ID from context and record as exemplar
func recordMetricWithTrace(ctx context.Context, obs prometheus.Observer, value float64) {
    span := trace.SpanFromContext(ctx)

    if obs, ok := obs.(prometheus.ExemplarObserver); ok && span.SpanContext().IsValid() {
        obs.ObserveWithExemplar(value, prometheus.Labels{
            "trace_id": span.SpanContext().TraceID().String(),
        })
    } else {
        obs.Observe(value)
    }
}

// Middleware that adds exemplars automatically
func traceAwareMiddleware(ctx context.Context, next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Extract trace ID from request headers
        traceID := r.Header.Get("X-Trace-ID")
        if traceID == "" {
            traceID = r.Header.Get("B3")  // Jaeger format
        }

        // Add to context
        ctx := context.WithValue(r.Context(), "trace_id", traceID)

        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

### 3.2 Multi-Dimensional Metrics

```go
// Bucket-based aggregation to reduce cardinality
func getUserBucket(userID string) string {
    hash := fnv.New32a()
    hash.Write([]byte(userID))
    bucket := hash.Sum32() % 10  // 10 buckets
    return fmt.Sprintf("bucket_%d", bucket)
}

var multiDimensionalMetric = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "transaction_total",
        Help: "Transactions by multiple dimensions",
    },
    []string{
        "region",           // 5 values
        "merchant_tier",    // 3 values
        "payment_method",   // 10 values
        "result",           // 2 values
        "user_bucket",      // 10 values
    },
)

// Total combinations: 5 × 3 × 10 × 2 × 10 = 3,000 series (acceptable)
// Without bucketing: 5 × 3 × 10 × 2 × 1M users = 300M series (unacceptable)
```

### 3.3 Custom Histogram Bucketing

```go
// Optimize buckets for specific use case
// Default: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10

// For API latency: focus on sub-second ranges
apiLatencyHistogram := prometheus.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "api_request_duration_seconds",
        Help:    "API request latency",
        Buckets: []float64{.001, .005, .01, .025, .05, .1, .25, .5, 1},  // Optimized for fast APIs
    },
    []string{"method", "endpoint"},
)

// For background job duration: focus on longer ranges
jobDurationHistogram := prometheus.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "job_duration_seconds",
        Help:    "Background job duration",
        Buckets: []float64{1, 10, 60, 300, 900, 3600, 86400},  // 1s to 24h
    },
    []string{"job_name"},
)
```

---

## Part 4: Monitoring Custom Metrics

### 4.1 Alert Rules for Business Metrics

```yaml
groups:
  - name: business_alerts
    interval: 30s
    rules:
      # Alert on low conversion rate
      - alert: ConversionRateLow
        expr: |
          (
            sum(rate(conversion_funnel_stage{stage="paid"}[1h]))
            /
            sum(rate(conversion_funnel_stage{stage="signup"}[1h]))
          ) < 0.01
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Conversion rate below 1%"
          description: "Current rate: {{ $value }}"

      # Alert on feature adoption lag
      - alert: FeatureAdoptionLag
        expr: feature:adoption_percent{feature="new_ui"} < 5
        for: 7d
        labels:
          severity: info
        annotations:
          summary: "Feature {{ $labels.feature }} adoption lagging"

      # Alert on critical operation failures
      - alert: CriticalOperationFailure
        expr: |
          (
            sum(rate(critical_operation_success_total{operation="payment"}[5m]))
            where greater_equal(...) < 0.99
          )
        for: 5m
        labels:
          severity: critical
```

### 4.2 Dashboard Queries

```json
{
  "dashboard": {
    "title": "Custom Business Metrics",
    "panels": [
      {
        "title": "Conversion Funnel",
        "targets": [
          {
            "expr": "conversion_funnel_stage"
          }
        ]
      },
      {
        "title": "Feature Adoption",
        "targets": [
          {
            "expr": "feature:adoption_percent"
          }
        ]
      },
      {
        "title": "User Retention by Cohort",
        "targets": [
          {
            "expr": "user:retention_rate"
          }
        ]
      }
    ]
  }
}
```

---

## Part 5: Best Practices

### 5.1 Metric Naming Conventions

```
<namespace>_<subsystem>_<name>_<unit>

Examples:
- http_request_duration_seconds      ✅ GOOD
- http_request_latency_ms            ✅ GOOD (if always in milliseconds)
- http_latency                        ❌ BAD (ambiguous unit)
- hrl                                 ❌ BAD (not descriptive)

Patterns:
- For counters: use "_total" suffix
  - http_requests_total
  - errors_total

- For gauges: no suffix
  - active_connections
  - temperature_celsius

- For histograms: use "_bucket", "_sum", "_count" (automatic)
  - http_request_duration_seconds_bucket
  - http_request_duration_seconds_sum
  - http_request_duration_seconds_count
```

### 5.2 Cardinality Guidelines

```
Label cardinality limits:

ALWAYS SAFE (<100K combinations):
- HTTP method (GET, POST, etc.) → 5 values
- Endpoint/path (static routes) → 50 values
- Status code (1xx, 2xx, 3xx, 4xx, 5xx) → 5 values
- Service/job name → 20 values
- Environment → 5 values
- Region → 10 values
- Tier (free, paid, enterprise) → 5 values

CAUTION (100K - 1M combinations):
- Database table names → 100 values
- API endpoints → 1000 values
- Merchant IDs (bucketed) → 10 values
- Product categories → 1000 values

NEVER USE (>1M combinations):
- User IDs
- Request IDs
- Session IDs
- Customer IDs
- Trace IDs
- Specific file paths
```

### 5.3 Recording Rule Strategy

```yaml
# Rules by complexity level

# Level 1: Simple aggregation (always precompute)
- record: job:http_requests:total
  expr: sum(http_requests_total) by (job)

# Level 2: Multi-step aggregation (precompute if used frequently)
- record: job:error_rate:5m
  expr: |
    (
      sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)
      /
      sum(rate(http_requests_total[5m])) by (job)
    ) * 100

# Level 3: Complex queries (precompute only if used in alerts/dashboards)
- record: slo:availability:daily
  expr: |
    (
      count(time() - max(timestamp(up)) by (job) > 300)
      /
      count(up)
    ) * 100
```

---

## Conclusion

Custom metrics enable better insights into application behavior. Follow these principles:

1. **Keep cardinality low** - Use buckets for aggregation
2. **Name clearly** - Use standardized naming conventions
3. **Precompute common queries** - Use recording rules
4. **Link to traces** - Use exemplars for deep investigation
5. **Alert on SLI violations** - Not just technical metrics
6. **Review regularly** - Audit metrics for usage and cardinality

---

*Last Updated: November 20, 2024*
*Based on: Prometheus best practices, OpenMetrics standard, real-world implementations*
