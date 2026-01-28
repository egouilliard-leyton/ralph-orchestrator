"use client";

import { useCallback, useMemo, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { TaskCard } from "./task-card";
import { useTasks, TaskWithUI } from "@/hooks/use-tasks";
import { cn } from "@/lib/utils";
import { WebSocketStatus } from "@/hooks/use-websocket";

// Connection status indicator icons
const WifiIcon = () => (
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
    <path d="M5 13a10 10 0 0 1 14 0" />
    <path d="M8.5 16.5a5 5 0 0 1 7 0" />
    <path d="M2 8.82a15 15 0 0 1 20 0" />
    <line x1="12" x2="12.01" y1="20" y2="20" />
  </svg>
);

const WifiOffIcon = () => (
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
    <line x1="2" x2="22" y1="2" y2="22" />
    <path d="M8.5 16.5a5 5 0 0 1 7 0" />
    <path d="M2 8.82a15 15 0 0 1 4.17-2.65" />
    <path d="M10.66 5c4.01-.36 8.14.9 11.34 3.76" />
    <path d="M16.85 11.25a10 10 0 0 1 2.22 1.68" />
    <path d="M5 13a10 10 0 0 1 5.24-2.76" />
    <line x1="12" x2="12.01" y1="20" y2="20" />
  </svg>
);

const RefreshIcon = () => (
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
    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
    <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
    <path d="M16 16h5v5" />
  </svg>
);

const AlertIcon = () => (
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
    <circle cx="12" cy="12" r="10" />
    <line x1="12" x2="12" y1="8" y2="12" />
    <line x1="12" x2="12.01" y1="16" y2="16" />
  </svg>
);

interface TaskBoardProps {
  projectId?: string;
}

interface ColumnConfig {
  id: string;
  title: string;
  description: string;
  status: TaskWithUI["status"];
  emptyMessage: string;
  color: string;
}

const columns: ColumnConfig[] = [
  {
    id: "todo",
    title: "To Do",
    description: "Tasks waiting to be started",
    status: "pending",
    emptyMessage: "No pending tasks",
    color: "border-t-gray-400",
  },
  {
    id: "in-progress",
    title: "In Progress",
    description: "Tasks currently being worked on",
    status: "in_progress",
    emptyMessage: "No tasks in progress",
    color: "border-t-yellow-500",
  },
  {
    id: "done",
    title: "Done",
    description: "Tasks that have been completed",
    status: "completed",
    emptyMessage: "No completed tasks",
    color: "border-t-green-500",
  },
];

function ConnectionIndicator({ status }: { status: WebSocketStatus }) {
  const statusConfig: Record<WebSocketStatus, { icon: React.FC; label: string; className: string }> = {
    connected: { icon: WifiIcon, label: "Connected", className: "text-green-600" },
    connecting: { icon: RefreshIcon, label: "Connecting...", className: "text-yellow-600 animate-spin" },
    reconnecting: { icon: RefreshIcon, label: "Reconnecting...", className: "text-yellow-600 animate-spin" },
    disconnected: { icon: WifiOffIcon, label: "Disconnected", className: "text-muted-foreground" },
    error: { icon: WifiOffIcon, label: "Connection error", className: "text-red-600" },
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

function TaskColumn({
  column,
  tasks,
  onStart,
  onSkip,
  onDelete,
}: {
  column: ColumnConfig;
  tasks: TaskWithUI[];
  onStart?: (taskId: string) => void;
  onSkip?: (taskId: string) => void;
  onDelete?: (taskId: string) => void;
}) {
  const isDraggable = column.status === "pending";
  const taskIds = useMemo(() => tasks.map((t) => t.id), [tasks]);

  return (
    <Card className={cn("flex flex-col h-full border-t-4", column.color)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{column.title}</CardTitle>
          <Badge variant="secondary" className="text-xs">
            {tasks.length}
          </Badge>
        </div>
        <CardDescription>{column.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto pb-4">
        {tasks.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            {column.emptyMessage}
          </p>
        ) : isDraggable ? (
          <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
            <div className="space-y-3">
              {tasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  isDraggable
                  onStart={onStart}
                  onSkip={onSkip}
                  onDelete={onDelete}
                />
              ))}
            </div>
          </SortableContext>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TaskBoardSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-3 h-[calc(100vh-200px)]">
      {[1, 2, 3].map((i) => (
        <Card key={i} className="flex flex-col h-full">
          <CardHeader className="pb-2">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-4 w-40 mt-1" />
          </CardHeader>
          <CardContent className="flex-1">
            <div className="space-y-3">
              {[1, 2, 3].map((j) => (
                <Skeleton key={j} className="h-24 w-full rounded-xl" />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TaskBoardError({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-[calc(100vh-200px)] text-center">
      <div className="text-red-500 mb-4">
        <AlertIcon />
      </div>
      <h3 className="text-lg font-semibold mb-2">Failed to load tasks</h3>
      <p className="text-sm text-muted-foreground mb-4 max-w-md">{error}</p>
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90"
      >
        <RefreshIcon />
        Try Again
      </button>
    </div>
  );
}

export function TaskBoard({ projectId }: TaskBoardProps) {
  const {
    tasks,
    isLoading,
    error,
    wsStatus,
    refetch,
    startTask,
    skipTask,
    deleteTask,
    reorderTasks,
  } = useTasks({ projectId });

  const [activeId, setActiveId] = useState<string | null>(null);

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Get tasks for each column
  const pendingTasks = useMemo(
    () =>
      tasks
        .filter((t) => t.status === "pending")
        .sort((a, b) => (a.priority ?? 0) - (b.priority ?? 0)),
    [tasks]
  );

  const inProgressTasks = useMemo(
    () => tasks.filter((t) => t.status === "in_progress"),
    [tasks]
  );

  const completedTasks = useMemo(
    () =>
      tasks
        .filter((t) => t.status === "completed")
        .sort(
          (a, b) =>
            new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        ),
    [tasks]
  );

  // Failed tasks go into a special section or can be shown in todo
  const failedTasks = useMemo(
    () => tasks.filter((t) => t.status === "failed"),
    [tasks]
  );

  // Find active task for drag overlay
  const activeTask = useMemo(
    () => tasks.find((t) => t.id === activeId),
    [tasks, activeId]
  );

  // Drag handlers
  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveId(null);

      const { active, over } = event;
      if (!over || active.id === over.id) return;

      // Only allow reordering within pending tasks
      const activeTask = pendingTasks.find((t) => t.id === active.id);
      const overTask = pendingTasks.find((t) => t.id === over.id);

      if (!activeTask || !overTask) return;

      const oldIndex = pendingTasks.findIndex((t) => t.id === active.id);
      const newIndex = pendingTasks.findIndex((t) => t.id === over.id);

      if (oldIndex === newIndex) return;

      // Create new order
      const newOrder = [...pendingTasks];
      const [removed] = newOrder.splice(oldIndex, 1);
      if (removed) {
        newOrder.splice(newIndex, 0, removed);
      }

      // Persist the new order
      void reorderTasks(newOrder.map((t) => t.id));
    },
    [pendingTasks, reorderTasks]
  );

  const handleDragCancel = useCallback(() => {
    setActiveId(null);
  }, []);

  // Action handlers
  const handleStart = useCallback(
    async (taskId: string) => {
      try {
        await startTask(taskId);
      } catch (err) {
        console.error("Failed to start task:", err);
      }
    },
    [startTask]
  );

  const handleSkip = useCallback(
    async (taskId: string) => {
      try {
        await skipTask(taskId);
      } catch (err) {
        console.error("Failed to skip task:", err);
      }
    },
    [skipTask]
  );

  const handleDelete = useCallback(
    async (taskId: string) => {
      try {
        await deleteTask(taskId);
      } catch (err) {
        console.error("Failed to delete task:", err);
      }
    },
    [deleteTask]
  );

  if (isLoading) {
    return <TaskBoardSkeleton />;
  }

  if (error) {
    return <TaskBoardError error={error} onRetry={refetch} />;
  }

  // Map column status to tasks
  const getTasksForColumn = (column: ColumnConfig): TaskWithUI[] => {
    switch (column.status) {
      case "pending":
        // Include failed tasks in todo column for retry
        return [...pendingTasks, ...failedTasks];
      case "in_progress":
        return inProgressTasks;
      case "completed":
        return completedTasks;
      default:
        return [];
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Connection status */}
      <div className="flex items-center justify-end mb-4">
        <ConnectionIndicator status={wsStatus} />
      </div>

      {/* Board */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <div className="grid gap-4 md:grid-cols-3 h-[calc(100vh-240px)]">
          {columns.map((column) => (
            <TaskColumn
              key={column.id}
              column={column}
              tasks={getTasksForColumn(column)}
              onStart={column.status === "pending" ? handleStart : undefined}
              onSkip={column.status === "pending" ? handleSkip : undefined}
              onDelete={column.status === "pending" ? handleDelete : undefined}
            />
          ))}
        </div>

        {/* Drag overlay */}
        <DragOverlay>
          {activeTask ? (
            <div className="opacity-80">
              <TaskCard task={activeTask} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
