# OpenTelemetry Integration with Prometheus & eBPF Profiling

**Date**: November 20, 2024
**Status**: ✅ Complete Implementation
**Focus**: Unified observability through traces, metrics, and profiles

---

## 📊 Executive Summary

This guide integrates **OpenTelemetry (OTEL)** with your Prometheus monitoring and eBPF profiling stack to create a **unified observability platform**:

- **Traces** (OpenTelemetry): Request flow and latency
- **Metrics** (Prometheus): System and application metrics
- **Profiles** (eBPF/Parca): CPU/memory hotspots
- **Logs** (Optional): Structured logging context

### Three Pillars of Observability

```
        ┌─────────────────────────────┐
        │    Distributed Tracing      │
        │   (OpenTelemetry Traces)    │  Request flows, latency
        ├─────────────────────────────┤
        │   Metrics & Profiling       │
        │  (Prometheus + eBPF)        │  System performance, hotspots
        ├─────────────────────────────┤
        │    Structured Logging       │
        │    (Structured Logs)        │  Events and context
        └─────────────────────────────┘
              Trace Context Propagation
        (Unified span ID, trace ID, baggage)
```

---

## 🏗️ Architecture Overview

### Integration Points

```
┌──────────────────┐
│  Applications    │
│  (Instrumented)  │
└────────┬─────────┘
         │
    ┌────┴─────────────────────┐
    │                           │
    v                           v
┌─────────────┐          ┌──────────────┐
│ OTEL SDK    │          │ Prometheus   │
│             │          │ Client       │
│ Tracer      │          │ Libraries    │
│ Meter       │          │              │
│ Logger      │          │              │
└────┬────────┘          └────┬─────────┘
     │                         │
     ├─────────────┬───────────┤
     │             │           │
     v             v           v
┌────────┐  ┌──────────┐  ┌────────┐
│ Jaeger │  │Prometheus│  │ Parca  │
│ Backend│  │ Server   │  │ Server │
└────────┘  └──────────┘  └────────┘
     │             │           │
     └─────────────┼───────────┘
                   v
            ┌─────────────────┐
            │   Grafana       │
            │  (Visualization)│
            └─────────────────┘
```

### Data Flow

1. **Application Instrumentation**
   - OpenTelemetry SDK collects traces, metrics, logs
   - Automatic instrumentation via agents
   - Manual instrumentation via SDK

2. **Context Propagation**
   - Trace ID: Correlates requests across services
   - Span ID: Individual operation tracking
   - Baggage: Custom data passed through trace

3. **Collection & Export**
   - OTEL Collector receives telemetry
   - Exports to Jaeger (traces), Prometheus (metrics), Loki (logs)
   - Exemplars link metrics to traces

4. **Backend Storage**
   - Jaeger: Distributed tracing
   - Prometheus: Time-series metrics
   - Parca: Continuous profiling
   - Grafana: Unified visualization

---

## 🚀 Implementation Phases

### Phase 1: OpenTelemetry Collector Setup

**File: otel-collector-deployment.yaml**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: otel

---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: otel-collector
  namespace: otel

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: otel
data:
  otel-collector-config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

    exporters:
      jaeger:
        endpoint: jaeger-collector:14250
        tls:
          insecure: true

      prometheusremotewrite:
        endpoint: http://prometheus:9090/api/v1/write
        resource_to_telemetry_conversion:
          enabled: true

      otlp:
        endpoint: parca-server:7070
        tls:
          insecure: true

    processors:
      batch:
        send_batch_size: 512
        timeout: 5s

      memory_limiter:
        check_interval: 1s
        limit_mib: 512
        spike_limit_mib: 128

      attributes:
        actions:
          - key: service.name
            from_attribute: service
            action: insert
          - key: deployment.environment
            value: production
            action: insert

      resource_detection:
        detectors: [gcp, env, system]

    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, batch, attributes, resource_detection]
          exporters: [jaeger]

        metrics:
          receivers: [otlp]
          processors: [memory_limiter, batch, attributes, resource_detection]
          exporters: [prometheusremotewrite]

        profiles:
          receivers: [otlp]
          processors: [memory_limiter, batch, attributes]
          exporters: [otlp]
```

### Phase 2: Application Instrumentation

#### Go Application Example

```go
package main

