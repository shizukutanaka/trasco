# Service Level Objectives & Indicators Framework

**Date**: November 20, 2024
**Status**: ✅ Complete Implementation
**Focus**: Defining, measuring, and tracking service reliability

---

## 📊 Executive Summary

This framework implements **Service Level Objectives (SLOs)** and **Service Level Indicators (SLIs)**, enabling data-driven reliability management through error budgets.

### SLO vs SLI vs SLA

```
┌────────────────────────────────────────────────────────┐
│ SLA (Service Level Agreement)                          │
│ - Legal contract with customers                        │
│ - Defines penalty/credits if SLO missed                │
│ - Example: "99.9% uptime or 10% credit"               │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ SLO (Service Level Objective)                          │
│ - Internal target we commit to                         │
│ - Slightly stricter than SLA for buffer                │
│ - Example: "99.95% availability" (internal)            │
│           "99.9% availability" (customer SLA)          │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ SLI (Service Level Indicator)                          │
│ - What we actually measure                             │
│ - Example: "successful_requests / total_requests"      │
│           = 99.87% last month                          │
└────────────────────────────────────────────────────────┘

Relationship: SLI ≥ SLO means we're meeting targets ✓
             SLI < SLO means we exceeded error budget ✗
```

---

## 🎯 SLO Definition by Service Tier

### Tier 1: Critical (Financial/Security)

```yaml
service: payment-processing
slo:
  availability: 99.99%    # 4 nines = 4.38 minutes/month
  latency_p99: 100ms
  error_rate: 0.01%

error_budget_per_month: 4.38 minutes
monthly_window: 43,200 minutes (30 days)
```

### Tier 2: High (Customer-Facing)

```yaml
service: api-gateway
slo:
  availability: 99.9%     # 3 nines = 43.2 minutes/month
  latency_p99: 1000ms
  error_rate: 0.1%

error_budget_per_month: 43.2 minutes
```

### Tier 3: Standard (Internal/Non-Critical)

```yaml
service: admin-dashboard
slo:
  availability: 99.5%     # 2.5 nines = 216 minutes/month
  latency_p99: 2000ms
  error_rate: 0.5%

error_budget_per_month: 216 minutes
```

### Tier 4: Best Effort (Experimental)

```yaml
service: beta-features
slo:
  availability: 95.0%     # 1.3 nines = 36 hours/month
  latency_p99: 5000ms
  error_rate: 5.0%

error_budget_per_month: 1,296 minutes (21.6 hours)
```

---

## 📏 SLI Measurement

### SLI Types

```promql
# Availability SLI
sli:service:availability =
  successful_requests / total_requests

# Latency SLI
sli:service:latency_p99 =
  histogram_quantile(0.99, request_duration_bucket)

# Error Budget SLI
sli:service:error_budget_consumed =
  (1 - actual_availability) / (1 - target_availability)
```

### Recording Rules for SLI

```yaml
groups:
  - name: sli.rules
    interval: 30s
    rules:
      # Availability SLI
      - record: sli:api_gateway:availability
        expr: |
          (sum(rate(http_requests_total{status=~"2..|3.."}[5m]))
           / sum(rate(http_requests_total[5m])))

      # Latency SLI
      - record: sli:api_gateway:latency:p99
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          )

      # Error Budget Remaining (% of monthly budget remaining)
      - record: sli:api_gateway:error_budget_remaining
        expr: |
          (
            (1 - sli:api_gateway:availability)
            / (1 - 0.999)  # Target: 99.9%
          ) * 100

      # Error Budget Burn Rate (how fast consuming budget)
      - record: sli:api_gateway:burn_rate:5m
        expr: |
          (
            1 - sli:api_gateway:availability
          ) / (1 - 0.999)
```

---

## 💰 Error Budget Management

### Error Budget Allocation

```
Monthly Budget: 43.2 minutes (99.9% SLO)

Allocation:
├─ Planned Maintenance: 10 minutes (23%)
├─ Emergency Maintenance: 10 minutes (23%)
├─ Deployment Risk: 15 minutes (35%)
└─ Unexpected Outages: 8.2 minutes (19%)
   └─ Buffer for contingencies
```

### Error Budget Burn Rate

