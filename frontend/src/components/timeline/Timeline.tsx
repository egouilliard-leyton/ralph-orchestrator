"use client";

import * as React from "react";
import { useState, useCallback, useMemo } from "react";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useTimeline,
  ZoomLevel,
  ALL_EVENT_TYPES,
  EVENT_TYPE_CONFIG,
} from "@/hooks/use-timeline";
import { TimelineEvent, TimelineEventType } from "@/services/api";
import { WebSocketStatus } from "@/hooks/use-websocket";

// Icons
function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

function ArrowRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function ShieldXIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m14.5 9.5-5 5" />
      <path d="m9.5 9.5 5 5" />
    </svg>
  );
}

function RadioIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="2" />
      <path d="M4.93 19.07a10 10 0 0 1 0-14.14" />
      <path d="M7.76 16.24a6 6 0 0 1 0-8.48" />
      <path d="M16.24 7.76a6 6 0 0 1 0 8.48" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}

function SendIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 2-7 20-4-9-9-4Z" />
      <path d="M22 2 11 13" />
    </svg>
  );
}

function AlertTriangleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}

function PlayCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polygon points="10 8 16 12 10 16 10 8" />
    </svg>
  );
}

function PauseCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="10" x2="10" y1="15" y2="9" />
      <line x1="14" x2="14" y1="15" y2="9" />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function FilterIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  );
}

function ZoomInIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" x2="16.65" y1="21" y2="16.65" />
      <line x1="11" x2="11" y1="8" y2="14" />
      <line x1="8" x2="14" y1="11" y2="11" />
    </svg>
  );
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

function WifiIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 13a10 10 0 0 1 14 0" />
      <path d="M8.5 16.5a5 5 0 0 1 7 0" />
      <path d="M2 8.82a15 15 0 0 1 20 0" />
      <line x1="12" x2="12.01" y1="20" y2="20" />
    </svg>
  );
}

function WifiOffIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="2" x2="22" y1="2" y2="22" />
      <path d="M8.5 16.5a5 5 0 0 1 7 0" />
      <path d="M2 8.82a15 15 0 0 1 4.17-2.65" />
      <path d="M10.66 5c4.01-.36 8.14.9 11.34 3.76" />
      <path d="M16.85 11.25a10 10 0 0 1 2.22 1.68" />
      <path d="M5 13a10 10 0 0 1 5.24-2.76" />
      <line x1="12" x2="12.01" y1="20" y2="20" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M16 16h5v5" />
    </svg>
  );
}

// Icon mapping for event types
const EVENT_ICONS: Record<string, React.FC<{ className?: string }>> = {
  play: PlayIcon,
  check: CheckIcon,
  x: XIcon,
  "arrow-right": ArrowRightIcon,
  shield: ShieldIcon,
  "shield-check": ShieldCheckIcon,
  "shield-x": ShieldXIcon,
  radio: RadioIcon,
  send: SendIcon,
  "alert-triangle": AlertTriangleIcon,
  "play-circle": PlayCircleIcon,
  "pause-circle": PauseCircleIcon,
  "check-circle": CheckCircleIcon,
};

// Color mappings
const EVENT_COLORS: Record<string, { bg: string; border: string; text: string; marker: string }> = {
  blue: {
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    text: "text-blue-600 dark:text-blue-400",
    marker: "bg-blue-500",
  },
  green: {
    bg: "bg-green-500/10",
    border: "border-green-500/30",
    text: "text-green-600 dark:text-green-400",
    marker: "bg-green-500",
  },
  red: {
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    text: "text-red-600 dark:text-red-400",
    marker: "bg-red-500",
  },
  purple: {
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
    text: "text-purple-600 dark:text-purple-400",
    marker: "bg-purple-500",
  },
  cyan: {
    bg: "bg-cyan-500/10",
    border: "border-cyan-500/30",
    text: "text-cyan-600 dark:text-cyan-400",
    marker: "bg-cyan-500",
  },
  yellow: {
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/30",
    text: "text-yellow-600 dark:text-yellow-400",
    marker: "bg-yellow-500",
  },
  orange: {
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    text: "text-orange-600 dark:text-orange-400",
    marker: "bg-orange-500",
  },
};

