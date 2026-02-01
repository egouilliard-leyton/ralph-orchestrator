"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LogLevel, LogSource, LogFilter } from "@/services/api";
import { getLevelBadgeVariant } from "./LogLine";

interface LogFilterPanelProps {
  filter: LogFilter;
  hasActiveFilters: boolean;
  onToggleLevel: (level: LogLevel) => void;
  onToggleSource: (source: LogSource) => void;
  onClearFilters: () => void;
}

const LOG_LEVELS: LogLevel[] = ["debug", "info", "warn", "error"];
const LOG_SOURCES: LogSource[] = ["implementation", "test", "review", "fix", "gate", "system"];

export function LogFilterPanel({
  filter,
  hasActiveFilters,
  onToggleLevel,
  onToggleSource,
  onClearFilters,
}: LogFilterPanelProps) {
  return (
    <div className="mt-3 space-y-3 rounded-md bg-muted/50 p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Filters</span>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="xs"
            onClick={onClearFilters}
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
              onClick={() => onToggleLevel(level)}
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
              onClick={() => onToggleSource(source)}
            >
              {source}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}