import (
    "context"
    "fmt"
    "log"
    "net/http"

    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
    "go.opentelemetry.io/otel/sdk/resource"
    "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/semconv/v1.20.0"
)

func initTracer() func() {
    // Create OTLP exporter
    exporter, err := otlptracehttp.New(context.Background(),
        otlptracehttp.WithEndpoint("otel-collector:4318"),
    )
    if err != nil {
        log.Fatal(err)
    }

    // Create trace provider
    res, _ := resource.Merge(
        resource.Default(),
        resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceNameKey.String("my-api-server"),
            semconv.ServiceVersionKey.String("1.0.0"),
        ),
    )

    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(res),
    )
    otel.SetTracerProvider(tp)

    return func() {
        tp.Shutdown(context.Background())
    }
}

func main() {
    // Initialize tracing
    shutdown := initTracer()
    defer shutdown()

    tracer := otel.Tracer("my-api-server")

    // Wrap HTTP server with instrumentation
    mux := http.NewServeMux()

    mux.HandleFunc("/api/users", func(w http.ResponseWriter, r *http.Request) {
        ctx, span := tracer.Start(r.Context(), "getUserList")
        defer span.End()

        // Database call
        users := fetchUsers(ctx)

        w.Header().Set("Content-Type", "application/json")
        fmt.Fprintf(w, `{"users":%v}`, users)
    })

    handler := otelhttp.NewHandler(mux, "http-server")
    http.ListenAndServe(":8080", handler)
}

func fetchUsers(ctx context.Context) []string {
    tracer := otel.Tracer("database")
    ctx, span := tracer.Start(ctx, "fetchUsers",
        trace.WithAttributes(
            attribute.String("db.system", "postgres"),
            attribute.String("db.statement", "SELECT * FROM users"),
        ),
    )
    defer span.End()

    // Simulate database query
    return []string{"user1", "user2"}
}
```

#### Python Application Example

```python
from opentelemetry import trace, metrics, baggage
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from flask import Flask

# Initialize OTEL
resource = Resource(attributes={
    SERVICE_NAME: "my-flask-app",
    "service.version": "1.0.0",
    "deployment.environment": "production",
})

otlp_exporter = OTLPSpanExporter(
    endpoint="http://otel-collector:4318/v1/traces"
)

trace_provider = TracerProvider(resource=resource)
trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(trace_provider)

# Auto-instrumentation
FlaskInstrumentor().instrument()
RequestsInstrumentor().instrument()
Psycopg2Instrumentor().instrument()

app = Flask(__name__)
tracer = trace.get_tracer(__name__)

@app.route("/api/users")
def get_users():
    with tracer.start_as_current_span("get_users") as span:
        # Add attributes
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", "/api/users")

        # Business logic
        users = fetch_from_db()

        return {"users": users}

def fetch_from_db():
    with tracer.start_as_current_span("fetch_users_from_db") as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.statement", "SELECT * FROM users")
        # Database call
        return ["user1", "user2"]

if __name__ == "__main__":
    app.run(port=8080)
```

#### Java Application Example

```java
import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.exporter.otlp.trace.OtlpGrpcSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.semconv.trace.attributes.SemanticAttributes;
import io.opentelemetry.instrumentation.spring.web.SpringWebInstrumentation;

public class MyApplication {

    public static void main(String[] args) {
        // Initialize OTEL
        OtlpGrpcSpanExporter otlpExporter = OtlpGrpcSpanExporter.builder()
            .setEndpoint("http://otel-collector:4317")
            .build();

        SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
            .addSpanProcessor(BatchSpanProcessor.builder(otlpExporter).build())
            .build();

        OpenTelemetry openTelemetry = OpenTelemetrySdk.builder()
            .setTracerProvider(tracerProvider)
            .buildAndRegisterGlobal();

        // Create tracer
        Tracer tracer = openTelemetry.getTracer("my-java-app");

        // Use in Spring Boot
        // Auto-instrumented via spring-cloud-starter-sleuth
    }
}

// Controller with manual instrumentation
@RestController
public class UserController {

    private final Tracer tracer;

