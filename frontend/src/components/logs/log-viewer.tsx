"use client";

import * as React from "react";
import { useEffect } from "react";
import { LogEntry, LogFilter } from "@/services/api";
import { WebSocketStatus } from "@/hooks/use-websocket";
import { useLogViewer } from "@/hooks/use-log-viewer";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FilterIcon,
  ScrollIcon,
  DownloadIcon,
  WifiIcon,
  WifiOffIcon,
  RefreshIcon,
} from "@/components/ui/icons";
import { LogLine } from "./LogLine";
import { LogSearchBar } from "./LogSearchBar";
import { LogFilterPanel } from "./LogFilterPanel";

interface ConnectionIndicatorProps {
  status: WebSocketStatus;
}

function ConnectionIndicator({ status }: ConnectionIndicatorProps) {
  const statusConfig: Record<WebSocketStatus, { icon: React.FC<{ className?: string }>; label: string; className: string }> = {
    connected: { icon: WifiIcon, label: "Live", className: "text-green-600" },
    connecting: { icon: RefreshIcon, label: "Connecting", className: "text-yellow-600 animate-spin" },
    reconnecting: { icon: RefreshIcon, label: "Reconnecting", className: "text-yellow-600 animate-spin" },
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

export function LogViewer({
  projectId,
  logs,
  isLoading,
  error,
  hasMore,
  filter: externalFilter,
  wsStatus,
  onFilterChange,
  onLoadMore,
  onDownload,
  className,
}: LogViewerProps) {
  const {
    autoScroll,
    toggleAutoScroll,
    showFilters,
    toggleFilters,
    searchInput,
    setSearchInput,
    handleSearch,
    clearSearch,
    toggleLevel,
    toggleSource,
    clearFilters,
    hasActiveFilters,
    filter,
    scrollRef,
    bottomRef,
    handleScroll,
  } = useLogViewer({
    initialFilter: externalFilter,
    onFilterChange,
  });

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs.length, autoScroll, bottomRef]);

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
              onClick={toggleFilters}
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
        <div className="mt-2">
          <LogSearchBar
            searchInput={searchInput}
            onSearchInputChange={setSearchInput}
            onSearch={handleSearch}
            onClear={clearSearch}
          />
        </div>

        {/* Filter panel */}
        {showFilters && (
          <LogFilterPanel
            filter={filter}
            hasActiveFilters={hasActiveFilters}
            onToggleLevel={toggleLevel}
            onToggleSource={toggleSource}
            onClearFilters={clearFilters}
          />
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