```promql
# How fast we're consuming the monthly error budget
burn_rate = (current_error_rate / slo_error_budget) / time_window

Examples (99.9% SLO):
├─ 0.3% error rate for 5m   → 10.0× burn (critical - page)
├─ 0.3% error rate for 1h   → 1.7× burn (warning - ticket)
└─ 0.1% error rate for 30d  → 1.0× burn (normal - monitor)
```

### Monthly Error Budget Chart

```
Day 1:  100% ████████████████████ remaining
Day 7:  85%  █████████████████░░░░ remaining
Day 14: 62%  ████████████░░░░░░░░░ remaining  ← On track
Day 21: 48%  █████████░░░░░░░░░░░░ remaining  ← Good
Day 28: 15%  ███░░░░░░░░░░░░░░░░░░ remaining  ← Warning
Day 30: 0%   ░░░░░░░░░░░░░░░░░░░░░ remaining  ← Exhausted ✗
```

---

## 📊 SLO Dashboards

### Dashboard 1: SLO Compliance

```promql
# Main SLO status
sli:api_gateway:availability               # Current SLI
slo_target: 0.999                           # Target (99.9%)
compliance: (sli / slo_target) * 100        # % of SLO
error_budget_remaining: (1 - sli / slo) * 100

Visualization:
├─ Big Number: Availability (99.87% - GREEN ✓)
├─ Gauge: Error Budget Remaining (35% - YELLOW ⚠)
├─ Graph: Availability Trend (last 30 days)
└─ Table: 30-day compliance by service
```

### Dashboard 2: Error Budget Tracking

```
Monthly Error Budget: 43.2 minutes

Consumed:
├─ Week 1: 8 minutes (failed deployment rollback)
├─ Week 2: 5 minutes (database maintenance)
├─ Week 3: 3 minutes (network incident)
└─ Week 4: 2 minutes (cache failure)
Total Used: 18 minutes (42%)
Remaining: 25 minutes (58%)
```

### Dashboard 3: Burn Rate Tracking

```
Current Burn Rate: 0.8×
├─ If continues for 30d: Normal ✓
├─ If doubles to 1.6×: Burn out in 15d ⚠
└─ If 10×: Burn out in 1.5d (CRITICAL 🔴)

Burn Rate Trend:
├─ 24h avg: 0.9× (normal)
├─ 7d avg: 0.85× (good - slightly under budget)
└─ 30d: 0.75× (excellent - conservative spending)
```

---

## 🎯 Decision Framework Using Error Budgets

### Decision: Can We Deploy?

```
Current Error Budget Remaining: 20 minutes
Deployment Risk Level: Medium (historical: 5% error rate)

Decision Logic:
├─ If budget > 50%: DEPLOY (75% margin)
├─ If budget 25-50%: DEPLOY (conservative deployment)
├─ If budget 10-25%: NO DEPLOY (wait for recovery)
└─ If budget < 10%: NO DEPLOY (emergency hold)

Decision: DEPLOY ✓ (20m > 15m threshold)
```

### Decision: Do We Need to Scale?

```
Current State:
├─ Error Rate: 0.08% (below 0.1% SLO)
├─ Latency p99: 980ms (below 1000ms SLO)
├─ Error Budget Burn: 0.9× (sustainable)

Decision: NO SCALING NEEDED ✓
Reason: All SLIs healthy, budget stable
```

### Decision: Do We Need to Invest?

```
30-Day Analysis:
├─ Error Budget Consumed: 42%
├─ Burn Rate Trend: Increasing (0.6× → 0.9×)
├─ Incidents: 3 (database, cache, deployment)

Decision: YES, INVEST ⚠
Actions:
├─ Improve database stability
├─ Add cache redundancy
├─ Improve deployment safety
Goal: Reduce burn rate from 0.9× → 0.5×
```

---

## 📋 SLO Definition Process

### Step 1: Interview Stakeholders

```
Questions to ask:
├─ What's the business impact of 1 minute downtime?
├─ What's the user tolerance for latency?
├─ What's the cost of missing SLO (penalties, lost revenue)?
└─ How does this compare to competitors?

Outcomes:
├─ Understand business requirements
├─ Set realistic, achievable SLOs
└─ Get buy-in from leadership
```

### Step 2: Define SLOs