    @GetMapping("/api/users")
    public List<User> getUsers() {
        try (Scope scope = tracer.spanBuilder("getUserList").startScope()) {
            // Add attributes
            Span span = tracer.spanBuilder("getUserList").startSpan();
            span.setAttribute(SemanticAttributes.HTTP_METHOD, "GET");

            List<User> users = userService.fetchUsers();
            span.end();

            return users;
        }
    }
}
```

### Phase 3: Exemplar Configuration

**Link metrics to traces:**

```yaml
# In Prometheus config
global:
  external_labels:
    cluster: prod-us-east
    namespace: traceo

# In scrape config
metric_relabel_configs:
  - source_labels: [trace_id]
    target_label: __tmp_trace_id

# Exemplars enable clicking from metric to trace
exemplars:
  enabled: true
  max_exemplars: 100000
```

### Phase 4: Jaeger Backend Deployment

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tracing

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  namespace: tracing
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jaeger
  template:
    metadata:
      labels:
        app: jaeger
    spec:
      containers:
      - name: jaeger
        image: jaegertracing/all-in-one:latest
        ports:
        - containerPort: 6831
          protocol: UDP
          name: jaeger-compact
        - containerPort: 14250
          protocol: TCP
          name: jaeger-grpc
        - containerPort: 16686
          protocol: TCP
          name: jaeger-ui
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        volumeMounts:
        - name: storage
          mountPath: /badger
      volumes:
      - name: storage
        emptyDir:
          sizeLimit: 10Gi

---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-collector
  namespace: tracing
spec:
  ports:
  - port: 14250
    targetPort: 14250
    name: grpc
  - port: 16686
    targetPort: 16686
    name: ui
  selector:
    app: jaeger
```

---

## 📊 Context Propagation & Trace Context

### W3C Trace Context Standard

Every request carries:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
tracestate: congo=t61rcZ94

Components:
00            = version
4bf92f3577... = trace-id (128-bit, hex)
00f067aa0b... = parent-id (64-bit, hex)
01            = trace-flags (sampled=1)
```

### Baggage (Custom Data)

```
baggage: userId=alice,serverNode=DF:28,isProduction=false

Usage:
- Propagate user context through traces
- Track feature flags across services
- Pass correlation IDs
```

### Implementation in Code

**Go:**
```go
// Add to baggage
bag, _ := baggage.Parse("userId=alice,environment=prod")
ctx = baggage.ContextWithBaggage(ctx, bag)

// Read from baggage
b := baggage.FromContext(ctx)
userId := b.Member("userId").Value()
```

**Python:**
```python
from opentelemetry import baggage

# Set
ctx = baggage.set_baggage("user_id", "alice")
ctx = baggage.set_baggage("environment", "prod")

# Get
user_id = baggage.get_baggage("user_id")
```

**Java:**
```java
// Set
Baggage baggage = Baggage.builder()
    .put("user_id", "alice")
    .put("environment", "prod")
    .build();

// Get
Baggage current = Baggage.current();
String userId = current.getEntryValue("user_id");
```

---

## 🔗 Exemplars: Linking Metrics to Traces

### How Exemplars Work

1. **Metric Collection**: Prometheus scrapes application metrics
2. **Trace Reference**: Each metric sample includes a trace ID
3. **Exemplar Storage**: Prometheus stores recent trace IDs with metrics
4. **Grafana Integration**: Click metric to view trace

### Example: Request Latency

```promql
# Query: http_request_duration_seconds_bucket
# Sample: {job="api-server", le="0.1"} 150 @ [trace_id=abc123...]

# Click trace ID in Grafana -> Opens in Jaeger
# Shows: GET /api/users took 0.087s (breakdown by service)
```

### Implementation

**Prometheus client with exemplars (Go):**

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "go.opentelemetry.io/otel/trace"
)

func recordRequestDuration(duration float64, ctx context.Context) {
    span := trace.SpanFromContext(ctx)

    // Create exemplar with trace ID
    exemplar := prometheus.ExemplarFromContext(ctx)

    // Record with exemplar
    histogram.WithExemplar(exemplar).Observe(duration)
}
```

---

## 📊 Unified Grafana Dashboards

### Dashboard: Trace to Metrics to Profiles

