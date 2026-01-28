"use client";

import { useEffect, useRef, useState, useCallback } from "react";

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export type WebSocketStatus = "connecting" | "connected" | "disconnected" | "error" | "reconnecting";

interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
}

type MessageHandler<T> = (message: WebSocketMessage<T>) => void;

interface UseWebSocketOptions<T> {
  /** WebSocket endpoint path (e.g., "/ws/projects") */
  endpoint: string;
  /** Callback when a message is received */
  onMessage?: MessageHandler<T>;
  /** Callback when connection status changes */
  onStatusChange?: (status: WebSocketStatus) => void;
  /** Whether to automatically reconnect on disconnect */
  autoReconnect?: boolean;
  /** Initial reconnect interval in milliseconds (doubles with each attempt) */
  reconnectInterval?: number;
  /** Maximum reconnect attempts */
  maxReconnectAttempts?: number;
  /** Maximum reconnect interval in milliseconds (cap for exponential backoff) */
  maxReconnectInterval?: number;
  /** Event types to filter for (undefined = all events) */
  eventTypes?: string[];
}

interface UseWebSocketReturn<T> {
  /** Current connection status */
  status: WebSocketStatus;
  /** Manually connect to the WebSocket */
  connect: () => void;
  /** Manually disconnect from the WebSocket */
  disconnect: () => void;
  /** Send a message through the WebSocket */
  send: (message: WebSocketMessage) => void;
  /** Subscribe to specific event types */
  subscribe: (eventTypes: string[], handler: MessageHandler<T>) => () => void;
  /** Current reconnect attempt number */
  reconnectAttempt: number;
  /** Whether the connection is healthy (connected) */
  isConnected: boolean;
}

/**
 * Creates and manages a WebSocket connection with enhanced features:
 * - Exponential backoff for reconnection
 * - Event subscription system
 * - Connection health monitoring
 *
 * @example
 * ```tsx
 * const { status, isConnected, subscribe } = useWebSocket<EventPayload>({
 *   endpoint: "/ws/projects/123/timeline",
 *   onMessage: handleMessage,
 * });
 *
 * // Subscribe to specific event types
 * useEffect(() => {
 *   const unsubscribe = subscribe(["task_started", "task_completed"], (msg) => {
 *     console.log("Task event:", msg);
 *   });
 *   return unsubscribe;
 * }, [subscribe]);
 * ```
 */
export function useWebSocket<T = unknown>({
  endpoint,
  onMessage,
  onStatusChange,
  autoReconnect = true,
  reconnectInterval = 1000,
  maxReconnectAttempts = 10,
  maxReconnectInterval = 30000,
  eventTypes,
}: UseWebSocketOptions<T>): UseWebSocketReturn<T> {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);
  const [status, setStatus] = useState<WebSocketStatus>("disconnected");
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  // Subscription system
  const subscriptionsRef = useRef<Map<string, Set<MessageHandler<T>>>>(new Map());

  // Store latest callbacks in refs to avoid stale closures
  const onMessageRef = useRef(onMessage);
  const onStatusChangeRef = useRef(onStatusChange);
  const eventTypesRef = useRef(eventTypes);

  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
  }, [onStatusChange]);

  useEffect(() => {
    eventTypesRef.current = eventTypes;
  }, [eventTypes]);

  // Calculate backoff interval with exponential increase
  const getBackoffInterval = useCallback((attempt: number): number => {
    const interval = reconnectInterval * Math.pow(2, attempt);
    return Math.min(interval, maxReconnectInterval);
  }, [reconnectInterval, maxReconnectInterval]);

  // Initialize WebSocket connection
  useEffect(() => {
    isMountedRef.current = true;

    function updateStatus(newStatus: WebSocketStatus) {
      if (isMountedRef.current) {
        setStatus(newStatus);
        onStatusChangeRef.current?.(newStatus);
      }
    }

    function handleMessage(message: WebSocketMessage<T>) {
      // Filter by event types if specified
      if (eventTypesRef.current && eventTypesRef.current.length > 0) {
        if (!eventTypesRef.current.includes(message.type)) {
          return;
        }
      }

      // Call the main onMessage handler
      onMessageRef.current?.(message);

      // Notify subscribers for this event type
      const handlers = subscriptionsRef.current.get(message.type);
      if (handlers) {
        handlers.forEach((handler) => handler(message));
      }

      // Also notify wildcard subscribers ("*")
      const wildcardHandlers = subscriptionsRef.current.get("*");
      if (wildcardHandlers) {
        wildcardHandlers.forEach((handler) => handler(message));
      }
    }

    function createConnection() {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        return;
      }

      updateStatus(reconnectAttemptsRef.current > 0 ? "reconnecting" : "connecting");

      try {
        const ws = new WebSocket(`${WS_BASE_URL}${endpoint}`);
        wsRef.current = ws;

        ws.onopen = () => {
          reconnectAttemptsRef.current = 0;
          setReconnectAttempt(0);
          updateStatus("connected");
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as WebSocketMessage<T>;
            handleMessage(message);
          } catch {
            console.error("Failed to parse WebSocket message:", event.data);
          }
        };

        ws.onerror = () => {
          updateStatus("error");
        };

        ws.onclose = () => {
          wsRef.current = null;

          // Schedule reconnect if enabled and within retry limits
          if (
            isMountedRef.current &&
            autoReconnect &&
            reconnectAttemptsRef.current < maxReconnectAttempts
          ) {
            const backoffInterval = getBackoffInterval(reconnectAttemptsRef.current);
            reconnectAttemptsRef.current += 1;
            setReconnectAttempt(reconnectAttemptsRef.current);
            updateStatus("reconnecting");

            reconnectTimeoutRef.current = setTimeout(() => {
              if (isMountedRef.current) {
                createConnection();
              }
            }, backoffInterval);
          } else {
            updateStatus("disconnected");
          }
        };
      } catch {
        updateStatus("error");
      }
    }

    // Start connection
    createConnection();

    // Cleanup on unmount
    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [endpoint, autoReconnect, maxReconnectAttempts, getBackoffInterval]);

  // Manual connect function
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }
    reconnectAttemptsRef.current = 0;
    setReconnectAttempt(0);
    // Trigger reconnection by closing existing connection
    wsRef.current?.close();
  }, []);

  // Manual disconnect function
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    reconnectAttemptsRef.current = maxReconnectAttempts; // Prevent auto-reconnect
    wsRef.current?.close();
    wsRef.current = null;
  }, [maxReconnectAttempts]);

  // Send message function
  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  // Subscribe to specific event types
  const subscribe = useCallback((types: string[], handler: MessageHandler<T>): (() => void) => {
    // Register handler for each event type
    types.forEach((type) => {
      if (!subscriptionsRef.current.has(type)) {
        subscriptionsRef.current.set(type, new Set());
      }
      subscriptionsRef.current.get(type)!.add(handler);
    });

    // Return unsubscribe function
    return () => {
      types.forEach((type) => {
        const handlers = subscriptionsRef.current.get(type);
        if (handlers) {
          handlers.delete(handler);
          if (handlers.size === 0) {
            subscriptionsRef.current.delete(type);
          }
        }
      });
    };
  }, []);

  return {
    status,
    connect,
    disconnect,
    send,
    subscribe,
    reconnectAttempt,
    isConnected: status === "connected",
  };
}