```yaml
service: api-gateway
owners:
  - backend-team
  - platform-team

slos:
  - indicator: availability
    target: 99.9%
    measurement: successful_requests / total_requests
    window: monthly

  - indicator: latency
    target: 1000ms p99
    measurement: http_request_duration_seconds (p99)
    window: daily

  - indicator: error_rate
    target: 0.1%
    measurement: failed_requests / total_requests
    window: hourly
```

### Step 3: Implement SLI Measurement

```yaml
# Recording rules to calculate SLIs
- record: sli:api_gateway:availability
  expr: (successful / total) * 100

- record: sli:api_gateway:latency:p99
  expr: histogram_quantile(0.99, duration_bucket)

- record: sli:api_gateway:error_rate
  expr: (errors / total) * 100
```

### Step 4: Implement Alerting

```yaml
# Alert when burn rate exceeds thresholds
- alert: ErrorBudgetBurnCritical
  expr: burn_rate > 10
  for: 5m
  action: page_on_call

- alert: ErrorBudgetBurnWarning
  expr: burn_rate > 3
  for: 15m
  action: create_ticket
```

### Step 5: Monitor & Review

```
Weekly Reviews:
├─ Is SLO being met? (YES/NO)
├─ What caused incidents?
├─ Are burn rates normal?
└─ Any trends?

Monthly Reviews:
├─ Monthly SLO compliance (target > 99.9%)
├─ Error budget spent (target < 100%)
├─ Incident postmortems
└─ Planned improvements

Quarterly Reviews:
├─ Are SLOs still realistic?
├─ Do they align with business goals?
├─ Should we increase target?
└─ SLO adjustment if needed
```

---

## 🏆 Best Practices

### DO ✅

```yaml
# DO: Set realistic SLOs based on current performance
# Find your 99th percentile, then set SLO at 95th

# DO: Include outage windows in error budget
deployment_window: 10 min/month
maintenance_window: 10 min/month
unexpected_outages: 23 min/month (remaining budget)

# DO: Align SLO with business needs
financial_services: 99.99% (4 nines)
e_commerce: 99.9% (3 nines)
internal_tools: 99.5% (2.5 nines)

# DO: Automate SLI measurement
# Use Prometheus recording rules, not manual calculation

# DO: Review SLOs quarterly
# Adjust if consistently over/under performing
```

### DON'T ❌

```yaml
# DON'T: Set SLOs too high
# Example: 99.999% (5 nines) is impractical for startups
# Reality: Most services operate at 99-99.9%

# DON'T: Use SLOs for punishment
# SLOs are targets, not guaranteed contracts
# Use for capacity planning, not blame

# DON'T: Ignore error budget
# "We have budget, let's deploy risky change"
# Remember: Budget must last entire month

# DON'T: Set SLOs without ops input
# Will be either too high (impossible) or too low (useless)
# Ops knows what's achievable
```

---

## 📊 Metrics & Monitoring

### Key Metrics

```promql
# SLI Metrics
sli:service:availability
sli:service:latency:p99
sli:service:error_rate
sli:service:burn_rate

# Error Budget Metrics
slo:service:error_budget_remaining
slo:service:error_budget_consumed
slo:service:burn_rate:5m
slo:service:burn_rate:1h
```

### Alert Rules

```yaml
# Burn rate alerts (already defined in ADVANCED_ALERTING_GUIDE.md)
- alert: ErrorBudgetBurnRateFast
  expr: burn_rate > 10
  for: 5m
  severity: critical

- alert: ErrorBudgetBurnRateMedium
  expr: burn_rate > 3
  for: 15m
  severity: warning

- alert: ErrorBudgetExhausted
  expr: error_budget_remaining <= 0
  for: 10m
  severity: critical
  action: "STOP all non-critical changes"
```

---

## 🎓 References

### Research Sources

- **Google SRE Book**: Chapter on SLOs and error budgets
- **Google Devel**: "The SLO Framework: Setting Reliability Expectations"
- **Prometheus**: Best practices for SLI measurement
- **CRE Best Practices**: Service level objectives

### Industry Examples

- **Google**: 99.99% SLO across most services
- **Amazon AWS**: 99.99% availability for critical services
- **Netflix**: Sophisticated SLO framework across 700+ services
- **Stripe**: 99.99% SLO for payment processing

---

**Version**: 1.0
**Status**: ✅ Production Ready
**Last Updated**: November 20, 2024

Generated with comprehensive research from Google SRE, Prometheus, and industry best practices.