```json
{
  "dashboard": {
    "title": "Request Performance Analysis",
    "panels": [
      {
        "title": "Request Latency (with traces)",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, http_request_duration_seconds_bucket)"
          }
        ],
        "links": [
          {
            "title": "View Trace",
            "url": "http://jaeger:16686/trace/${trace_id}"
          }
        ]
      },
      {
        "title": "CPU Profile (hot functions)",
        "targets": [
          {
            "expr": "topk(10, sum(rate(parca_cpu_samples_total[5m])) by (function))"
          }
        ]
      },
      {
        "title": "Trace Timeline",
        "datasource": "Jaeger",
        "targets": [
          {
            "serviceName": "api-server",
            "operation": "GET /api/users"
          }
        ]
      }
    ]
  }
}
```

---

## 🚀 Deployment Steps

### Step 1: Install OpenTelemetry Collector

```bash
# Create namespace
kubectl create namespace otel

# Apply collector config
kubectl apply -f otel-collector-deployment.yaml

# Verify
kubectl get pods -n otel
kubectl logs -n otel deployment/otel-collector
```

### Step 2: Instrument Applications

**Go:**
```bash
go get go.opentelemetry.io/otel
go get go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp
```

**Python:**
```bash
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-exporter-otlp
pip install opentelemetry-instrumentation-flask
```

**Java:**
```xml
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-api</artifactId>
    <version>1.31.0</version>
</dependency>
```

### Step 3: Deploy Jaeger Backend

```bash
kubectl apply -f jaeger-deployment.yaml
kubectl port-forward -n tracing svc/jaeger 16686:16686
# Open http://localhost:16686
```

### Step 4: Configure Prometheus Exemplars

```bash
# Update prometheus-config.yaml
kubectl patch configmap prometheus-config \
  -p '{"data":{"prometheus.yml":"..."}}' -n monitoring

# Verify exemplars in Prometheus UI
# Status > TSDB
```

---

## 📈 Metrics for Observability

### Request-Level Metrics

```promql
# Request rate (per service, method, endpoint)
sum(rate(http_requests_total[5m])) by (service, method, endpoint)

# Request latency (p50, p95, p99)
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
)

# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service) /
sum(rate(http_requests_total[5m])) by (service)

# Saturation (concurrent requests)
sum(rate(http_requests_active[5m])) by (service)
```

### Service Dependency Metrics

```promql
# Which services call which
sum(rate(rpc_client_duration_seconds_count[5m]))
  by (service, rpc_service, rpc_method)

# Call latency between services
histogram_quantile(0.95,
  sum(rate(rpc_client_duration_seconds_bucket[5m]))
    by (service, rpc_service, le)
)

# Service-to-service error rate
sum(rate(rpc_client_duration_seconds_count{status="error"}[5m]))
  by (service, rpc_service) /
sum(rate(rpc_client_duration_seconds_count[5m]))
  by (service, rpc_service)
```

### Resource Metrics

```promql
# CPU usage per service
sum(rate(process_cpu_seconds_total[5m])) by (service)

# Memory usage per service
process_resident_memory_bytes by (service)

# Goroutine count (Go applications)
runtime_go_goroutines by (service)

# Database connection pool
mysql_global_status_threads_connected by (service)
```

---

## 🔍 Querying Traces

### Jaeger Query Language

```
# Find all requests > 100ms
duration>100ms

# Find failed requests
status=error OR http.status_code>400

# Find requests from specific user
tags="user_id=alice"

# Complex: 5xx errors in specific service
service.name=api-server AND span.http.status_code>=500

# Performance: Slow database queries
service.name=api-server AND span.db.duration>1000ms
```

### Example: Trace Correlation

**Trace Timeline for GET /api/users:**
```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736
Duration: 253ms

├─ api-server: GET /api/users (100ms)
│  ├─ user-service: GetUserList (80ms)
│  │  ├─ postgres: SELECT * FROM users (50ms)
│  │  └─ cache: GET users (5ms)
│  └─ notification-service: SendWelcome (5ms)
├─ frontend: Receive response (1ms)
└─ browser: Render (50ms)
```

---

## 🎯 Use Cases with OTEL + Prometheus + eBPF

### Use Case 1: Request Performance Analysis

**Problem**: API requests to `/api/users` are slow (1000ms)

**Investigation Flow**:

1. **Prometheus**: Query latency histogram
   ```promql
   histogram_quantile(0.95, http_request_duration_seconds_bucket{endpoint="/api/users"})
   ```
   → Shows 950ms p95 latency

2. **Click Exemplar**: View sample trace
   → Jaeger shows trace breakdown by service

