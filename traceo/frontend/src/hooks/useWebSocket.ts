import { useEffect, useRef, useCallback, useState } from 'react'

type WebSocketMessage = {
  type: 'metrics' | 'alerts' | 'incidents' | 'traces' | 'logs'
  data: unknown
  timestamp: number
}

type WebSocketEventHandler = (data: unknown) => void

const WEBSOCKET_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
const RECONNECT_INTERVAL = 3000 // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 10

export const useWebSocket = () => {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const messageBufferRef = useRef<WebSocketMessage[]>([])
  const flushIntervalRef = useRef<number | null>(null)

  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handlersRef = useRef<Map<string, Set<WebSocketEventHandler>>>(
    new Map()
  )

  const flushMessageBuffer = useCallback(() => {
    if (messageBufferRef.current.length === 0) return

    // Process buffered messages in batches
    const messages = messageBufferRef.current.splice(0, 100)
    messages.forEach((msg) => {
      const handlers = handlersRef.current.get(msg.type)
      if (handlers) {
        handlers.forEach((handler) => handler(msg.data))
      }
    })
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      wsRef.current = new WebSocket(WEBSOCKET_URL)

      wsRef.current.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0

        // Start buffer flushing
        flushIntervalRef.current = window.setInterval(flushMessageBuffer, 100)
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage
          messageBufferRef.current.push(message)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      wsRef.current.onerror = () => {
        setError('WebSocket connection error')
        setIsConnected(false)
      }

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)

        // Clear flush interval
        if (flushIntervalRef.current) {
          clearInterval(flushIntervalRef.current)
        }

        // Attempt to reconnect
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++
          reconnectTimeoutRef.current = window.setTimeout(
            connect,
            RECONNECT_INTERVAL
          )
        } else {
          setError('Failed to connect after multiple attempts')
        }
      }
    } catch (err) {
      setError(`WebSocket connection failed: ${err}`)
    }
  }, [flushMessageBuffer])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (flushIntervalRef.current) {
      clearInterval(flushIntervalRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const send = useCallback((type: string, data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }))
    }
  }, [])

  const subscribe = useCallback(
    (messageType: string, handler: WebSocketEventHandler) => {
      if (!handlersRef.current.has(messageType)) {
        handlersRef.current.set(messageType, new Set())
      }
      handlersRef.current.get(messageType)!.add(handler)

      return () => {
        const handlers = handlersRef.current.get(messageType)
        if (handlers) {
          handlers.delete(handler)
        }
      }
    },
    []
  )

  useEffect(() => {
    connect()
    return disconnect
  }, [connect, disconnect])

  return {
    isConnected,
    error,
    send,
    subscribe,
  }
}

// Hook for specific message types
export const useWebSocketData = (messageType: string) => {
  const [data, setData] = useState<unknown>(null)
  const [lastUpdate, setLastUpdate] = useState<number>(0)
  const { subscribe, isConnected } = useWebSocket()

  useEffect(() => {
    const unsubscribe = subscribe(messageType, (newData) => {
      setData(newData)
      setLastUpdate(Date.now())
    })

    return unsubscribe
  }, [messageType, subscribe])

  return {
    data,
    lastUpdate,
    isConnected,
  }
}
