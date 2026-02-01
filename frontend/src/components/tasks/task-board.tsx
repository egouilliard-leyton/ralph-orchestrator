"use client";

import { useCallback, useMemo } from "react";
import { DndContext, DragOverlay } from "@dnd-kit/core";
import { useTasks, TaskWithUI } from "@/hooks/use-tasks";
import { useTaskDnd } from "@/hooks/use-task-dnd";
import { TaskCard } from "./task-card";
import { TaskColumn, TASK_COLUMNS, ColumnConfig } from "./TaskColumn";
import { TaskBoardSkeleton } from "./TaskBoardSkeleton";
import { TaskBoardError } from "./TaskBoardError";
import { ConnectionIndicator } from "./ConnectionIndicator";

interface TaskBoardProps {
  projectId?: string;
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

  // DnD functionality
  const {
    sensors,
    collisionDetection,
    activeId,
    activeTask,
    handleDragStart,
    handleDragEnd,
    handleDragCancel,
  } = useTaskDnd({
    tasks,
    onReorder: reorderTasks,
  });

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

  const failedTasks = useMemo(
    () => tasks.filter((t) => t.status === "failed"),
    [tasks]
  );

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

  if (isLoading) {
    return <TaskBoardSkeleton />;
  }

  if (error) {
    return <TaskBoardError error={error} onRetry={refetch} />;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Connection status */}
      <div className="flex items-center justify-end mb-4">
        <ConnectionIndicator status={wsStatus} />
      </div>

      {/* Board */}
      <DndContext
        sensors={sensors}
        collisionDetection={collisionDetection}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <div className="grid gap-4 md:grid-cols-3 h-[calc(100vh-240px)]">
          {TASK_COLUMNS.map((column) => (
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
