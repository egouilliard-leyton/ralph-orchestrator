"use client";

import { useState, useEffect, useCallback } from "react";
import {
  api,
  GitStatus,
  Branch,
  CreateBranchRequest,
  CreatePRRequest,
  PRResult,
} from "@/services/api";
import { useWebSocket, WebSocketStatus } from "./use-websocket";

interface GitUpdatePayload {
  action: "branch_changed" | "commit" | "push" | "pull" | "status_changed";
  branch?: string;
  status?: GitStatus;
}

interface UseGitOptions {
  projectId: string;
}

interface UseGitReturn {
  gitStatus: GitStatus | null;
  isLoading: boolean;
  error: string | null;
  wsStatus: WebSocketStatus;
  refetch: () => Promise<void>;
  createBranch: (name: string, baseBranch?: string) => Promise<void>;
  switchBranch: (branchName: string) => Promise<void>;
  deleteBranch: (branchName: string) => Promise<void>;
  createPR: (data: CreatePRRequest) => Promise<PRResult>;
}

export function useGit({ projectId }: UseGitOptions): UseGitReturn {
  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGitStatus = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const status = await api.git.getStatus(projectId);
      setGitStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch git status");
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Handle WebSocket messages for real-time updates
  const handleWebSocketMessage = useCallback(
    (message: { type: string; payload: GitUpdatePayload }) => {
      if (message.type !== "git_update") return;

      const { action, status } = message.payload;

      if (action === "status_changed" && status) {
        setGitStatus(status);
      } else {
        // For other actions, refetch the full status
        void fetchGitStatus();
      }
    },
    [fetchGitStatus]
  );

  const { status: wsStatus } = useWebSocket<GitUpdatePayload>({
    endpoint: `/ws/projects/${projectId}/git`,
    onMessage: handleWebSocketMessage,
  });

  // Initial fetch
  useEffect(() => {
    void fetchGitStatus();
  }, [fetchGitStatus]);

  // Git actions
  const createBranch = useCallback(
    async (name: string, baseBranch?: string) => {
      try {
        setError(null);
        const newBranch = await api.git.createBranch(projectId, {
          name,
          baseBranch,
        });

        // Optimistically update the git status
        setGitStatus((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            currentBranch: newBranch.name,
            branches: [...prev.branches, { ...newBranch, isCurrent: true }].map(
              (b) => ({
                ...b,
                isCurrent: b.name === newBranch.name,
              })
            ),
          };
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to create branch";
        setError(message);
        throw err;
      }
    },
    [projectId]
  );

  const switchBranch = useCallback(
    async (branchName: string) => {
      try {
        setError(null);
        const newStatus = await api.git.switchBranch(projectId, branchName);
        setGitStatus(newStatus);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to switch branch";
        setError(message);
        throw err;
      }
    },
    [projectId]
  );

  const deleteBranch = useCallback(
    async (branchName: string) => {
      try {
        setError(null);
        await api.git.deleteBranch(projectId, branchName);

        // Optimistically remove the branch from status
        setGitStatus((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            branches: prev.branches.filter((b) => b.name !== branchName),
          };
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to delete branch";
        setError(message);
        // Refetch to get accurate state
        await fetchGitStatus();
        throw err;
      }
    },
    [projectId, fetchGitStatus]
  );

  const createPR = useCallback(
    async (data: CreatePRRequest): Promise<PRResult> => {
      try {
        setError(null);
        const result = await api.git.createPR(projectId, data);
        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to create PR";
        setError(message);
        throw err;
      }
    },
    [projectId]
  );

  return {
    gitStatus,
    isLoading,
    error,
    wsStatus,
    refetch: fetchGitStatus,
    createBranch,
    switchBranch,
    deleteBranch,
    createPR,
  };
}
