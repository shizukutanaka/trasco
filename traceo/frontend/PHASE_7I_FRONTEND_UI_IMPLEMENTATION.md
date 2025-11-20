# Phase 7I: Frontend UI Implementation Plan

**Date**: November 20, 2024
**Status**: 🎨 Design & Architecture Phase
**Priority**: Critical (4-6 weeks effort)
**Scope**: MVP covering core observability workflows

---

## 🎯 UI Architecture Overview

### Technology Stack

```
Frontend Framework: React 18 + TypeScript
UI Component Library: Recharts (visualizations) + Mantine (components)
State Management: React Query + Zustand
Real-time: WebSocket + Socket.io
Testing: Vitest + React Testing Library
Build: Vite
Deployment: Docker + Kubernetes (NextJS optional for SSR)
```

### Directory Structure

```
traceo-ui/
├── src/
│   ├── components/
│   │   ├── Dashboard/
│   │   ├── Alerts/
│   │   ├── Incidents/
│   │   ├── Services/
│   │   ├── Traces/
│   │   ├── Logs/
│   │   ├── Metrics/
│   │   ├── Cost/
│   │   └── Common/
│   ├── pages/
│   │   ├── DashboardPage
│   │   ├── AlertsPage
│   │   ├── IncidentsPage
│   │   ├── ServicesPage
│   │   ├── ExplorerPage
│   │   └── SettingsPage
│   ├── api/
│   │   ├── prometheus.ts
│   │   ├── jaeger.ts
│   │   ├── loki.ts
│   │   ├── parca.ts
│   │   └── incidents.ts
│   ├── hooks/
│   ├── types/
│   ├── utils/
│   ├── theme/
│   └── App.tsx
├── public/
├── package.json
└── vite.config.ts
```

---

## 📊 Core UI Pages

### 1. Dashboard Page (Landing/Overview)

**Purpose**: Real-time system health overview

**Components**:
- System Health Card (% healthy services)
- Recent Incidents Timeline (last 24h)
- Top Errors by Service (bar chart)
- Service Dependency Map (D3.js visualization)
- SLO Compliance Gauge
- Active Alerts Widget

**Mockup**:
```
┌─────────────────────────────────────────────┐
│ 🔍 TRACEO DASHBOARD                    [⚙️] │
├─────────────────────────────────────────────┤
│                                             │
│  ✓ System Health: 98.7%  |  5 Healthy      │
│  🔴 Critical Alerts: 2   |  ⚠️ Warnings: 5  │
│                                             │
│ ┌─── RECENT INCIDENTS ─────────────────┐   │
│ │ • 14:32 Database slow queries (5m)   │   │
│ │ • 13:15 API timeout (2h)             │   │
│ │ • 09:45 Memory spike (resolved)      │   │
│ └─────────────────────────────────────┘   │
│                                             │
│ ┌─── TOP ERRORS ────────┐ ┌─ SLO STATUS ─┐ │
│ │ api-gateway    450 err│ │ api: 99.8% ✓ │ │
│ │ auth-service   320 err│ │ db:  99.5% ✓ │ │
│ │ email-ingest    95 err│ │ cache: 98% ⚠️│ │
│ └──────────────────────┘ └───────────────┘ │
│                                             │
└─────────────────────────────────────────────┘
```

### 2. Alerts Page

**Purpose**: Manage, acknowledge, and resolve alerts

**Features**:
- Alert list (filtering by severity, service, status)
- Alert details (metric, value, threshold, history)
- Acknowledge/Resolve actions
- Alert history timeline
- Bulk actions (snooze, resolve multiple)
- Alert rules management

**Implementation Example**:

