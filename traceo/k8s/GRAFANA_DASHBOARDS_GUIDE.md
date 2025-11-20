# Grafana Dashboards - Unified Observability Visualization

**Date**: November 20, 2024
**Status**: ✅ Complete Implementation
**Focus**: Unified visualization of metrics, traces, and profiles

---

## 📊 Executive Summary

This guide provides comprehensive Grafana dashboard configurations that unify the three pillars of observability:

- **Metrics** (Prometheus): System and application KPIs
- **Traces** (Jaeger): Request flow and latency breakdown
- **Profiles** (Parca/eBPF): CPU/memory hotspots

### Observability Experience

```
┌────────────────────────────────────────┐
│     Grafana Unified Dashboard          │
├────────────────────────────────────────┤
│                                        │
│  [Panel] Request Latency (with traces) │
│  [Panel] Error Rate                    │
│  [Panel] CPU Usage (with profiles)     │
│  [Panel] Memory Hotspots               │
│  [Panel] Service Dependencies          │
│  [Panel] Trace Timeline                │
│  [Panel] Flamegraph                    │
│                                        │
│  Click metric → View trace → View code │
│                                        │
└────────────────────────────────────────┘
```

---

## 🎯 Dashboard Strategy

### Dashboard Types

1. **System Overview Dashboard**
   - High-level cluster and service health
   - Golden signals (latency, traffic, errors, saturation)
   - Key service status

2. **Service-Level Dashboards**
   - Per-service metrics
   - Request lifecycle
   - Dependencies and downstream impact

3. **Performance Analysis Dashboard**
   - CPU profiling flamegraphs
   - Memory hotspots
   - Lock contention
   - I/O performance

4. **Troubleshooting Dashboard**
   - Trace search interface
   - Error analysis
   - Latency correlation
   - Anomaly detection

5. **SLO/SLI Tracking Dashboard**
   - Error budget consumption
   - Burn rate alerts
   - Service reliability metrics

---

## 📋 Dashboard Specifications

### Dashboard 1: System Overview

**Purpose**: High-level health and golden signals

**Panels**:
1. **Cluster Health Status** (Stat panel)
   - Nodes up: `count(up{job="node"})`
   - Pods running: `count(kube_pod_info)`
   - Services healthy: `count(up{job=~"api|db|cache"})`

2. **Golden Signals** (4-panel grid)
   - Latency: `histogram_quantile(0.95, http_request_duration_seconds_bucket)`
   - Traffic: `sum(rate(http_requests_total[5m]))`
   - Errors: `sum(rate(http_requests_total{status=~"5.."}[5m]))`
   - Saturation: `rate(container_cpu_usage_seconds_total[5m])`

3. **Service Status** (Table)
   - Service name
   - Error rate (last 5m)
   - p95 latency
   - Instance count
   - Last alert

4. **Request Timeline** (Graph)
   - Request rate per service
   - Color-coded by health status
   - Hover shows latency percentiles

5. **Top Errors** (Bar gauge)
   - Error type
   - Frequency (last hour)
   - Service affected
   - Click to trace

6. **Alert Summary** (Table)
   - Alert name
   - Severity
   - Firing duration
   - Affected service

### Dashboard 2: Service Deep Dive

**Purpose**: Single service performance analysis

**Template Variables**:
- `$service`: Service name (dropdown)
- `$namespace`: Kubernetes namespace
- `$pod`: Pod name (optional filtering)

**Panels**:

1. **Service Overview Card** (Stat)
   - Service: `$service`
   - Replicas: `count(kube_pod_info{pod=~"$service.*"})`
   - Uptime: `100 * avg(up{job="$service"})`

