"use client";

import { useState, useEffect, useCallback } from "react";
import { api, Task } from "@/services/api";
import { useWebSocket, WebSocketStatus } from "./use-websocket";

// Extended task type with additional UI fields
export interface TaskWithUI extends Task {
  currentAgent?: "implementation" | "test" | "review" | null;
  duration?: number; // Duration in seconds
  startedAt?: string;
  liveOutput?: string;
  isRunning?: boolean;
}

interface TaskUpdatePayload {
  taskId: string;
  task?: TaskWithUI;
  action: "created" | "updated" | "deleted" | "status_changed" | "output";
  output?: string;
}

interface UseTasksOptions {
  projectId?: string;
}

interface UseTasksReturn {
  tasks: TaskWithUI[];
  isLoading: boolean;
  error: string | null;
  wsStatus: WebSocketStatus;
  refetch: () => Promise<void>;
  startTask: (taskId: string) => Promise<void>;
  skipTask: (taskId: string) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
  reorderTasks: (taskIds: string[]) => Promise<void>;
  getTasksByStatus: (status: Task["status"]) => TaskWithUI[];
}

export function useTasks({ projectId }: UseTasksOptions = {}): UseTasksReturn {
  const [tasks, setTasks] = useState<TaskWithUI[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await api.tasks.list(projectId);
      // Transform to TaskWithUI
      const tasksWithUI: TaskWithUI[] = data.map((task) => ({
        ...task,
        currentAgent: task.status === "in_progress" ? "implementation" : null,
        isRunning: task.status === "in_progress",
      }));
      setTasks(tasksWithUI);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch tasks");
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Handle WebSocket messages for real-time updates
  const handleWebSocketMessage = useCallback(
    (message: { type: string; payload: TaskUpdatePayload }) => {
      if (message.type !== "task_update") return;

      const { action, taskId, task, output } = message.payload;

      setTasks((current) => {
        switch (action) {
          case "created":
            if (task) {
              return [...current, task];
            }
            return current;

          case "updated":
          case "status_changed":
            if (task) {
              return current.map((t) =>
                t.id === taskId
                  ? {
                      ...task,
                      currentAgent:
                        task.status === "in_progress"
                          ? task.currentAgent || "implementation"
                          : null,
                      isRunning: task.status === "in_progress",
                    }
                  : t
              );
            }
            return current;

          case "output":
            // Append live output to the running task
            return current.map((t) =>
              t.id === taskId
                ? { ...t, liveOutput: (t.liveOutput || "") + (output || "") }
                : t
            );

          case "deleted":
            return current.filter((t) => t.id !== taskId);

          default:
            return current;
        }
      });
    },
    []
  );

  const { status: wsStatus } = useWebSocket<TaskUpdatePayload>({
    endpoint: projectId ? `/ws/projects/${projectId}/tasks` : "/ws/tasks",
    onMessage: handleWebSocketMessage,
  });

  // Initial fetch
  useEffect(() => {
    void fetchTasks();
  }, [fetchTasks]);

  // Task actions
  const startTask = useCallback(
    async (taskId: string) => {
      try {
        // Mark task as running optimistically
        setTasks((current) =>
          current.map((t) =>
            t.id === taskId
              ? {
                  ...t,
                  status: "in_progress" as const,
                  isRunning: true,
                  currentAgent: "implementation",
                  startedAt: new Date().toISOString(),
                }
              : t
          )
        );

        // Trigger orchestration run
        if (projectId) {
          await api.orchestration.run(projectId);
        }
      } catch (err) {
        // Revert on error
        await fetchTasks();
        throw err;
      }
    },
    [projectId, fetchTasks]
  );

  const skipTask = useCallback(
    async (taskId: string) => {
      try {
        // Mark as skipped (completed with a skip flag conceptually)
        setTasks((current) =>
          current.map((t) =>
            t.id === taskId
              ? { ...t, status: "completed" as const, isRunning: false }
              : t
          )
        );
        await api.tasks.update(taskId, { status: "completed" });
      } catch (err) {
        await fetchTasks();
        throw err;
      }
    },
    [fetchTasks]
  );

  const deleteTask = useCallback(
    async (taskId: string) => {
      try {
        // Optimistically remove
        setTasks((current) => current.filter((t) => t.id !== taskId));
        await api.tasks.delete(taskId);
      } catch (err) {
        await fetchTasks();
        throw err;
      }
    },
    [fetchTasks]
  );

  const reorderTasks = useCallback(
    async (taskIds: string[]) => {
      try {
        // Reorder tasks locally based on the new order
        setTasks((current) => {
          const taskMap = new Map(current.map((t) => [t.id, t]));
          const reorderedPending: TaskWithUI[] = [];
          const others: TaskWithUI[] = [];

          // Separate pending tasks that are in the reorder list
          for (const id of taskIds) {
            const task = taskMap.get(id);
            if (task && task.status === "pending") {
              reorderedPending.push({
                ...task,
                priority: reorderedPending.length,
              });
            }
          }

          // Keep other tasks as is
          for (const task of current) {
            if (!taskIds.includes(task.id) || task.status !== "pending") {
              others.push(task);
            }
          }

          return [...reorderedPending, ...others];
        });

        // Persist the new order to backend
        // The backend should accept an array of task IDs to update priorities
        for (let i = 0; i < taskIds.length; i++) {
          const taskId = taskIds[i];
          if (taskId) {
            await api.tasks.update(taskId, { priority: i });
          }
        }
      } catch (err) {
        await fetchTasks();
        throw err;
      }
    },
    [fetchTasks]
  );

  const getTasksByStatus = useCallback(
    (status: Task["status"]) => {
      return tasks.filter((t) => t.status === status);
    },
    [tasks]
  );

  return {
    tasks,
    isLoading,
    error,
    wsStatus,
    refetch: fetchTasks,
    startTask,
    skipTask,
    deleteTask,
    reorderTasks,
    getTasksByStatus,
  };
}
