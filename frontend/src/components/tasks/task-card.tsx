"use client";

import { useState, useMemo, useEffect } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import type { TaskWithUI } from "@/hooks/use-tasks";

// SVG Icons
const GripIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="9" cy="5" r="1" />
    <circle cx="9" cy="12" r="1" />
    <circle cx="9" cy="19" r="1" />
    <circle cx="15" cy="5" r="1" />
    <circle cx="15" cy="12" r="1" />
    <circle cx="15" cy="19" r="1" />
  </svg>
);

const PlayIcon = () => (
  <svg
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
    <polygon points="6 3 20 12 6 21 6 3" />
  </svg>
);

const SkipIcon = () => (
  <svg
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
    <polygon points="5 4 15 12 5 20 5 4" />
    <line x1="19" y1="5" x2="19" y2="19" />
  </svg>
);

const TrashIcon = () => (
  <svg
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
    <path d="M3 6h18" />
    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
  </svg>
);

const CheckIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const CircleIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
  </svg>
);

const ClockIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

interface TaskCardProps {
  task: TaskWithUI;
  isDraggable?: boolean;
  onStart?: (taskId: string) => void;
  onSkip?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
}

const agentLabels: Record<string, string> = {
  implementation: "Implementing",
  test: "Writing Tests",
  review: "Reviewing",
};