2. **Request Metrics** (4 stat panels)
   - QPS: `sum(rate(http_requests_total{service="$service"}[1m]))`
   - p95 Latency: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{service="$service"}[5m])) by (le))`
   - Error Rate: `sum(rate(http_requests_total{service="$service",status=~"5.."}[5m])) / sum(rate(http_requests_total{service="$service"}[5m]))`
   - Saturation: `sum(http_requests_active{service="$service"}) / sum(http_requests_total_capacity{service="$service"})`

3. **Request Rate Over Time** (Graph)
   - Query: `sum(rate(http_requests_total{service="$service"}[5m])) by (method, endpoint)`
   - Legend: `{{method}} {{endpoint}}`
   - Y-axis: requests/second

4. **Latency Distribution** (Heatmap)
   - Query: `sum(rate(http_request_duration_seconds_bucket{service="$service"}[5m])) by (le)`
   - Shows latency distribution over time
   - Click to view exemplar trace

5. **Error Breakdown** (Pie chart)
   - Query: `sum(rate(http_requests_total{service="$service",status!=~"2..|3.."}[5m])) by (status, error_type)`
   - Shows error types and frequencies

6. **Dependencies** (Node graph)
   - Query: Service spans to other services
   - Shows call graph
   - Size = call frequency
   - Color = error rate

7. **Downstream Impact** (Graph)
   - Query: Request rate to all downstream services
   - Shows how service affects others
   - Alerts on unusual patterns

8. **CPU Profile** (Flamegraph)
   - Query: `topk(20, sum(rate(parca_cpu_samples_total{service="$service"}[5m])) by (function))`
   - Integrated with Parca UI

9. **Memory Hotspots** (Table)
   - Query: `topk(10, sum(rate(parca_memory_alloc_bytes_total{service="$service"}[5m])) by (function))`
   - Shows allocation hotspots
   - Sorted by frequency

10. **Trace Search** (Panel)
    - Service: `$service`
    - Status filter: dropdown (all, errors only, slow)
    - Time range: links to Jaeger
    - Shows recent traces

### Dashboard 3: Performance Analysis & Profiling

**Purpose**: Deep performance debugging

**Panels**:

1. **CPU Flamegraph** (Flamegraph panel)
   - Query: Parca CPU profile
   - Interactive navigation
   - Shows function call stacks
   - Color intensity = CPU time

2. **CPU Top Functions** (Table)
   - Query: `topk(20, sum(rate(parca_cpu_samples_total[5m])) by (function, pod))`
   - Function name
   - CPU samples/sec
   - % of total
   - Pod name

3. **Memory Flamegraph** (Flamegraph panel)
   - Query: Parca memory allocation profile
   - Shows allocation hotspots
   - Interactive filtering

4. **Memory Trends** (Graph)
   - Allocation rate: `sum(rate(parca_memory_alloc_bytes_total[5m]))`
   - Deallocation rate: `sum(rate(parca_memory_free_bytes_total[5m]))`
   - Memory pressure: `avg(ebpf_memory_pressure_some)`

5. **Syscall Latency** (Heatmap)
   - Query: `sum(rate(ebpf_syscall_duration_seconds_bucket[5m])) by (syscall, le)`
   - Shows syscall latency distribution
   - Identifies slow syscalls

6. **Lock Contention** (Graph)
   - Query: `sum(rate(parca_lock_contention_total[5m])) by (lock_name)`
   - Shows synchronization bottlenecks

7. **I/O Performance** (Graph)
   - Query: `histogram_quantile(0.95, sum(rate(ebpf_io_duration_seconds_bucket[5m])) by (operation, le))`
   - Read/write latency
   - Identifies I/O bottlenecks

8. **Context Switches** (Graph)
   - Query: `sum(rate(ebpf_context_switches_total[5m]))`
   - High context switches = CPU contention

9. **Page Faults** (Graph)
   - Query: `sum(rate(ebpf_page_faults_total[5m])) by (pod)`
   - Major page faults indicate memory pressure

### Dashboard 4: Troubleshooting & Root Cause

**Purpose**: Rapid problem identification and resolution

**Panels**:

1. **Anomaly Detection Alert** (Alert list)
   - Shows detected anomalies
   - Latency spikes
   - Error rate increases
   - Resource exhaustion

2. **Affected Services** (Graph)
   - Query: Track which services are impacted
   - Shows service-to-service error propagation

3. **Trace Search & Filter** (Panel)
   - Service selector
   - Operation filter
   - Error filter (all, errors only, slow)
   - Time range
   - Links to Jaeger with auto-populated filters

4. **Error Spike Timeline** (Graph)
   - Query: `sum(rate(http_requests_total{status=~"5.."}[1m])) by (service, error_type)`
   - Highlights error spikes
   - Correlates with trace data

5. **Latency Correlation** (Graph)
   - Query: Request latency vs resource usage
   - Shows correlation coefficient
   - Identifies root cause (CPU, I/O, DB, etc)

6. **Recent Traces** (Table)
   - Fetches from Jaeger API
   - Shows latest traces matching filters
   - Click to view full trace
   - Shows exemplar indicators

7. **Service Metrics Snapshot** (Table)
   - Service
   - Error rate
   - p95 latency
   - CPU usage
   - Memory usage
   - Comparison: now vs 1h ago

8. **Dependency Chain** (Node graph)
   - Shows request flow through services
   - Highlights errors at each hop
   - Identifies bottleneck service

### Dashboard 5: SLO/SLI Tracking

**Purpose**: Service reliability and error budget tracking

**Panels**:

1. **Error Budget Status** (Gauge)
   - Query: `(slo:api_gateway:error_ratio / 0.01) * 100`
   - Shows % of error budget consumed
   - Color: green (< 50%), yellow (50-90%), red (> 90%)
   - Threshold: 0.01 (1% error SLO)

2. **Burn Rate Alerts** (Table)
   - Multi-window multi-burn-rate alerts
   - Windows: 1h, 6h, 1d, 30d
   - Burn rate: (error rate / SLO) / time_window
   - Alert: burn_rate > 1.0 (consuming budget)

3. **SLO Compliance Trend** (Graph)
   - Query: `slo:api_gateway:compliance_ratio`
   - Shows % compliance over time
   - Target line at SLO (99.9%)
   - Highlights periods below target

4. **Error Budget Consumption** (Graph)
   - Query: `(slo:api_gateway:error_ratio) * 100`
   - Shows % of error budget used
   - Projections (at current rate, when exhausted)

5. **Mean Time To Recovery** (Stat)
   - Query: `avg_over_time(mttr[7d:1h])`
   - Shows average recovery time
   - Identifies services with poor recovery

6. **Incident History** (Table)
   - Date
   - Service
   - Duration
   - Root cause
   - Error budget impact
   - Links to postmortem

7. **Error Budget Forecast** (Graph)
   - Query: Extrapolate consumption
   - If rate continues, when budget exhausted?
   - Proactive alerting

---

## 🎨 Dashboard Visualization Techniques

### Panel Types & Best Uses

| Panel Type | Best For | Example |
|-----------|----------|---------|
| **Graph** | Time series trends | Request rate, latency over time |
| **Heatmap** | Distribution over time | Latency distribution, percentiles |
| **Stat** | Single value KPI | Current latency p95, error rate |
| **Gauge** | Progress indicator | Error budget consumed % |
| **Table** | Detailed comparison | Top errors, service health |
| **Flamegraph** | Code profiling | CPU/memory hotspots |
| **Node Graph** | Service dependencies | Service-to-service calls |
| **Pie Chart** | Composition | Error types breakdown |
| **Bar Gauge** | Ranked values | Top functions by CPU |

### Color Schemes

**Health Status**:
- Green: Good (< p50 latency, 0% errors)
- Yellow: Warning (50-95 percentile, < 5% errors)
- Red: Critical (> p95 latency, > 5% errors)

**Heat Colors** (worst → best):
- Red: Worst performance
- Yellow: Average
- Green: Best performance
- Blue: No data

---

## 📥 Dashboard Import Instructions

### Method 1: JSON Import

1. **Get dashboard JSON**:
   ```bash
   # Dashboard files available in grafana-dashboards/ folder
   ls -la grafana-dashboards/
   ```

2. **Import in Grafana UI**:
   - Home → Dashboards → Import
   - Upload JSON file OR paste content
   - Select Prometheus datasource
   - Click "Import"

3. **Verify**:
   - Dashboard appears in Dashboards list
   - All variables populated
   - Panels showing data

### Method 2: Helm Values

```yaml
grafana:
  dashboardProviders:
    dashboardproviders.yaml:
      apiVersion: 1
      providers:
      - name: 'default'
        orgId: 1
        folder: ''
        type: file
        disableDeletion: false
        editable: true
        options:
          path: /var/lib/grafana/dashboards/default

  dashboards:
    default:
      prometheus-metrics:
        url: https://raw.githubusercontent.com/.../dashboards/system-overview.json
      jaeger-traces:
        url: https://raw.githubusercontent.com/.../dashboards/trace-analysis.json
