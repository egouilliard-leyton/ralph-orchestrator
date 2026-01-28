"use client";

import * as React from "react";
import {
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
} from "react";
import { LogEntry, LogLevel, LogSource, LogFilter } from "@/services/api";
import { WebSocketStatus } from "@/hooks/use-websocket";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

// Icons
function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  );
}

function ScrollIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 5v14" />
      <path d="m19 12-7 7-7-7" />
    </svg>
  );
}

function FilterIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  );
}

function ClearIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

function WifiIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 13a10 10 0 0 1 14 0" />
      <path d="M8.5 16.5a5 5 0 0 1 7 0" />
      <path d="M2 8.82a15 15 0 0 1 20 0" />
      <line x1="12" x2="12.01" y1="20" y2="20" />
    </svg>
  );
}

function WifiOffIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
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

function RefreshCwIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M16 16h5v5" />
    </svg>
  );
}

function ConnectionIndicator({ status }: { status: WebSocketStatus }) {
  const statusConfig: Record<WebSocketStatus, { icon: React.FC<{ className?: string }>; label: string; className: string }> = {
    connected: { icon: WifiIcon, label: "Live", className: "text-green-600" },
    connecting: { icon: RefreshCwIcon, label: "Connecting", className: "text-yellow-600 animate-spin" },
    reconnecting: { icon: RefreshCwIcon, label: "Reconnecting", className: "text-yellow-600 animate-spin" },
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

// ANSI color code mappings
const ANSI_COLORS: Record<number, string> = {
  30: "text-gray-900 dark:text-gray-100",
  31: "text-red-600 dark:text-red-400",
  32: "text-green-600 dark:text-green-400",
  33: "text-yellow-600 dark:text-yellow-400",
  34: "text-blue-600 dark:text-blue-400",
  35: "text-purple-600 dark:text-purple-400",
  36: "text-cyan-600 dark:text-cyan-400",
  37: "text-gray-200 dark:text-gray-300",
  90: "text-gray-500",
  91: "text-red-400",
  92: "text-green-400",
  93: "text-yellow-400",
  94: "text-blue-400",
  95: "text-purple-400",
  96: "text-cyan-400",
  97: "text-white",
};

const ANSI_BG_COLORS: Record<number, string> = {
  40: "bg-gray-900",
  41: "bg-red-600",
  42: "bg-green-600",
  43: "bg-yellow-600",
  44: "bg-blue-600",
  45: "bg-purple-600",
  46: "bg-cyan-600",
  47: "bg-gray-200",
};

interface AnsiSegment {
  text: string;
  classes: string;
  isBold?: boolean;
  isUnderline?: boolean;
}

function parseAnsiCodes(text: string): AnsiSegment[] {
  const segments: AnsiSegment[] = [];
  const ansiRegex = /\x1b\[([0-9;]*)m/g;

  let currentClasses: string[] = [];
  let isBold = false;
  let isUnderline = false;
  let lastIndex = 0;
  let match;

  while ((match = ansiRegex.exec(text)) !== null) {
    // Add text before this ANSI code
    if (match.index > lastIndex) {
      segments.push({
        text: text.substring(lastIndex, match.index),
        classes: currentClasses.join(" "),
        isBold,
        isUnderline,
      });
    }

    // Parse ANSI codes
    const codes = match[1]?.split(";").map(Number) ?? [0];
    for (const code of codes) {
      if (code === 0) {
        // Reset
        currentClasses = [];
        isBold = false;
        isUnderline = false;
      } else if (code === 1) {
        isBold = true;
      } else if (code === 4) {
        isUnderline = true;
      } else if (ANSI_COLORS[code]) {
        currentClasses = currentClasses.filter((c) => !c.startsWith("text-"));
        currentClasses.push(ANSI_COLORS[code]);
      } else if (ANSI_BG_COLORS[code]) {
        currentClasses = currentClasses.filter((c) => !c.startsWith("bg-"));
        currentClasses.push(ANSI_BG_COLORS[code]);
      }
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    segments.push({
      text: text.substring(lastIndex),
      classes: currentClasses.join(" "),
      isBold,
      isUnderline,
    });
  }

  return segments;
}

function AnsiText({
  text,
  searchTerm,
}: {
  text: string;
  searchTerm?: string;
}) {
  const segments = useMemo(() => parseAnsiCodes(text), [text]);

  return (
    <>
      {segments.map((segment, index) => {
        let content: React.ReactNode = segment.text;

        // Highlight search term
        if (searchTerm && segment.text.toLowerCase().includes(searchTerm.toLowerCase())) {
          const parts = segment.text.split(new RegExp(`(${escapeRegExp(searchTerm)})`, "gi"));
          content = parts.map((part, i) =>
            part.toLowerCase() === searchTerm.toLowerCase() ? (
              <mark key={i} className="bg-yellow-300 dark:bg-yellow-600 text-inherit">
                {part}
              </mark>
            ) : (
              part
            )
          );
        }

        return (
          <span
            key={index}
            className={cn(
              segment.classes,
              segment.isBold && "font-bold",
              segment.isUnderline && "underline"
            )}
          >
            {content}
          </span>
        );
      })}
    </>
  );
}

function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

interface LogViewerProps {
  projectId: string;
  logs: LogEntry[];
  isLoading: boolean;
  error: string | null;
  hasMore: boolean;
  filter: LogFilter;
  wsStatus?: WebSocketStatus;
  onFilterChange: (filter: LogFilter) => void;
  onLoadMore: () => void;
  onDownload: () => void;
  className?: string;
}

const LOG_LEVELS: LogLevel[] = ["debug", "info", "warn", "error"];
const LOG_SOURCES: LogSource[] = ["implementation", "test", "review", "fix", "gate", "system"];

function getLevelBadgeVariant(level: LogLevel): "default" | "secondary" | "warning" | "error" {
  switch (level) {
    case "debug":
      return "secondary";
    case "info":
      return "default";
    case "warn":
      return "warning";
    case "error":
      return "error";
  }
}

function getSourceColor(source: LogSource): string {
  switch (source) {
    case "implementation":
      return "text-blue-600 dark:text-blue-400";
    case "test":
      return "text-green-600 dark:text-green-400";
    case "review":
      return "text-purple-600 dark:text-purple-400";
    case "fix":
      return "text-orange-600 dark:text-orange-400";
    case "gate":
      return "text-cyan-600 dark:text-cyan-400";
    case "system":
      return "text-gray-600 dark:text-gray-400";
    default:
      return "text-muted-foreground";
  }
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  });
}

export function LogViewer({
  projectId,
  logs,
  isLoading,
  error,
  hasMore,
  filter,
  wsStatus,
  onFilterChange,
  onLoadMore,
  onDownload,
  className,
}: LogViewerProps) {
  const [autoScroll, setAutoScroll] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [searchInput, setSearchInput] = useState(filter.search ?? "");
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs.length, autoScroll]);

  // Detect manual scroll to disable auto-scroll
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

    if (!isAtBottom && autoScroll) {
      setAutoScroll(false);
    }
  }, [autoScroll]);

  const toggleAutoScroll = useCallback(() => {
    setAutoScroll((prev) => !prev);
    if (!autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [autoScroll]);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      onFilterChange({ ...filter, search: searchInput || undefined });
    },
    [filter, searchInput, onFilterChange]
  );

  const clearSearch = useCallback(() => {
    setSearchInput("");
    onFilterChange({ ...filter, search: undefined });
  }, [filter, onFilterChange]);

  const toggleLevel = useCallback(
    (level: LogLevel) => {
      const currentLevels = filter.levels ?? [];
      const newLevels = currentLevels.includes(level)
        ? currentLevels.filter((l) => l !== level)
        : [...currentLevels, level];
      onFilterChange({ ...filter, levels: newLevels.length > 0 ? newLevels : undefined });
    },
    [filter, onFilterChange]
  );

  const toggleSource = useCallback(
    (source: LogSource) => {
      const currentSources = filter.sources ?? [];
      const newSources = currentSources.includes(source)
        ? currentSources.filter((s) => s !== source)
        : [...currentSources, source];
      onFilterChange({ ...filter, sources: newSources.length > 0 ? newSources : undefined });
    },
    [filter, onFilterChange]
  );

  const clearFilters = useCallback(() => {
    setSearchInput("");
    onFilterChange({});
  }, [onFilterChange]);

  const hasActiveFilters = Boolean(
    filter.search ||
      (filter.levels && filter.levels.length > 0) ||
      (filter.sources && filter.sources.length > 0)
  );

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Logs</CardTitle>
          <div className="flex items-center gap-1">
            {wsStatus && (
              <>
                <ConnectionIndicator status={wsStatus} />
                <div className="w-px h-4 bg-border mx-1" />
              </>
            )}
            <Button
              variant={showFilters ? "secondary" : "ghost"}
              size="icon-xs"
              onClick={() => setShowFilters(!showFilters)}
              title="Toggle filters"
            >
              <FilterIcon className="size-4" />
            </Button>
            <Button
              variant={autoScroll ? "secondary" : "ghost"}
              size="icon-xs"
              onClick={toggleAutoScroll}
              title={autoScroll ? "Auto-scroll enabled" : "Auto-scroll disabled"}
            >
              <ScrollIcon className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onDownload}
              title="Download logs"
            >
              <DownloadIcon className="size-4" />
            </Button>
          </div>
        </div>

        {/* Search bar */}
        <form onSubmit={handleSearch} className="flex gap-2 mt-2">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-2 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search logs..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-8 pr-8 h-8"
            />
            {searchInput && (
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                className="absolute right-1 top-1/2 -translate-y-1/2"
                onClick={clearSearch}
              >
                <ClearIcon className="size-3" />
              </Button>
            )}
          </div>
          <Button type="submit" size="sm" variant="outline">
            Search
          </Button>
        </form>

        {/* Filter panel */}
        {showFilters && (
          <div className="mt-3 space-y-3 rounded-md bg-muted/50 p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Filters</span>
              {hasActiveFilters && (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={clearFilters}
                  className="text-xs"
                >
                  Clear all
                </Button>
              )}
            </div>

            {/* Level filters */}
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground">Log Level</span>
              <div className="flex flex-wrap gap-1">
                {LOG_LEVELS.map((level) => (
                  <Badge
                    key={level}
                    variant={filter.levels?.includes(level) ? getLevelBadgeVariant(level) : "outline"}
                    className="cursor-pointer"
                    onClick={() => toggleLevel(level)}
                  >
                    {level}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Source filters */}
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground">Source</span>
              <div className="flex flex-wrap gap-1">
                {LOG_SOURCES.map((source) => (
                  <Badge
                    key={source}
                    variant={filter.sources?.includes(source) ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => toggleSource(source)}
                  >
                    {source}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="flex-1 min-h-0 p-0">
        {error && (
          <div className="mx-6 mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-96 overflow-y-auto font-mono text-xs"
        >
          {logs.length === 0 && !isLoading && (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              No logs found
            </div>
          )}

          <div className="divide-y divide-border">
            {logs.map((log) => (
              <LogLine key={log.id} log={log} searchTerm={filter.search} />
            ))}
          </div>

          {hasMore && (
            <div className="flex justify-center py-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={onLoadMore}
                disabled={isLoading}
              >
                {isLoading ? "Loading..." : "Load more"}
              </Button>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </CardContent>
    </Card>
  );
}

interface LogLineProps {
  log: LogEntry;
  searchTerm?: string;
}

function LogLine({ log, searchTerm }: LogLineProps) {
  return (
    <div
      className={cn(
        "px-4 py-1.5 hover:bg-muted/50 flex items-start gap-2",
        log.level === "error" && "bg-red-500/5",
        log.level === "warn" && "bg-yellow-500/5"
      )}
    >
      <span className="text-muted-foreground shrink-0 w-24">
        {formatTimestamp(log.timestamp)}
      </span>
      <Badge
        variant={getLevelBadgeVariant(log.level)}
        className="shrink-0 w-12 justify-center text-[10px] py-0"
      >
        {log.level.toUpperCase()}
      </Badge>
      <span className={cn("shrink-0 w-24", getSourceColor(log.source))}>
        [{log.source}]
      </span>
      <span className="flex-1 whitespace-pre-wrap break-all">
        <AnsiText text={log.message} searchTerm={searchTerm} />
      </span>
    </div>
  );
}
