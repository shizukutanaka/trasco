import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface Metric {
  timestamp: number
  value: number
  labels: Record<string, string>
}

export interface Alert {
  id: string
  name: string
  severity: 'critical' | 'warning' | 'info'
  state: 'firing' | 'resolved'
  timestamp: number
  description: string
  service: string
}

export interface Service {
  name: string
  status: 'healthy' | 'degraded' | 'down'
  latency_p99: number
  error_rate: number
  throughput: number
  dependencies: string[]
}

export interface Incident {
  id: string
  title: string
  service: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  status: 'open' | 'acknowledged' | 'resolved'
  created_at: string
  resolved_at?: string
  duration_minutes?: number
}

// Hooks for Prometheus metrics
export const useMetrics = (query: string, timeRange: 'hour' | 'day' | 'week' = 'hour') => {
  return useQuery({
    queryKey: ['metrics', query, timeRange],
    queryFn: async () => {
      const end = Math.floor(Date.now() / 1000)
      const start = end - (timeRange === 'hour' ? 3600 : timeRange === 'day' ? 86400 : 604800)

      const response = await apiClient.get('/prometheus/query_range', {
        params: {
          query,
          start,
          end,
          step: '60s',
        },
      })

      return response.data.data.result
    },
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 10000,
  })
}

// Hooks for alerts
export const useAlerts = () => {
  return useQuery({
    queryKey: ['alerts'],
    queryFn: async () => {
      const response = await apiClient.get('/alerts')
      return response.data.alerts as Alert[]
    },
    refetchInterval: 15000, // Refetch every 15 seconds
    staleTime: 5000,
  })
}

export const useAcknowledgeAlert = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (alertId: string) => {
      await apiClient.post(`/alerts/${alertId}/acknowledge`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
    },
  })
}

// Hooks for services
export const useServices = () => {
  return useQuery({
    queryKey: ['services'],
    queryFn: async () => {
      const response = await apiClient.get('/services')
      return response.data.services as Service[]
    },
    refetchInterval: 60000, // Refetch every 60 seconds
    staleTime: 30000,
  })
}

export const useServiceDependencies = () => {
  return useQuery({
    queryKey: ['service-dependencies'],
    queryFn: async () => {
      const response = await apiClient.get('/services/dependencies')
      return response.data
    },
    refetchInterval: 120000, // Refetch every 2 minutes
    staleTime: 60000,
  })
}

// Hooks for incidents
export const useIncidents = (limit: number = 20) => {
  return useQuery({
    queryKey: ['incidents', limit],
    queryFn: async () => {
      const response = await apiClient.get('/incidents', {
        params: { limit },
      })
      return response.data.incidents as Incident[]
    },
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 10000,
  })
}

export const useIncident = (incidentId: string) => {
  return useQuery({
    queryKey: ['incident', incidentId],
    queryFn: async () => {
      const response = await apiClient.get(`/incidents/${incidentId}`)
      return response.data.incident as Incident
    },
  })
}

export const useResolveIncident = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (incidentId: string) => {
      await apiClient.post(`/incidents/${incidentId}/resolve`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
    },
  })
}

// Hooks for traces
export const useTraces = (service: string, limit: number = 100) => {
  return useQuery({
    queryKey: ['traces', service, limit],
    queryFn: async () => {
      const response = await apiClient.get('/traces', {
        params: { service, limit },
      })
      return response.data.traces
    },
    refetchInterval: 45000, // Refetch every 45 seconds
    staleTime: 15000,
  })
}

// Hooks for logs
export const useLogs = (query: string, limit: number = 100) => {
  return useQuery({
    queryKey: ['logs', query, limit],
    queryFn: async () => {
      const response = await apiClient.get('/logs', {
        params: { query, limit },
      })
      return response.data.logs
    },
    refetchInterval: 30000,
    staleTime: 10000,
  })
}

// Hooks for cost data
export const useCostData = (timeRange: 'day' | 'week' | 'month' = 'month') => {
  return useQuery({
    queryKey: ['cost-data', timeRange],
    queryFn: async () => {
      const response = await apiClient.get('/costs', {
        params: { timeRange },
      })
      return response.data
    },
    refetchInterval: 300000, // Refetch every 5 minutes
    staleTime: 120000, // 2 minutes
  })
}

export default apiClient