export function TaskCard({
  task,
  isDraggable = false,
  onStart,
  onSkip,
  onDelete,
}: TaskCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: task.id,
    disabled: !isDraggable,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  // Calculate duration display - uses interval to update live
  const [durationDisplay, setDurationDisplay] = useState<string | null>(() => {
    // Initial calculation in state initializer (pure)
    if (!task.startedAt || !task.isRunning) return null;
    const start = new Date(task.startedAt).getTime();
    const now = Date.now();
    const seconds = Math.floor((now - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  });

  useEffect(() => {
    if (!task.startedAt || !task.isRunning) {
      return;
    }

    const calculateDuration = () => {
      const start = new Date(task.startedAt!).getTime();
      const now = Date.now();
      const seconds = Math.floor((now - start) / 1000);
      if (seconds < 60) return `${seconds}s`;
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
      const hours = Math.floor(minutes / 60);
      return `${hours}h ${minutes % 60}m`;
    };

    // Update every second for running tasks
    const interval = setInterval(() => {
      setDurationDisplay(calculateDuration());
    }, 1000);

    return () => clearInterval(interval);
  }, [task.startedAt, task.isRunning]);

  // Truncate description
  const truncatedDescription = useMemo(() => {
    if (!task.description) return null;
    if (task.description.length <= 100) return task.description;
    return task.description.slice(0, 100) + "...";
  }, [task.description]);

  // Status badge variant
  const statusVariant = useMemo(() => {
    switch (task.status) {
      case "completed":
        return "success";
      case "in_progress":
        return "warning";
      case "failed":
        return "error";
      default:
        return "secondary";
    }
  }, [task.status]);

  const statusLabel = useMemo(() => {
    switch (task.status) {
      case "completed":
        return "Done";
      case "in_progress":
        return task.currentAgent
          ? agentLabels[task.currentAgent]
          : "In Progress";
      case "failed":
        return "Failed";
      default:
        return "To Do";
    }
  }, [task.status, task.currentAgent]);

  return (
    <>
      <Card
        ref={setNodeRef}
        style={style}
        className={cn(
          "cursor-pointer transition-all hover:shadow-md",
          isDragging && "opacity-50 shadow-lg",
          task.isRunning && "border-yellow-500/50"
        )}
        onClick={() => setIsExpanded(true)}
      >
        <CardHeader className="pb-2 pt-4 px-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2 flex-1 min-w-0">
              {isDraggable && (
                <button
                  className="mt-0.5 cursor-grab touch-none text-muted-foreground hover:text-foreground"
                  {...attributes}
                  {...listeners}
                  onClick={(e) => e.stopPropagation()}
                >
                  <GripIcon />
                </button>
              )}
              <CardTitle className="text-sm font-medium leading-tight line-clamp-2">
                {task.title}
              </CardTitle>
            </div>
            <Badge variant={statusVariant} className="shrink-0">
              {task.isRunning && (
                <span className="mr-1 inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
              )}
              {statusLabel}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="pb-4 px-4 pt-0">
          {truncatedDescription && (
            <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
              {truncatedDescription}
            </p>
          )}

          {/* Acceptance criteria preview */}
          {task.acceptanceCriteria && task.acceptanceCriteria.length > 0 && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground mb-2">
              <span className="flex items-center gap-0.5">
                {task.status === "completed" ? (
                  <CheckIcon />
                ) : (
                  <CircleIcon />
                )}
              </span>
              <span>
                {task.acceptanceCriteria.length} acceptance criteria
              </span>
            </div>
          )}

          {/* Duration/timestamp for running tasks */}
          {task.isRunning && durationDisplay && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <ClockIcon />
              <span>{durationDisplay}</span>
            </div>
          )}

          {/* Quick actions for pending tasks */}
          {task.status === "pending" && (
            <div className="flex items-center gap-1 mt-2">
              {onStart && (
                <Button
                  size="xs"
                  variant="default"
                  onClick={(e) => {
                    e.stopPropagation();
                    onStart(task.id);
                  }}
                >
                  <PlayIcon />
                  <span>Start</span>
                </Button>
              )}
              {onSkip && (
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSkip(task.id);
                  }}
                >
                  <SkipIcon />
                </Button>
              )}
              {onDelete && (
                <Button
                  size="xs"
                  variant="ghost"
                  className="text-destructive hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(task.id);
                  }}
                >
                  <TrashIcon />
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Expanded task detail sheet */}
      <Sheet open={isExpanded} onOpenChange={setIsExpanded}>
        <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <div className="flex items-start justify-between gap-2 pr-8">
              <SheetTitle className="text-left">{task.title}</SheetTitle>
              <Badge variant={statusVariant}>
                {task.isRunning && (
                  <span className="mr-1 inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
                )}
                {statusLabel}
              </Badge>
            </div>
            {task.description && (
              <SheetDescription className="text-left">
                {task.description}
              </SheetDescription>
            )}
          </SheetHeader>

          <div className="mt-6 space-y-6 px-4">
            {/* Acceptance Criteria */}
            {task.acceptanceCriteria && task.acceptanceCriteria.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">
                  Acceptance Criteria
                </h4>
                <ul className="space-y-2">
                  {task.acceptanceCriteria.map((criterion, index) => (
                    <li
                      key={index}
                      className="flex items-start gap-2 text-sm text-muted-foreground"
                    >
                      <span className="mt-0.5 shrink-0">
                        {task.status === "completed" ? (
                          <span className="text-green-600">
                            <CheckIcon />
                          </span>
                        ) : (
                          <CircleIcon />
                        )}
                      </span>
                      <span>{criterion}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Current Agent Indicator */}
            {task.isRunning && task.currentAgent && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Current Agent</h4>
                <div className="flex items-center gap-2">
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-yellow-500" />
                  <span className="text-sm">{agentLabels[task.currentAgent]}</span>
                  {durationDisplay && (
                    <span className="text-xs text-muted-foreground">
                      ({durationDisplay})
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Live Agent Output */}
            {task.liveOutput && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Live Output</h4>
                <div className="bg-muted rounded-md p-3 max-h-64 overflow-y-auto">
                  <pre className="text-xs whitespace-pre-wrap font-mono">
                    {task.liveOutput}
                  </pre>
                </div>
              </div>
            )}

            {/* Task metadata */}
            <div className="text-xs text-muted-foreground space-y-1">
              <p>ID: {task.id}</p>
              {task.priority !== undefined && (
                <p>Priority: {task.priority}</p>
              )}
              <p>Created: {new Date(task.createdAt).toLocaleString()}</p>
              <p>Updated: {new Date(task.updatedAt).toLocaleString()}</p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 pt-4 border-t">
              {task.status === "pending" && onStart && (
                <Button
                  onClick={() => {
                    onStart(task.id);
                    setIsExpanded(false);
                  }}
                >
                  <PlayIcon />
                  <span>Start Task</span>
                </Button>
              )}
              {task.status === "pending" && onSkip && (
                <Button
                  variant="outline"
                  onClick={() => {
                    onSkip(task.id);
                    setIsExpanded(false);
                  }}
                >
                  <SkipIcon />
                  <span>Skip</span>
                </Button>
              )}
              {task.status === "pending" && onDelete && (
                <Button
                  variant="destructive"
                  onClick={() => {
                    onDelete(task.id);
                    setIsExpanded(false);
                  }}
                >
                  <TrashIcon />
                  <span>Delete</span>
                </Button>
              )}
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