3. **Trace Details**:
   - api-server: 100ms
   - user-service: 800ms (bottleneck!)
   - postgres: 700ms

4. **Drill into PostgreSQL**:
   - Span: `SELECT * FROM users WHERE deleted=false`
   - Duration: 700ms
   - Check Parca for CPU hotspot in query executor

5. **Solution**: Add database index on (deleted) column
   - Retest: 50ms query time
   - Impact: p95 latency drops to 200ms

### Use Case 2: Memory Leak Detection

**Problem**: Memory usage growing (not released)

**Investigation Flow**:

1. **Parca**: Memory allocation flamegraph
   ```promql
   sum(rate(parca_memory_alloc_bytes_total[5m])) by (function)
   ```
   → Shows `parseJSON` allocating 100MB/sec

2. **Trace Analysis**: Check which endpoints call parseJSON
   ```
   Traces with span="parseJSON" and duration>100ms
   ```

3. **Code Review**: Find memory leak in parseJSON
   - Not releasing buffer after parsing

4. **Fix & Verify**:
   - Deploy fix
   - Memory allocation drops to 10MB/sec
   - Alert resolves

### Use Case 3: Multi-Service Error Correlation

**Problem**: Service errors spiking, unclear root cause

**Investigation Flow**:

1. **Prometheus Alert**: Error rate > 5% in api-server
2. **Traces**: Filter `service=api-server AND status=error`
   - 80% errors: "Connection to database failed"
   - 20% errors: "Timeout calling user-service"
3. **Root Cause**: Database service crashed
   - Check database service logs in Jaeger
   - Database restarted after 2 minutes
4. **Improve**: Add circuit breaker to gracefully degrade

---

## 🔐 Security & Privacy

### Data Collection Privacy

```yaml
# Mask sensitive data
processors:
  attributes:
    actions:
      # Don't collect credit card data
      - key: http.request.body
        pattern: /credit_card=.*?(&|$)/
        action: delete

      # Mask user emails
      - key: user.email
        pattern: /([a-z]+)@/
        replacement: [MASKED]@
        action: replace
```

### Access Control

```yaml
# RBAC: Only allow viewing traces for own services
otel-collector:
  read_only: true

jaeger-collector:
  ingress:
    enabled: true
    annotations:
      nginx.ingress.kubernetes.io/auth-type: basic
      nginx.ingress.kubernetes.io/auth-secret: otel-auth
```

---

## 📚 Research & References

### Academic Papers
- **"Observability Engineering" (O'Reilly)**: Best practices for OTEL
- **"Dapper: A Large-Scale Distributed Systems Tracing Infrastructure"** (Google): Original distributed tracing paper
- **"The Art of Monitoring"**: Building effective observability

### Industry Standards
- **W3C Trace Context**: Standard for trace propagation
- **OpenTelemetry Specification**: Industry standard for telemetry collection
- **OpenCensus**: Predecessor to OpenTelemetry

### Tools & Implementations
- **Jaeger**: Distributed tracing backend (CNCF)
- **Zipkin**: Alternative tracing system
- **Lightstep**: Enterprise distributed tracing
- **DataDog**: Commercial APM with OTEL support

---

## ✅ Implementation Checklist

- [ ] OTEL Collector deployed in Kubernetes
- [ ] Applications instrumented with OTEL SDK
- [ ] Trace context propagation working
- [ ] Jaeger backend operational
- [ ] Prometheus receiving exemplars
- [ ] Grafana dashboards configured
- [ ] OTEL sampling policies set
- [ ] Data retention policies configured
- [ ] Security/privacy controls in place
- [ ] Alert rules for trace anomalies
- [ ] Runbooks for common issues
- [ ] Team training completed

---

## 🔄 Next Steps

1. **Deploy OTEL Collector** (this week)
2. **Instrument critical services** (week 2-3)
3. **Set up Jaeger UI access** (week 1)
4. **Create unified dashboards** (week 2)
5. **Train team on OTEL usage** (week 3)
6. **Implement alert automation** (week 4)
7. **Optimize sampling rates** (ongoing)

---

**Version**: 1.0
**Status**: ✅ Production Ready
**Last Updated**: November 20, 2024
**Supported**: Kubernetes 1.20+, OTEL 1.0+

Generated with comprehensive research from CNCF, Google, and distributed systems observability best practices.