// Connection status indicator
function ConnectionIndicator({ status }: { status: WebSocketStatus }) {
  const statusConfig = {
    connected: { icon: WifiIcon, label: "Live", className: "text-green-600" },
    connecting: { icon: RefreshIcon, label: "Connecting...", className: "text-yellow-600 animate-spin" },
    reconnecting: { icon: RefreshIcon, label: "Reconnecting...", className: "text-yellow-600 animate-spin" },
    disconnected: { icon: WifiOffIcon, label: "Offline", className: "text-muted-foreground" },
    error: { icon: WifiOffIcon, label: "Error", className: "text-red-600" },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={cn("flex items-center gap-1 text-xs", config.className)}>
      <Icon />
      <span>{config.label}</span>
    </div>
  );
}

// Format timestamp for display
function formatTimestamp(timestamp: string, includeDate = false): string {
  const date = new Date(timestamp);

  if (includeDate) {
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// Format relative time
function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const date = new Date(timestamp);
  const diff = now.getTime() - date.getTime();

  if (diff < 60000) {
    return "just now";
  } else if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000);
    return `${minutes}m ago`;
  } else if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000);
    return `${hours}h ago`;
  } else {
    const days = Math.floor(diff / 86400000);
    return `${days}d ago`;
  }
}

// Format duration
function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  } else if (ms < 60000) {
    return `${(ms / 1000).toFixed(1)}s`;
  } else {
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  }
}

// Format group key for display
function formatGroupKey(key: string, zoomLevel: ZoomLevel): string {
  if (key === "all") {
    return "All Events";
  }

  const date = new Date(key);

  switch (zoomLevel) {
    case "hourly":
      return date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    case "daily":
      return date.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
      });
    default:
      return key;
  }
}

interface TimelineEventCardProps {
  event: TimelineEvent;
  isExpanded: boolean;
  onToggle: () => void;
}

const DEFAULT_COLORS = {
  bg: "bg-gray-500/10",
  border: "border-gray-500/30",
  text: "text-gray-600 dark:text-gray-400",
  marker: "bg-gray-500",
};

