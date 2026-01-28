"use client";

import { useState, useEffect, useCallback } from "react";
import { api, ProjectWithStats } from "@/services/api";
import { useWebSocket, WebSocketStatus } from "./use-websocket";

interface ProjectUpdatePayload {
  projectId: string;
  project?: ProjectWithStats;
  action: "created" | "updated" | "deleted" | "status_changed";
}

interface UseProjectsReturn {
  projects: ProjectWithStats[];
  isLoading: boolean;
  error: string | null;
  wsStatus: WebSocketStatus;
  refetch: () => Promise<void>;
}

export function useProjects(): UseProjectsReturn {
  const [projects, setProjects] = useState<ProjectWithStats[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await api.projects.listWithStats();
      setProjects(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch projects");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle WebSocket messages for real-time updates
  const handleWebSocketMessage = useCallback(
    (message: { type: string; payload: ProjectUpdatePayload }) => {
      if (message.type !== "project_update") return;

      const { action, projectId, project } = message.payload;

      setProjects((current) => {
        switch (action) {
          case "created":
            if (project) {
              return [...current, project];
            }
            return current;

          case "updated":
          case "status_changed":
            if (project) {
              return current.map((p) => (p.id === projectId ? project : p));
            }
            return current;

          case "deleted":
            return current.filter((p) => p.id !== projectId);

          default:
            return current;
        }
      });
    },
    []
  );

  const { status: wsStatus } = useWebSocket<ProjectUpdatePayload>({
    endpoint: "/ws/projects",
    onMessage: handleWebSocketMessage,
  });

  // Initial fetch
  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects]);

  return {
    projects,
    isLoading,
    error,
    wsStatus,
    refetch: fetchProjects,
  };
}
