"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConnectionStatus } from "@/components/ui/connection-status";
import { SearchIcon, GridIcon, ListIcon } from "@/components/ui/icons";
import { WebSocketStatus } from "@/hooks/use-websocket";
import { ViewMode, StatusFilter } from "@/hooks/use-project-filters";

interface ProjectFiltersProps {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  statusFilter: StatusFilter;
  onStatusFilterChange: (filter: StatusFilter) => void;
  statusCounts: Record<StatusFilter, number>;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  wsStatus?: WebSocketStatus;
}

const STATUS_OPTIONS: StatusFilter[] = ["all", "active", "idle", "error"];

export function ProjectFilters({
  searchQuery,
  onSearchQueryChange,
  statusFilter,
  onStatusFilterChange,
  statusCounts,
  viewMode,
  onViewModeChange,
  wsStatus,
}: ProjectFiltersProps) {
  return (
    <div className="flex flex-col sm:flex-row gap-4">
      {/* Search */}
      <div className="relative flex-1">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          placeholder="Search projects..."
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Connection Status */}
      {wsStatus && (
        <div className="flex items-center">
          <ConnectionStatus status={wsStatus} showLabel shortLabel />
        </div>
      )}

      {/* Status Filter */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
        {STATUS_OPTIONS.map((status) => (
          <Button
            key={status}
            variant={statusFilter === status ? "default" : "outline"}
            size="sm"
            onClick={() => onStatusFilterChange(status)}
            className="shrink-0"
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
            <span className="ml-1 text-xs opacity-70">
              ({statusCounts[status]})
            </span>
          </Button>
        ))}
      </div>

      {/* View Toggle */}
      <div className="flex items-center border rounded-md">
        <Button
          variant={viewMode === "grid" ? "secondary" : "ghost"}
          size="icon-sm"
          onClick={() => onViewModeChange("grid")}
          aria-label="Grid view"
          className="rounded-r-none"
        >
          <GridIcon />
        </Button>
        <Button
          variant={viewMode === "list" ? "secondary" : "ghost"}
          size="icon-sm"
          onClick={() => onViewModeChange("list")}
          aria-label="List view"
          className="rounded-l-none"
        >
          <ListIcon />
        </Button>
      </div>
    </div>
  );
}
