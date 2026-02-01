"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { LogEntry, LogLevel, LogSource } from "@/services/api";
import { formatTimestamp } from "@/lib/format-time";
import { AnsiText } from "./AnsiText";

interface LogLineProps {
  log: LogEntry;
  searchTerm?: string;
}

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

export function LogLine({ log, searchTerm }: LogLineProps) {
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

export { getLevelBadgeVariant, getSourceColor };