```typescript
// src/components/Alerts/AlertsPage.tsx
import React, { useState, useEffect } from 'react';
import { useQuery } from 'react-query';
import { Container, Table, Badge, Button, Group } from '@mantine/core';
import { BarChart } from 'recharts';

export interface Alert {
  id: string;
  name: string;
  status: 'firing' | 'resolved';
  severity: 'critical' | 'warning' | 'info';
  service: string;
  timestamp: number;
  value: number;
  threshold: number;
}

export const AlertsPage: React.FC = () => {
  const { data: alerts, isLoading } = useQuery('alerts', async () => {
    const response = await fetch('/api/alerts');
    return response.json() as Promise<Alert[]>;
  });

  const [filter, setFilter] = useState<'all' | 'critical' | 'warning'>('all');

  const filteredAlerts = alerts?.filter(a =>
    filter === 'all' ? true : a.severity === filter
  ) || [];

  return (
    <Container>
      <h1>🔔 Alerts</h1>

      <Group mb="md">
        <Button
          variant={filter === 'all' ? 'filled' : 'light'}
          onClick={() => setFilter('all')}
        >
          All ({alerts?.length || 0})
        </Button>
        <Button
          variant={filter === 'critical' ? 'filled' : 'light'}
          color="red"
          onClick={() => setFilter('critical')}
        >
          Critical ({alerts?.filter(a => a.severity === 'critical').length || 0})
        </Button>
        <Button
          variant={filter === 'warning' ? 'filled' : 'light'}
          color="yellow"
          onClick={() => setFilter('warning')}
        >
          Warning ({alerts?.filter(a => a.severity === 'warning').length || 0})
        </Button>
      </Group>

      <Table striped highlightOnHover>
        <thead>
          <tr>
            <th>Alert Name</th>
            <th>Service</th>
            <th>Severity</th>
            <th>Value</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredAlerts.map(alert => (
            <tr key={alert.id}>
              <td>{alert.name}</td>
              <td>{alert.service}</td>
              <td>
                <Badge
                  color={
                    alert.severity === 'critical'
                      ? 'red'
                      : alert.severity === 'warning'
                      ? 'yellow'
                      : 'blue'
                  }
                >
                  {alert.severity}
                </Badge>
              </td>
              <td>{alert.value.toFixed(2)}</td>
              <td>
                <Badge
                  color={alert.status === 'firing' ? 'red' : 'green'}
                  variant="dot"
                >
                  {alert.status}
                </Badge>
              </td>
              <td>
                <Group spacing="xs">
                  {alert.status === 'firing' && (
                    <>
                      <Button
                        size="xs"
                        variant="light"
                        onClick={() => acknowledgeAlert(alert.id)}
                      >
                        Acknowledge
                      </Button>
                      <Button
                        size="xs"
                        variant="light"
                        color="green"
                        onClick={() => resolveAlert(alert.id)}
                      >
                        Resolve
                      </Button>
                    </>
                  )}
                </Group>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Container>
  );
};
```

### 3. Incidents Page

**Purpose**: Track and manage incidents

**Features**:
- Incident list with timeline
- Incident details (alerts, timeline, participants)
- War room collaboration (real-time updates)
- Post-mortem template
- Incident metrics (MTTD, MTTR, MTBF)

### 4. Services Page

**Purpose**: View service catalog and health

**Features**:
- Service list with health status
- Service dependency graph (interactive D3.js)
- Per-service metrics (error rate, latency, throughput)
- Service SLO compliance
- Logs/traces for service

### 5. Explorer Page (Unified Query Interface)

**Purpose**: Query metrics, logs, and traces

**Features**:
- Multi-source query builder
- Prometheus PromQL editor
- Loki LogQL editor
- Jaeger trace search
- Combined results view
- Query templates/bookmarks

### 6. Cost Dashboard

**Purpose**: Cost visibility and chargeback

**Features**:
- Monthly cost trend
- Cost by team/service
- Cost per operation
- Cost anomalies
- Cost forecasting
- Chargeback reports

---

## 🏗️ React Components Library

### API Client

```typescript
// src/api/prometheus.ts
import axios, { AxiosInstance } from 'axios';

export class PrometheusClient {
  private client: AxiosInstance;

  constructor(baseURL = 'http://prometheus:9090') {
    this.client = axios.create({ baseURL });
  }

  async query(promql: string) {
    const response = await this.client.get('/api/v1/query', {
      params: { query: promql }
    });
    return response.data.data.result;
  }

  async queryRange(promql: string, start: number, end: number, step: number) {
    const response = await this.client.get('/api/v1/query_range', {
      params: { query: promql, start, end, step }
    });
    return response.data.data.result;
  }

  async getMetrics() {
    const response = await this.client.get('/api/v1/label/__name__/values');
    return response.data.data;
  }
}

// src/api/jaeger.ts
export class JaegerClient {
  private baseURL: string;

  constructor(baseURL = 'http://jaeger:16686') {
    this.baseURL = baseURL;
  }

  async searchTraces(service: string, operation?: string, limit = 20) {
    const response = await fetch(
      `${this.baseURL}/api/traces?service=${service}&operation=${operation}&limit=${limit}`
    );
    return response.json();
  }

  async getTrace(traceID: string) {
    const response = await fetch(`${this.baseURL}/api/traces/${traceID}`);
    return response.json();
  }
}

// src/api/loki.ts
export class LokiClient {
  private baseURL: string;

  constructor(baseURL = 'http://loki:3100') {
    this.baseURL = baseURL;
  }

  async queryRange(query: string, start: number, end: number) {
    const response = await fetch(
      `${this.baseURL}/loki/api/v1/query_range?query=${query}&start=${start}&end=${end}`
    );
    return response.json();
  }
}
```

### Key Components

