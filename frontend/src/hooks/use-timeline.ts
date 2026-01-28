"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  api,
  TimelineEvent,
  TimelineEventType,
  TimelineFilter,
} from "@/services/api";
import { useWebSocket, WebSocketStatus } from "./use-websocket";

interface TimelineUpdatePayload {
  event: TimelineEvent;
  action: "created" | "updated";
}

export type ZoomLevel = "hourly" | "daily" | "all";

interface UseTimelineOptions {
  projectId: string;
  /** Initial event type filter */
  initialTypes?: TimelineEventType[];
  /** Initial zoom level */
  initialZoom?: ZoomLevel;
}

interface UseTimelineReturn {
  /** All timeline events */
  events: TimelineEvent[];
  /** Filtered events based on current filter */
  filteredEvents: TimelineEvent[];
  /** Events grouped by time period based on zoom level */
  groupedEvents: Map<string, TimelineEvent[]>;
  /** Loading state */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
  /** WebSocket connection status */
  wsStatus: WebSocketStatus;
  /** Current filter settings */
  filter: TimelineFilter;
  /** Current zoom level */
  zoomLevel: ZoomLevel;
  /** Whether there are more events to load */
  hasMore: boolean;
  /** Update filter */
  setFilter: (filter: TimelineFilter) => void;
  /** Set zoom level */
  setZoomLevel: (level: ZoomLevel) => void;
  /** Toggle a specific event type in the filter */
  toggleEventType: (type: TimelineEventType) => void;
  /** Load more events */
  loadMore: () => Promise<void>;
  /** Refetch events */
  refetch: () => Promise<void>;
  /** Get download URL for JSON export */
  getDownloadJsonUrl: () => string;
  /** Get download URL for CSV export */
  getDownloadCsvUrl: () => string;
}

// All available event types for filtering
export const ALL_EVENT_TYPES: TimelineEventType[] = [
  "task_started",
  "task_completed",
  "task_failed",
  "agent_transition",
  "gate_started",
  "gate_passed",
  "gate_failed",
  "signal_received",
  "signal_sent",
  "error",
  "session_started",
  "session_paused",
  "session_resumed",
  "session_completed",
];

// Event type display configuration
export const EVENT_TYPE_CONFIG: Record<
  TimelineEventType,
  { label: string; color: string; icon: string }
> = {
  task_started: { label: "Task Started", color: "blue", icon: "play" },
  task_completed: { label: "Task Completed", color: "green", icon: "check" },
  task_failed: { label: "Task Failed", color: "red", icon: "x" },
  agent_transition: { label: "Agent Transition", color: "purple", icon: "arrow-right" },
  gate_started: { label: "Gate Started", color: "cyan", icon: "shield" },
  gate_passed: { label: "Gate Passed", color: "green", icon: "shield-check" },
  gate_failed: { label: "Gate Failed", color: "red", icon: "shield-x" },
  signal_received: { label: "Signal Received", color: "yellow", icon: "radio" },
  signal_sent: { label: "Signal Sent", color: "yellow", icon: "send" },
  error: { label: "Error", color: "red", icon: "alert-triangle" },
  session_started: { label: "Session Started", color: "blue", icon: "play-circle" },
  session_paused: { label: "Session Paused", color: "orange", icon: "pause-circle" },
  session_resumed: { label: "Session Resumed", color: "blue", icon: "play-circle" },
  session_completed: { label: "Session Completed", color: "green", icon: "check-circle" },
};

function getTimeKey(timestamp: string, zoomLevel: ZoomLevel): string {
  const date = new Date(timestamp);

  switch (zoomLevel) {
    case "hourly":
      return date.toISOString().slice(0, 13) + ":00"; // YYYY-MM-DDTHH:00
    case "daily":
      return date.toISOString().slice(0, 10); // YYYY-MM-DD
    case "all":
    default:
      return "all";
  }
}

function getZoomTimeRange(zoomLevel: ZoomLevel): { startTime?: string; endTime?: string } {
  const now = new Date();

  switch (zoomLevel) {
    case "hourly":
      // Last 24 hours
      const dayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      return { startTime: dayAgo.toISOString() };
    case "daily":
      // Last 7 days
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      return { startTime: weekAgo.toISOString() };
    case "all":
    default:
      return {};
  }
}