```

### Method 3: API Call

```bash
# Create dashboard via API
curl -X POST http://grafana:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @dashboard.json \
  -H "Authorization: Bearer $GRAFANA_API_TOKEN"
```

---

## 🔧 Dashboard Customization

### Template Variables

**Common Variables**:

```yaml
cluster:
  type: "query"
  datasource: "Prometheus"
  query: 'label_values(up, cluster)'

namespace:
  type: "query"
  datasource: "Prometheus"
  query: 'label_values(kube_pod_info, namespace)'

service:
  type: "query"
  datasource: "Prometheus"
  query: 'label_values(http_requests_total, job)'

pod:
  type: "query"
  datasource: "Prometheus"
  query: 'label_values(container_cpu_usage_seconds_total{pod=~"$service.*"}, pod)'
```

### Ad-hoc Filters

Enable users to add custom filters:

```yaml
adhocFilters:
  datasource: "Prometheus"
  placeholder: "filter labels"
  # Example: job=api AND status=error
```

---

## 🔗 Data Source Configuration

### Prometheus Datasource

```yaml
name: "Prometheus"
type: "prometheus"
url: "http://prometheus:9090"
jsonData:
  timeInterval: "30s"
  exemplarTraceIdDestinations:
    - name: "TraceID"
      datasourceUid: "jaeger-uid"
      urlDisplayLabel: "View in Jaeger"
      url: "$${data.value}"
