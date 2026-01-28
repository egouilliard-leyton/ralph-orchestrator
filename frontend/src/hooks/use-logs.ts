"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api, LogEntry, LogFilter, LogsResponse } from "@/services/api";
import { useWebSocket, WebSocketStatus } from "./use-websocket";

interface LogUpdatePayload {
  action: "new_log" | "logs_cleared";
  log?: LogEntry;
}

interface UseLogsOptions {
  projectId: string;
  initialFilter?: LogFilter;
  pageSize?: number;
}

interface UseLogsReturn {
  logs: LogEntry[];
  isLoading: boolean;
  error: string | null;
  hasMore: boolean;
  filter: LogFilter;
  wsStatus: WebSocketStatus;
  setFilter: (filter: LogFilter) => void;
  loadMore: () => Promise<void>;
  refetch: () => Promise<void>;
  clearLogs: () => void;
  downloadUrl: string;
}

export function useLogs({
  projectId,
  initialFilter = {},
  pageSize = 100,
}: UseLogsOptions): UseLogsReturn {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [filter, setFilter] = useState<LogFilter>(initialFilter);
  const nextCursorRef = useRef<string | undefined>(undefined);

  const fetchLogs = useCallback(
    async (append = false) => {
      try {
        if (!append) {
          setIsLoading(true);
          nextCursorRef.current = undefined;
        }
        setError(null);

        const response = await api.logs.list(
          projectId,
          filter,
          append ? nextCursorRef.current : undefined
        );

        setLogs((prev) => (append ? [...prev, ...response.logs] : response.logs));
        setHasMore(response.hasMore);
        nextCursorRef.current = response.nextCursor;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch logs");
      } finally {
        setIsLoading(false);
      }
    },
    [projectId, filter]
  );

  // Handle WebSocket messages for real-time log streaming
  const handleWebSocketMessage = useCallback(
    (message: { type: string; payload: LogUpdatePayload }) => {
      if (message.type !== "log_update") return;

      const { action, log } = message.payload;

      if (action === "new_log" && log) {
        // Check if the log matches current filters
        if (shouldIncludeLog(log, filter)) {
          setLogs((prev) => [...prev, log]);
        }
      } else if (action === "logs_cleared") {
        setLogs([]);
      }
    },
    [filter]
  );

  const { status: wsStatus } = useWebSocket<LogUpdatePayload>({
    endpoint: `/ws/projects/${projectId}/logs`,
    onMessage: handleWebSocketMessage,
  });

  // Refetch when filter changes
  useEffect(() => {
    void fetchLogs(false);
  }, [fetchLogs]);

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoading) return;
    await fetchLogs(true);
  }, [hasMore, isLoading, fetchLogs]);

  const clearLogs = useCallback(() => {
    setLogs([]);
    nextCursorRef.current = undefined;
    setHasMore(false);
  }, []);

  const updateFilter = useCallback((newFilter: LogFilter) => {
    setFilter(newFilter);
    // Clear existing logs when filter changes
    setLogs([]);
    nextCursorRef.current = undefined;
  }, []);

  // Generate download URL with current filters
  const downloadUrl = api.logs.download(projectId, filter);

  return {
    logs,
    isLoading,
    error,
    hasMore,
    filter,
    wsStatus,
    setFilter: updateFilter,
    loadMore,
    refetch: () => fetchLogs(false),
    clearLogs,
    downloadUrl,
  };
}

/**
 * Check if a log entry matches the current filter criteria
 */
function shouldIncludeLog(log: LogEntry, filter: LogFilter): boolean {
  // Check level filter
  if (filter.levels && filter.levels.length > 0) {
    if (!filter.levels.includes(log.level)) {
      return false;
    }
  }

  // Check source filter
  if (filter.sources && filter.sources.length > 0) {
    if (!filter.sources.includes(log.source)) {
      return false;
    }
  }

  // Check search filter
  if (filter.search) {
    if (!log.message.toLowerCase().includes(filter.search.toLowerCase())) {
      return false;
    }
  }

  // Check time range
  if (filter.startTime) {
    const logTime = new Date(log.timestamp).getTime();
    const startTime = new Date(filter.startTime).getTime();
    if (logTime < startTime) {
      return false;
    }
  }

  if (filter.endTime) {
    const logTime = new Date(log.timestamp).getTime();
    const endTime = new Date(filter.endTime).getTime();
    if (logTime > endTime) {
      return false;
    }
  }

  return true;
}