```typescript
// src/components/Common/MetricChart.tsx
import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

interface DataPoint {
  timestamp: number;
  value: number;
}

interface MetricChartProps {
  data: DataPoint[];
  title: string;
  color?: string;
  unit?: string;
}

export const MetricChart: React.FC<MetricChartProps> = ({
  data,
  title,
  color = '#1f77b4',
  unit = ''
}) => {
  const formattedData = data.map(d => ({
    ...d,
    time: new Date(d.timestamp * 1000).toLocaleTimeString()
  }));

  return (
    <div>
      <h3>{title}</h3>
      <LineChart width={600} height={300} data={formattedData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" />
        <YAxis label={{ value: unit, angle: -90, position: 'insideLeft' }} />
        <Tooltip />
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          isAnimationActive={false}
          dot={false}
        />
      </LineChart>
    </div>
  );
};

// src/components/Services/ServiceDependencyGraph.tsx
import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface Node {
  id: string;
  label: string;
  health: 'healthy' | 'degraded' | 'down';
}

interface Link {
  source: string;
  target: string;
  latency: number;
}

interface ServiceDependencyGraphProps {
  nodes: Node[];
  links: Link[];
}

export const ServiceDependencyGraph: React.FC<ServiceDependencyGraphProps> = ({
  nodes,
  links
}) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const width = 800;
    const height = 600;

    const svg = d3.select(svgRef.current);

    // Create force simulation
    const simulation = d3
      .forceSimulation(nodes as any)
      .force(
        'link',
        d3.forceLink(links).id((d: any) => d.id)
      )
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2));

    // Draw links
    const link = svg
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .style('stroke', '#999')
      .style('stroke-width', 2);

    // Draw nodes
    const node = svg
      .selectAll('circle')
      .data(nodes)
      .enter()
      .append('circle')
      .attr('r', 10)
      .style('fill', (d: any) => {
        switch (d.health) {
          case 'healthy': return '#4CAF50';
          case 'degraded': return '#FFC107';
          case 'down': return '#F44336';
          default: return '#999';
        }
      })
      .call(
        d3.drag()
          .on('start', dragStarted)
          .on('drag', dragged)
          .on('end', dragEnded) as any
      );

    // Add labels
    const labels = svg
      .selectAll('text')
      .data(nodes)
      .enter()
      .append('text')
      .text((d: any) => d.label)
      .style('font-size', '12px')
      .style('text-anchor', 'middle');

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node
        .attr('cx', (d: any) => d.x)
        .attr('cy', (d: any) => d.y);

      labels
        .attr('x', (d: any) => d.x)
        .attr('y', (d: any) => d.y);
    });

    function dragStarted(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event: any, d: any) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragEnded(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }
  }, [nodes, links]);

  return <svg ref={svgRef} width={800} height={600} />;
};
```

---

## 🚀 Development Setup

### 1. Initialize React Project

```bash
npm create vite@latest traceo-ui -- --template react-ts
cd traceo-ui
npm install

# Add dependencies
npm install @mantine/core @mantine/hooks mantine-datatable
npm install recharts d3 @types/d3
npm install react-query axios
npm install zustand socket.io-client
npm install @tabler/icons-react
npm install -D @types/react @types/node typescript vitest @testing-library/react
```

### 2. Theme Configuration

```typescript
// src/theme.ts
import { MantineThemeOverride } from '@mantine/core';

export const theme: MantineThemeOverride = {
  primaryColor: 'blue',
  colors: {
    gray: [
      '#f8f9fa',
      '#f1f3f5',
      '#e9ecef',
      '#dee2e6',
      '#ced4da',
      '#adb5bd',
      '#868e96',
      '#495057',
      '#212529',
      '#0d1117',
    ],
  },
  fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  headings: {
    fontFamily: '"Inter", sans-serif',
    sizes: {
      h1: { fontSize: '2.5rem', fontWeight: 700 },
      h2: { fontSize: '2rem', fontWeight: 600 },
      h3: { fontSize: '1.5rem', fontWeight: 600 },
    },
  },
  globalStyles: (theme) => ({
    body: {
      backgroundColor: theme.colors.gray[0],
    },
  }),
};
```

---

## 📋 Implementation Timeline

### Week 1: Foundation & Core Components
- [ ] React project setup
- [ ] Routing and layout
- [ ] Theme and styling
- [ ] API clients (Prometheus, Jaeger, Loki)
- [ ] Common components (charts, tables, badges)

### Week 2: Core Pages
- [ ] Dashboard page
- [ ] Alerts page
- [ ] Services page (list only)
- [ ] Basic routing between pages

### Week 3: Advanced Features
- [ ] Service dependency graph
- [ ] Incidents page
- [ ] Explorer page (metric queries)
- [ ] Cost dashboard

### Week 4-6: Polish & Integration
- [ ] Real-time updates (WebSocket)
- [ ] Dark mode
- [ ] Mobile responsiveness
- [ ] Accessibility (WCAG 2.1)
- [ ] Performance optimization
- [ ] Deployment (Docker + Kubernetes)

---

## 🎨 UI/UX Best Practices

1. **Readability**: Large, clear fonts (16px base)
2. **Contrast**: WCAG AA compliance (4.5:1 ratio)
3. **Responsiveness**: Mobile-first approach
4. **Dark Mode**: Eye-friendly dark color scheme
5. **Loading States**: Clear spinners and skeletons
6. **Error Messages**: Actionable error text
7. **Keyboard Navigation**: Full keyboard support
8. **Accessibility**: Alt text for images, ARIA labels

---

**Version**: 1.0
**Status**: 🎨 Ready for Implementation
**Next Steps**: Begin Week 1 implementation with React project setup

This UI will transform Traceo from a backend-only system to a complete observability platform with intuitive user interfaces.