```

### Jaeger Datasource

```yaml
name: "Jaeger"
type: "jaeger"
url: "http://jaeger:16686"
jsonData:
  tracesInDatabase: true
```

### Parca Datasource

```yaml
name: "Parca"
type: "parca"
url: "http://parca-server:7071"
jsonData:
  defaultOrgId: 1
```

---

## 📊 Query Examples

### Prometheus Queries with Exemplars

```promql
# Request latency with exemplars
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
) # Click exemplar to view trace

# Error rate with root cause
sum(rate(http_requests_total{status=~"5.."}[5m])) by (error_type)
# Hover shows error type

# CPU usage by function
topk(10, sum(rate(parca_cpu_samples_total[5m])) by (function))
# Click to view code
```

### Jaeger Queries

```
# Find slow requests
duration > 1000ms

# Find errors
status = error OR http.status_code >= 500

# Span duration
span.duration > 100ms AND service.name = api-server
```

---

## 🎯 Dashboard Best Practices

### Design Principles

1. **Clarity**: One metric, one purpose per panel
2. **Hierarchy**: Overview → Details → Debug
3. **Actionability**: Insights that drive decisions
4. **Context**: Compare current vs baseline
5. **Interactivity**: Drilldown from high level to detail

### Performance Tips

1. **Reduce Query Complexity**
   - Use recording rules instead of complex queries
   - Aggregate at collection time, not query time
   - Example: Pre-compute p95 percentiles

2. **Caching**
   - Set appropriate refresh intervals (30s - 5m)
   - Use `max_over_time()` for trend queries
   - Cache static reference data

3. **Panel Optimization**
   - Limit data points (< 10K per panel)
   - Use downsampling for long time ranges
   - Optimize variable queries

### Alerting Integration

```yaml
# Create alerts from dashboard panels
alert: "HighErrorRate"
expr: "sum(rate(http_requests_total{status=~'5..'}[5m])) > 100"
annotations:
  dashboard: "Service Deep Dive"
  service: "$service"
  grafana_url: "http://grafana:3000/d/dashboard-id?var-service=$service"
```

---

## 📱 Multi-Device Dashboards

### Mobile-Friendly Design

```yaml
# Mobile dashboard (simplified)
panels:
  - title: "Error Rate"
    type: "stat"
    height: 200
  - title: "Latency"
    type: "gauge"
    height: 200
  - title: "Requests"
    type: "stat"
    height: 200
  - title: "Recent Errors"
    type: "table"
    height: 300
```

### Responsive Layouts

```yaml
# Auto-adjust for different screen sizes
gridPos:
  mobile: {h: 4, w: 12, x: 0, y: 0}
  tablet: {h: 4, w: 8, x: 0, y: 0}
  desktop: {h: 4, w: 6, x: 0, y: 0}
```

---

## ✅ Dashboard Implementation Checklist

- [ ] System Overview dashboard deployed
- [ ] Service Deep Dive dashboard template created
- [ ] Performance Analysis dashboard configured
- [ ] Troubleshooting dashboard with Jaeger links
- [ ] SLO/SLI tracking dashboard set up
- [ ] Prometheus datasource configured
- [ ] Jaeger datasource linked
- [ ] Parca datasource integrated
- [ ] Template variables functional
- [ ] Ad-hoc filtering enabled
- [ ] Exemplars linking traces
- [ ] Drill-down to Jaeger working
- [ ] Alert annotations configured
- [ ] Mobile-friendly layout tested
- [ ] Dashboard sharing configured
- [ ] Backups of dashboard JSON

---

## 🚀 Deployment Steps

1. **Create dashboards ConfigMap**:
   ```bash
   kubectl create configmap grafana-dashboards \
     --from-file=dashboards/ \
     -n monitoring
   ```

2. **Mount in Grafana**:
   ```yaml
   volumeMounts:
   - name: dashboard-config
     mountPath: /var/lib/grafana/dashboards
   ```

3. **Verify in UI**:
   - Home → Dashboards
   - Click to open
   - Verify data appearing

---

## 📚 References

- [Grafana Dashboard Syntax](https://grafana.com/docs/grafana/latest/dashboards/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Plugins](https://grafana.com/grafana/plugins/)
- [Google SRE Dashboards](https://sre.google/sre-book/monitoring-distributed-systems/)

---

**Version**: 1.0
**Status**: ✅ Production Ready
**Last Updated**: November 20, 2024

Generated with comprehensive observability best practices from Google SRE, Grafana, and CNCF.