export function useTimeline({
  projectId,
  initialTypes,
  initialZoom = "all",
}: UseTimelineOptions): UseTimelineReturn {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TimelineFilter>({
    types: initialTypes,
  });
  const [zoomLevel, setZoomLevel] = useState<ZoomLevel>(initialZoom);
  const [hasMore, setHasMore] = useState(false);
  const [cursor, setCursor] = useState<string | undefined>(undefined);

  // Compute the effective filter including zoom-based time range
  const effectiveFilter = useMemo((): TimelineFilter => {
    const zoomRange = getZoomTimeRange(zoomLevel);
    return {
      ...filter,
      startTime: filter.startTime ?? zoomRange.startTime,
      endTime: filter.endTime ?? zoomRange.endTime,
    };
  }, [filter, zoomLevel]);

  // Fetch timeline events
  const fetchEvents = useCallback(
    async (loadMore = false) => {
      try {
        if (!loadMore) {
          setIsLoading(true);
          setError(null);
        }

        const response = await api.timeline.list(
          projectId,
          effectiveFilter,
          loadMore ? cursor : undefined
        );

        if (loadMore) {
          setEvents((prev) => [...prev, ...response.events]);
        } else {
          setEvents(response.events);
        }

        setHasMore(response.hasMore);
        setCursor(response.nextCursor);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch timeline");
      } finally {
        setIsLoading(false);
      }
    },
    [projectId, effectiveFilter, cursor]
  );

  // Handle WebSocket messages for real-time updates
  const handleWebSocketMessage = useCallback(
    (message: { type: string; payload: TimelineUpdatePayload }) => {
      if (message.type !== "timeline_update") return;

      const { event, action } = message.payload;

      // Check if event matches current filter
      if (effectiveFilter.types && effectiveFilter.types.length > 0) {
        if (!effectiveFilter.types.includes(event.type)) {
          return;
        }
      }

      setEvents((current) => {
        switch (action) {
          case "created":
            // Insert new event at the beginning (most recent first)
            return [event, ...current];

          case "updated":
            return current.map((e) => (e.id === event.id ? event : e));

          default:
            return current;
        }
      });
    },
    [effectiveFilter.types]
  );

  const { status: wsStatus } = useWebSocket<TimelineUpdatePayload>({
    endpoint: `/ws/projects/${projectId}/timeline`,
    onMessage: handleWebSocketMessage,
  });

  // Initial fetch and refetch when filter/zoom changes
  useEffect(() => {
    setCursor(undefined);
    void fetchEvents(false);
  }, [projectId, effectiveFilter]);

  // Filter events locally based on type filter
  const filteredEvents = useMemo(() => {
    if (!filter.types || filter.types.length === 0) {
      return events;
    }
    return events.filter((event) => filter.types!.includes(event.type));
  }, [events, filter.types]);

  // Group events by time period based on zoom level
  const groupedEvents = useMemo(() => {
    const groups = new Map<string, TimelineEvent[]>();

    filteredEvents.forEach((event) => {
      const key = getTimeKey(event.timestamp, zoomLevel);
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key)!.push(event);
    });

    return groups;
  }, [filteredEvents, zoomLevel]);

  // Toggle event type in filter
  const toggleEventType = useCallback((type: TimelineEventType) => {
    setFilter((current) => {
      const currentTypes = current.types ?? [];
      const newTypes = currentTypes.includes(type)
        ? currentTypes.filter((t) => t !== type)
        : [...currentTypes, type];

      return {
        ...current,
        types: newTypes.length > 0 ? newTypes : undefined,
      };
    });
  }, []);

  // Load more events
  const loadMore = useCallback(async () => {
    if (hasMore && cursor) {
      await fetchEvents(true);
    }
  }, [hasMore, cursor, fetchEvents]);

  // Get download URLs
  const getDownloadJsonUrl = useCallback(() => {
    return api.timeline.downloadJson(projectId, effectiveFilter);
  }, [projectId, effectiveFilter]);

  const getDownloadCsvUrl = useCallback(() => {
    return api.timeline.downloadCsv(projectId, effectiveFilter);
  }, [projectId, effectiveFilter]);

  return {
    events,
    filteredEvents,
    groupedEvents,
    isLoading,
    error,
    wsStatus,
    filter,
    zoomLevel,
    hasMore,
    setFilter,
    setZoomLevel,
    toggleEventType,
    loadMore,
    refetch: () => fetchEvents(false),
    getDownloadJsonUrl,
    getDownloadCsvUrl,
  };
}