function TimelineEventCard({ event, isExpanded, onToggle }: TimelineEventCardProps) {
  const config = EVENT_TYPE_CONFIG[event.type];
  const colors = EVENT_COLORS[config.color] ?? DEFAULT_COLORS;
  const Icon = EVENT_ICONS[config.icon];

  return (
    <div
      className={cn(
        "relative pl-8 pb-4 last:pb-0 cursor-pointer group",
        "before:absolute before:left-3 before:top-6 before:bottom-0 before:w-px",
        "before:bg-border last:before:hidden"
      )}
      onClick={onToggle}
    >
      {/* Timeline marker */}
      <div
        className={cn(
          "absolute left-1.5 top-1 w-4 h-4 rounded-full flex items-center justify-center",
          colors.marker
        )}
      >
        {Icon && <Icon className="size-2.5 text-white" />}
      </div>

      {/* Event content */}
      <div
        className={cn(
          "rounded-lg border p-3 transition-all",
          colors.bg,
          colors.border,
          "hover:shadow-sm"
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="outline" className={cn("text-[10px] py-0", colors.text)}>
                {config.label}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {formatRelativeTime(event.timestamp)}
              </span>
            </div>
            <h4 className="font-medium text-sm truncate">{event.title}</h4>
          </div>
          <Button
            variant="ghost"
            size="icon-xs"
            className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            {isExpanded ? (
              <ChevronDownIcon className="size-3" />
            ) : (
              <ChevronRightIcon className="size-3" />
            )}
          </Button>
        </div>

        {/* Description (always visible if present and short) */}
        {event.description && !isExpanded && (
          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
            {event.description}
          </p>
        )}

        {/* Expanded details */}
        {isExpanded && (
          <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
            {event.description && (
              <p className="text-xs text-muted-foreground">{event.description}</p>
            )}

            <div className="flex flex-wrap gap-2 text-xs">
              <span className="text-muted-foreground">
                {formatTimestamp(event.timestamp, true)}
              </span>
              {event.metadata?.duration && (
                <Badge variant="secondary" className="text-[10px] py-0">
                  {formatDuration(event.metadata.duration)}
                </Badge>
              )}
            </div>

            {/* Metadata display */}
            {event.metadata && Object.keys(event.metadata).length > 0 && (
              <div className="space-y-1.5 mt-2">
                {event.metadata.taskId && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-muted-foreground">Task:</span>
                    <code className="px-1 py-0.5 bg-muted rounded text-[10px]">
                      {event.metadata.taskTitle || event.metadata.taskId}
                    </code>
                  </div>
                )}
                {event.metadata.agent && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-muted-foreground">Agent:</span>
                    <Badge variant="outline" className="text-[10px] py-0">
                      {event.metadata.agent}
                    </Badge>
                    {event.metadata.previousAgent && (
                      <>
                        <ArrowRightIcon className="size-3 text-muted-foreground" />
                        <Badge variant="outline" className="text-[10px] py-0">
                          {event.metadata.previousAgent}
                        </Badge>
                      </>
                    )}
                  </div>
                )}
                {event.metadata.gateName && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-muted-foreground">Gate:</span>
                    <code className="px-1 py-0.5 bg-muted rounded text-[10px]">
                      {event.metadata.gateName}
                    </code>
                    {event.metadata.gateDuration && (
                      <span className="text-muted-foreground">
                        ({formatDuration(event.metadata.gateDuration)})
                      </span>
                    )}
                  </div>
                )}
                {event.metadata.gateCmd && (
                  <div className="text-xs">
                    <span className="text-muted-foreground">Command:</span>
                    <pre className="mt-1 p-2 bg-muted rounded text-[10px] overflow-x-auto">
                      {event.metadata.gateCmd}
                    </pre>
                  </div>
                )}
                {event.metadata.gateOutput && (
                  <div className="text-xs">
                    <span className="text-muted-foreground">Output:</span>
                    <pre className="mt-1 p-2 bg-muted rounded text-[10px] max-h-32 overflow-auto whitespace-pre-wrap">
                      {event.metadata.gateOutput}
                    </pre>
                  </div>
                )}
                {event.metadata.signalType && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-muted-foreground">Signal:</span>
                    <code className="px-1 py-0.5 bg-muted rounded text-[10px]">
                      {event.metadata.signalType}
                    </code>
                  </div>
                )}
                {event.metadata.errorMessage && (
                  <div className="text-xs">
                    <span className="text-red-600 dark:text-red-400">Error:</span>
                    <pre className="mt-1 p-2 bg-red-500/10 border border-red-500/20 rounded text-[10px] max-h-32 overflow-auto whitespace-pre-wrap text-red-700 dark:text-red-300">
                      {event.metadata.errorMessage}
                      {event.metadata.errorStack && `\n\n${event.metadata.errorStack}`}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface TimelineGroupProps {
  groupKey: string;
  events: TimelineEvent[];
  zoomLevel: ZoomLevel;
  expandedEvents: Set<string>;
  onToggleEvent: (eventId: string) => void;
}

function TimelineGroup({
  groupKey,
  events,
  zoomLevel,
  expandedEvents,
  onToggleEvent,
}: TimelineGroupProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (zoomLevel === "all") {
    // No grouping, render events directly
    return (
      <>
        {events.map((event) => (
          <TimelineEventCard
            key={event.id}
            event={event}
            isExpanded={expandedEvents.has(event.id)}
            onToggle={() => onToggleEvent(event.id)}
          />
        ))}
      </>
    );
  }

  return (
    <div className="mb-4">
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="flex items-center gap-2 mb-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        {isCollapsed ? (
          <ChevronRightIcon className="size-4" />
        ) : (
          <ChevronDownIcon className="size-4" />
        )}
        <span>{formatGroupKey(groupKey, zoomLevel)}</span>
        <Badge variant="secondary" className="text-[10px] py-0">
          {events.length}
        </Badge>
      </button>

      {!isCollapsed && (
        <div className="ml-2">
          {events.map((event) => (
            <TimelineEventCard
              key={event.id}
              event={event}
              isExpanded={expandedEvents.has(event.id)}
              onToggle={() => onToggleEvent(event.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Export dropdown component
function ExportDropdown({
  onExportJson,
  onExportCsv,
}: {
  onExportJson: () => void;
  onExportCsv: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={() => setIsOpen(!isOpen)}
        title="Export timeline"
      >
        <DownloadIcon className="size-4" />
      </Button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 top-full mt-1 z-20 bg-popover border rounded-md shadow-lg py-1 min-w-[120px]">
            <button
              className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted transition-colors"
              onClick={() => {
                onExportJson();
                setIsOpen(false);
              }}
            >
              Export JSON
            </button>
            <button
              className="w-full px-3 py-1.5 text-sm text-left hover:bg-muted transition-colors"
              onClick={() => {
                onExportCsv();
                setIsOpen(false);
              }}
            >
              Export CSV
            </button>
          </div>
        </>
      )}
    </div>
  );
}

interface TimelineProps {
  projectId: string;
  className?: string;
}

export function Timeline({ projectId, className }: TimelineProps) {
  const {
    filteredEvents,
    groupedEvents,
    isLoading,
    error,
    wsStatus,
    filter,
    zoomLevel,
    hasMore,
    setZoomLevel,
    toggleEventType,
    loadMore,
    refetch,
    getDownloadJsonUrl,
    getDownloadCsvUrl,
  } = useTimeline({ projectId });

  const [showFilters, setShowFilters] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());

  // Toggle event expansion
  const handleToggleEvent = useCallback((eventId: string) => {
    setExpandedEvents((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) {
        next.delete(eventId);
      } else {
        next.add(eventId);
      }
      return next;
    });
  }, []);

  // Handle export
  const handleExportJson = useCallback(() => {
    const url = getDownloadJsonUrl();
    window.open(url, "_blank");
  }, [getDownloadJsonUrl]);

  const handleExportCsv = useCallback(() => {
    const url = getDownloadCsvUrl();
    window.open(url, "_blank");
  }, [getDownloadCsvUrl]);

  // Group events into sorted array
  const sortedGroups = useMemo(() => {
    const entries = Array.from(groupedEvents.entries());
    // Sort by key descending (most recent first)
    return entries.sort((a, b) => b[0].localeCompare(a[0]));
  }, [groupedEvents]);

  // Check if any filters are active
  const hasActiveFilters = filter.types && filter.types.length > 0;

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Timeline</CardTitle>
          <div className="flex items-center gap-1">
            <ConnectionIndicator status={wsStatus} />
            <div className="w-px h-4 bg-border mx-1" />
            <Button
              variant={showFilters ? "secondary" : "ghost"}
              size="icon-xs"
              onClick={() => setShowFilters(!showFilters)}
              title="Toggle filters"
            >
              <FilterIcon className="size-4" />
            </Button>
            <ExportDropdown
              onExportJson={handleExportJson}
              onExportCsv={handleExportCsv}
            />
          </div>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-2 mt-2">
          <ZoomInIcon className="size-4 text-muted-foreground" />
          <div className="flex gap-1">
            {(["hourly", "daily", "all"] as ZoomLevel[]).map((level) => (
              <Button
                key={level}
                variant={zoomLevel === level ? "secondary" : "ghost"}
                size="xs"
                onClick={() => setZoomLevel(level)}
              >
                {level === "hourly" ? "24h" : level === "daily" ? "7d" : "All"}
              </Button>
            ))}
          </div>
        </div>

        {/* Filter panel */}
        {showFilters && (
          <div className="mt-3 space-y-3 rounded-md bg-muted/50 p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Event Types</span>
              {hasActiveFilters && (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => {
                    // Clear all type filters
                    ALL_EVENT_TYPES.forEach((type) => {
                      if (filter.types?.includes(type)) {
                        toggleEventType(type);
                      }
                    });
                  }}
                  className="text-xs"
                >
                  Clear all
                </Button>
              )}
            </div>
            <div className="flex flex-wrap gap-1">
              {ALL_EVENT_TYPES.map((type) => {
                const config = EVENT_TYPE_CONFIG[type];
                const isActive = filter.types?.includes(type);
                const colors = EVENT_COLORS[config.color] ?? DEFAULT_COLORS;
                return (
                  <Badge
                    key={type}
                    variant={isActive ? "default" : "outline"}
                    className={cn(
                      "cursor-pointer text-[10px]",
                      isActive && colors.bg,
                      isActive && colors.text
                    )}
                    onClick={() => toggleEventType(type)}
                  >
                    {config.label}
                  </Badge>
                );
              })}
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="flex-1 min-h-0 overflow-y-auto">
        {error && (
          <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
            <Button
              variant="ghost"
              size="xs"
              onClick={refetch}
              className="ml-2"
            >
              Retry
            </Button>
          </div>
        )}

        {isLoading && filteredEvents.length === 0 ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-3">
                <Skeleton className="w-4 h-4 rounded-full shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-16 w-full rounded-lg" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center text-muted-foreground">
            <p className="text-sm">No timeline events found</p>
            {hasActiveFilters && (
              <p className="text-xs mt-1">Try adjusting your filters</p>
            )}
          </div>
        ) : (
          <div>
            {sortedGroups.map(([key, events]) => (
              <TimelineGroup
                key={key}
                groupKey={key}
                events={events}
                zoomLevel={zoomLevel}
                expandedEvents={expandedEvents}
                onToggleEvent={handleToggleEvent}
              />
            ))}

            {hasMore && (
              <div className="flex justify-center py-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={loadMore}
                  disabled={isLoading}
                >
                  {isLoading ? "Loading..." : "Load more"}
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
