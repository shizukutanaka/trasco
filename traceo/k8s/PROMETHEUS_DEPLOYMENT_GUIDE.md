# Advanced Prometheus Deployment Guide for Production

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Deployment Methods](#deployment-methods)
3. [Configuration Details](#configuration-details)
4. [Performance Tuning](#performance-tuning)
5. [Cardinality Management](#cardinality-management)
6. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
7. [Cost Optimization](#cost-optimization)
8. [Migration Path](#migration-path)

---

## Architecture Overview

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Kubernetes Cluster (traceo)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Application A   │  │  Application B   │  │  Application C   │  │
│  │  (metrics)       │  │  (metrics)       │  │  (metrics)       │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │                     │                     │             │
│           └─────────────────────┼─────────────────────┘             │
│                                 │                                   │
│                    ┌────────────▼────────────┐                      │
│                    │  Prometheus (StatefulSet)                      │
│                    │  - pod 0 (prometheus-0)                        │
│                    │  - pod 1 (prometheus-1)                        │
│                    │  - Shared PVC (100GB ea.)                      │
│                    └────────────┬────────────┘                      │
│                                 │                                   │
│         ┌───────────────────────┼───────────────────────┐           │
│         │                       │                       │           │
│    ┌────▼────┐           ┌──────▼────────┐      ┌──────▼─────┐    │
│    │ Alerting │           │   Querying    │      │ Remote Write│    │
│    │(Alert-   │           │  (Grafana)    │      │ (Mimir)     │    │
│    │manager)  │           │               │      │             │    │
│    └──────────┘           └───────────────┘      └─────────────┘    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
        │                        │                          │
        │                        │                          │
        ▼                        ▼                          ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│   AlertManager   │  │    Grafana       │  │  Mimir (Long-term)   │
│   (Cluster)      │  │  (Dashboards)    │  │  (Deduplication)     │
└──────────────────┘  └──────────────────┘  └──────────────────────┘
```

### Data Flow

1. **Scraping**: Prometheus scrapes metrics from endpoints (K8s, apps, exporters)
2. **Evaluation**: Rules are evaluated every 30s
   - Recording rules: Pre-aggregate expensive queries
   - Alert rules: Determine which alerts to fire
3. **Storage**: Metrics stored in local TSDB (90-day retention)
4. **Remote Write**: Samples sent to Mimir for long-term storage
5. **Querying**: Grafana queries from Prometheus (for dashboards) and Mimir (for history)
6. **Alerting**: Fired alerts sent to Alertmanager for routing

---

## Deployment Methods

### Method 1: Using Helm (Recommended for Production)

#### Installation Steps

```bash
# Add Prometheus Community Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create monitoring namespace
kubectl create namespace monitoring

# Create values file
cat > prometheus-values.yaml <<'EOF'
# Prometheus Operator values
prometheus:
  prometheusSpec:
    image:
      tag: v2.50.0

    # High Availability (2 replicas)
    replicas: 2

    # Resource requests and limits
    resources:
      requests:
        cpu: 500m
        memory: 2Gi
      limits:
        cpu: 2000m
        memory: 4Gi

    # Storage configuration
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: fast-ssd
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 100Gi

    # Retention settings
    retention: 90d
    retentionSize: "50GB"

    # WAL compression
    walCompression: true

    # External labels
    externalLabels:
      cluster: "traceo-prod"
      environment: "production"

    # Affinity for pod distribution
    affinity:
      podAntiAffinity:
        preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                  - key: app.kubernetes.io/name
                    operator: In
                    values: ["prometheus"]
              topologyKey: kubernetes.io/hostname

    # Service monitors
    serviceMonitorSelector: {}
    serviceMonitorNamespaceSelector: {}

    # Rule selectors
    ruleSelector: {}
    ruleNamespaceSelector: {}

    # Query configuration
    queryTimeout: "2m"
    queryMaxConcurrency: 20
    queryMaxSamples: 50000000

    # Remote write (Mimir)
    remoteWrite:
      - url: http://mimir-distributor.monitoring:8080/api/v1/push
        queueConfig:
          capacity: 10000
          maxShards: 200
          minShards: 1
          maxSamplesPerSend: 5000
          batchSendDeadline: 5s
          minBackoff: 30ms
          maxBackoff: 5s

# Alertmanager configuration
alertmanager:
  enabled: true
  alertmanagerSpec:
    replicas: 2
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 200m
        memory: 256Mi

# Prometheus Operator
prometheusOperator:
  enabled: true

# Node Exporter
nodeExporter:
  enabled: true

# Kube State Metrics
kubeStateMetrics:
  enabled: true

# Grafana
grafana:
  enabled: true
  adminPassword: $(kubectl -n monitoring get secret --sort-by=.metadata.creationTimestamp -1 | base64 --decode | cut -d ',' -f 2)

EOF

# Install Prometheus stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  -f prometheus-values.yaml \
  --namespace monitoring \
  --create-namespace
```

#### Verify Installation

```bash
# Check Prometheus deployment
kubectl get pods -n monitoring
kubectl get pvc -n monitoring
kubectl get svc -n monitoring

# Access Prometheus UI
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090
# Visit http://localhost:9090

# Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:3000
# Visit http://localhost:3000 (admin / prom-operator)
```

### Method 2: Using Kubectl (Manual Application)

```bash
# Apply Prometheus configuration
kubectl apply -f prometheus-config.yaml
kubectl apply -f prometheus-advanced-config.yaml
kubectl apply -f prometheus-operator-config.yaml

# Verify
kubectl get statefulsets -n traceo
kubectl get configmaps -n traceo
kubectl get svc -n traceo
```

---

## Configuration Details

### Scrape Configuration Best Practices

#### 1. Scrape Intervals by Priority

```yaml
# CRITICAL: API Gateway (15s)
# - Request rate, error rate, latency
# - SLO monitoring
# - Incident detection

# STANDARD: Services (30s)
# - Business logic metrics
# - Database queries
# - Cache operations

# INFRASTRUCTURE: Nodes (60s)
# - CPU, memory, disk
# - Network I/O
# - Lower priority alerts
```

#### 2. Metric Relabeling Strategy

```promql
# Problem: High cardinality from unique user IDs in request paths
# Example: /api/users/123456789 - each unique ID is a separate series

# Solution 1: Drop the metric entirely
metric_relabel_configs:
  - source_labels: [__name__]
    regex: 'http_request_path'
    action: drop

# Solution 2: Aggregate to higher-level category
metric_relabel_configs:
  - source_labels: [user_id]
    regex: '(\d).*'
    target_label: user_bucket
    replacement: '${1}X'
    action: replace

# Solution 3: Drop when specific label exists
metric_relabel_configs:
  - source_labels: [debug_label]
    action: drop
    regex: 'true'
```

#### 3. Label Cardinality Limits

```yaml
scrape_configs:
  - job_name: 'applications'
    kubernetes_sd_configs:
      - role: pod

    # Cardinality protection
    sample_limit: 100000          # Max samples per scrape
    label_limit: 50               # Max labels per metric
    label_name_length_limit: 128  # Max label name length
    label_value_length_limit: 256 # Max label value length
```

---

## Performance Tuning

### 1. TSDB Block Optimization

```yaml
args:
  # Default: 2h initial, compacted up to 10% of retention
  - --storage.tsdb.min-block-duration=2h
  - --storage.tsdb.max-block-duration=4h  # Faster compaction

  # WAL settings
  - --storage.tsdb.wal-compression        # 50% size reduction

  # Retention
  - --storage.tsdb.retention.time=90d
  - --storage.tsdb.retention.size=50GB
```

**Impact Analysis**:
- Smaller max-block-duration: Lower query latency, more I/O
- Larger max-block-duration: Higher query latency, less I/O
- WAL compression: 50% storage savings, negligible CPU (<1%)

### 2. Memory Optimization

```
Memory Calculation for 1M active series:
- Head Block: 1M series × 8KB = 8GB
- WAL (3 segments): 128MB × 3 = 384MB
- Queries: 20% × (8GB + 0.4GB) ≈ 1.7GB
- Overhead: 20% × 8.4GB ≈ 1.7GB
- Total: ~12GB minimum, 16GB recommended, 24GB safe
```

```yaml
# Kubernetes resource allocation
resources:
  requests:
    memory: 16Gi
    cpu: 4
  limits:
    memory: 24Gi
    cpu: 8

# Go GC tuning
env:
  - name: GOGC
    value: "75"  # More aggressive GC (default: 100)
```

### 3. Query Performance

```promql
# BAD: Scans all series
rate(http_requests_total[5m])

# GOOD: Filter early
rate(http_requests_total{job="api"}[5m])

# BETTER: Use recording rule
rate(job:http_requests:rate5m{job="api"})

# Aggregation
# BAD: Keep all dimensions
http_requests_total

# GOOD: Drop unnecessary labels
sum without (instance, pod) (http_requests_total)

# Regex matching (expensive)
# BAD: Complex regex
path=~"/api/users/.*"

# GOOD: Use pre-aggregated metric
job="user-api"
```

---

## Cardinality Management

### 1. Identifying Cardinality Issues

```bash
# Top 10 metrics by cardinality
curl -s 'http://prometheus:9090/api/v1/query?query=topk(10,count(__)%20by%20(__name__))' | jq '.'

# Cardinality per metric
curl -s 'http://prometheus:9090/api/v1/query?query=count(http_requests_total)' | jq '.'

# Series growth rate
curl -s 'http://prometheus:9090/api/v1/query?query=rate(prometheus_tsdb_symbol_table_size_bytes[5m])' | jq '.'
```

### 2. Prevention Strategies

| Metric | Root Cause | Solution |
|--------|-----------|----------|
| http_request_path | Unique URLs | Drop or aggregate by endpoint |
| user_id | User IDs in labels | Remove or use user_segment |
| pod_name | Pod name per instance | Keep it (needed for debugging) |
| trace_id | Distributed tracing | Use as exemplar, not label |
| version | API version in label | Use with low cardinality values |

### 3. Cardinality Dashboard

```promql
# Cardinality over time
count({__name__=~".+"})

# Series growth rate
rate(prometheus_tsdb_symbol_table_size_bytes[1h])

# Top metrics by cardinality
topk(20, count by (__name__)({__name__=~".+"}))

# High-cardinality metrics
sum by (__name__) (
  count by (__name__, job) ({__name__=~".+"})
) > 1000000
```

---

## Monitoring & Troubleshooting

### Common Issues & Solutions

#### Issue 1: Out of Memory

**Symptoms**: Prometheus pod killed with OOMKilled

**Diagnosis**:
```bash
# Check current cardinality
kubectl exec -n traceo prometheus-0 -- \
  curl -s 'localhost:9090/api/v1/query?query=count(__)%20by%20(__name__)' | jq '.data.result | length'

# Check memory usage
kubectl top pod -n traceo prometheus-0

# Check scrape targets
kubectl exec -n traceo prometheus-0 -- \
  curl -s 'localhost:9090/api/v1/targets'
```

**Solution**:
1. Reduce cardinality via metric relabeling
2. Increase scrape interval (60s → 90s)
3. Drop unnecessary metrics
4. Increase memory limits

#### Issue 2: High Query Latency

**Diagnosis**:
```promql
# Query latency
histogram_quantile(0.99, rate(prometheus_engine_query_duration_seconds_bucket[5m]))

# Number of concurrent queries
prometheus_engine_queries

# Largest query result
rate(prometheus_engine_query_results_total[5m])
```

**Solution**:
1. Create recording rules for expensive queries
2. Increase `--query.max-concurrency`
3. Reduce time range for dashboards
4. Use `without()` to reduce output series

#### Issue 3: Remote Write Backlog

**Diagnosis**:
```promql
# Backlog size
prometheus_remote_storage_samples_dropped_total

# Queue depth
prometheus_remote_storage_samples_pending

# Retry rate
rate(prometheus_remote_storage_retries_total[5m])
```

**Solution**:
1. Increase `maxShards` in remote_write config
2. Check Mimir/Thanos cluster health
3. Increase `batch_send_deadline`
4. Check network connectivity

### Debugging Checklist

```bash
# 1. Pod status
kubectl describe pod -n traceo prometheus-0

# 2. Logs
kubectl logs -n traceo prometheus-0 -c prometheus --tail=100

# 3. Configuration validation
kubectl exec -n traceo prometheus-0 -- \
  promtool check config /etc/prometheus/prometheus.yml

# 4. Rules validation
kubectl exec -n traceo prometheus-0 -- \
  promtool check rules /etc/prometheus/rules/*.yml

# 5. TSDB health
kubectl exec -n traceo prometheus-0 -- \
  curl -s 'localhost:9090/api/v1/status/runtimeinfo'

# 6. Storage health
kubectl exec -n traceo prometheus-0 -- \
  ls -lh /prometheus/wal
```

---

## Cost Optimization

### Storage Tiering

```yaml
# 1. Local SSD (hot) - 15 days
storage:
  tsdb:
    retention:
      time: 15d
      size: 500GB

# 2. S3 with Intelligent-Tiering (warm/cold) - 90+ days
remote_write:
  - url: http://s3-endpoint/api/v1/write
    storage_class: INTELLIGENT_TIERING

# 3. Lifecycle Policy (AWS S3)
Rules:
  - Days: 30 → STANDARD_IA (infrequent access)
  - Days: 90 → GLACIER_IR (instant retrieval)
  - Days: 365 → DEEP_ARCHIVE
```

### Scrape Optimization

```
Baseline: 10M active series @ 30s scrape
- Samples/sec: 333,333
- Daily data: 28.8B samples
- Storage/day: ~144GB

Cost Reduction Options:

1. Extend scrape interval (30s → 60s): 50% reduction
   - Cost: 50% less data
   - Trade-off: Alert latency +30s

2. Drop unused metrics: 20-30% reduction
   - Cost: 20-30% less data
   - Trade-off: Less visibility

3. Reduce cardinality: 40-50% reduction
   - Cost: 40-50% less series
   - Trade-off: Less granular debugging

Combined Effect:
- Original: 144GB/day × 365 × $0.10/GB = $5,256/year (storage only)
- Optimized: 50GB/day × 365 × $0.10/GB = $1,825/year
- Savings: 65% ($3,431/year)
```

---

## Migration Path

### Phase 1: Baseline (Week 1)
- [ ] Deploy Prometheus with 1 replica
- [ ] Set up basic scrape configs
- [ ] Create basic alert rules
- [ ] Establish baseline metrics

### Phase 2: High Availability (Week 2)
- [ ] Upgrade to 2 replicas
- [ ] Set up PodDisruptionBudget
- [ ] Configure pod anti-affinity
- [ ] Test failover scenarios

### Phase 3: Advanced Features (Week 3-4)
- [ ] Add remote write to Mimir
- [ ] Implement SLO/SLI rules
- [ ] Set up Prometheus Operator
- [ ] Configure ServiceMonitors

### Phase 4: Optimization (Week 5-6)
- [ ] Analyze cardinality
- [ ] Optimize scrape configs
- [ ] Create recording rules
- [ ] Cost analysis & reduction

### Phase 5: Monitoring & Maintenance (Ongoing)
- [ ] Daily health checks
- [ ] Weekly cardinality review
- [ ] Monthly cost optimization
- [ ] Quarterly config audit

---

## Key Metrics to Monitor

### Prometheus Health

```promql
# Scrape success rate
rate(prometheus_tsdb_blocks_loaded[5m])

# Cardinality growth
rate(prometheus_tsdb_symbol_table_size_bytes[1h])

# Rule evaluation latency
histogram_quantile(0.99, rate(prometheus_rule_evaluation_duration_seconds[5m]))

# Remote write lag
rate(prometheus_remote_storage_samples_total[5m])
```

### Application SLOs

```promql
# Availability (error rate)
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Latency (p99)
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Saturation (resource utilization)
100 - (avg by (node) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

---

## References & Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/alerting/)
- [Google SRE Book - Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)
- [CNCF SLO Workgroup](https://github.com/cncf/sig-observability/tree/main/slos-workgroup)
- [Thanos Documentation](https://thanos.io/tip/thanos/introduction.md/)
- [Grafana Mimir Documentation](https://grafana.com/docs/mimir/latest/)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [Sloth (SLO generator)](https://sloth.dev/)

---

## Support & Troubleshooting

For issues or questions:
1. Check Prometheus logs: `kubectl logs -n traceo prometheus-0`
2. Validate configuration: `promtool check config prometheus.yml`
3. Review alert rules: `promtool check rules *.yml`
4. Check Prometheus targets: Visit http://prometheus:9090/targets
5. Consult Prometheus documentation: https://prometheus.io/docs/

**Created**: 2024-11-20
**Version**: 2.0 (Advanced Production Setup)
**Last Updated**: 2024-11-20
