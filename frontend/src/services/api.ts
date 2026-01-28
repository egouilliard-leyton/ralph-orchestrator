/**
 * REST API client for Ralph Orchestrator backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, ...fetchOptions } = options;

  let url = `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams(params);
    url += `?${searchParams.toString()}`;
  }

  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
  });

  if (!response.ok) {
    const errorMessage = await response.text().catch(() => response.statusText);
    throw new ApiError(response.status, response.statusText, errorMessage);
  }

  // Handle empty responses
  const text = await response.text();
  if (!text) {
    return {} as T;
  }

  return JSON.parse(text) as T;
}

// Project types
export interface Project {
  id: string;
  name: string;
  path: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
}

// Extended project type with dashboard-specific fields
export interface ProjectWithStats extends Project {
  currentBranch?: string;
  status: "active" | "idle" | "error";
  lastActivity?: string;
  taskCounts: {
    pending: number;
    inProgress: number;
    completed: number;
    failed: number;
  };
}

// Task types
export interface Task {
  id: string;
  projectId: string;
  title: string;
  description?: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  priority?: number;
  acceptanceCriteria?: string[];
  currentAgent?: "implementation" | "test" | "review" | null;
  startedAt?: string;
  duration?: number;
  createdAt: string;
  updatedAt: string;
}

// Session types
export interface Session {
  id: string;
  projectId: string;
  status: "active" | "paused" | "completed" | "failed";
  currentTaskId?: string;
  startedAt: string;
  endedAt?: string;
}

// Config types
export interface Gate {
  name: string;
  cmd: string;
  when?: string;
  timeout_seconds?: number;
  fatal?: boolean;
}

export interface ServiceConfig {
  start?: { dev?: string; prod?: string };
  serve?: { dev?: string; prod?: string };
  build?: string;
  port: number;
  health?: string[];
  timeout?: number;
}

export interface RalphConfig {
  version: string;
  task_source: {
    type: "prd_json" | "cr_markdown";
    path: string;
  };
  git: {
    base_branch: string;
    remote: string;
  };
  gates: {
    build: Gate[];
    full: Gate[];
  };
  test_paths?: string[];
  services?: {
    backend?: ServiceConfig;
    frontend?: ServiceConfig;
  };
  limits?: {
    claude_timeout?: number;
    max_iterations?: number;
    post_verify_iterations?: number;
    ui_fix_iterations?: number;
    robot_fix_iterations?: number;
  };
  autopilot?: {
    enabled?: boolean;
    reports_dir?: string;
    branch_prefix?: string;
    create_pr?: boolean;
  };
  agents?: {
    implementation?: { model?: string; timeout?: number; allowed_tools?: string[] };
    test_writing?: { model?: string; timeout?: number; allowed_tools?: string[] };
    review?: { model?: string; timeout?: number; allowed_tools?: string[] };
    fix?: { model?: string; timeout?: number; allowed_tools?: string[] };
    planning?: { model?: string; timeout?: number; allowed_tools?: string[] };
  };
}

export interface ConfigValidationResult {
  valid: boolean;
  errors: Array<{ path: string; message: string }>;
}

// Git types
export interface Branch {
  name: string;
  isCurrent: boolean;
  isRemote: boolean;
  lastCommit: {
    sha: string;
    message: string;
    author: string;
    timestamp: string;
  };
  ahead: number;
  behind: number;
}

export interface GitStatus {
  currentBranch: string;
  branches: Branch[];
  isDirty: boolean;
  untrackedFiles: number;
  modifiedFiles: number;
  stagedFiles: number;
}

export interface CreateBranchRequest {
  name: string;
  baseBranch?: string;
}

export interface CreatePRRequest {
  title: string;
  description: string;
  baseBranch?: string;
}

export interface PRResult {
  url: string;
  number: number;
  title: string;
}

// Log types
export type LogLevel = "debug" | "info" | "warn" | "error";
export type LogSource = "implementation" | "test" | "review" | "fix" | "gate" | "system";

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  source: LogSource;
  message: string;
  metadata?: Record<string, unknown>;
}

export interface LogFilter {
  levels?: LogLevel[];
  sources?: LogSource[];
  search?: string;
  startTime?: string;
  endTime?: string;
}

export interface LogsResponse {
  logs: LogEntry[];
  hasMore: boolean;
  nextCursor?: string;
}

// Timeline event types based on timeline.jsonl from Ralph Orchestrator
export type TimelineEventType =
  | "task_started"
  | "task_completed"
  | "task_failed"
  | "agent_transition"
  | "gate_started"
  | "gate_passed"
  | "gate_failed"
  | "signal_received"
  | "signal_sent"
  | "error"
  | "session_started"
  | "session_paused"
  | "session_resumed"
  | "session_completed";

export interface TimelineEvent {
  id: string;
  timestamp: string;
  type: TimelineEventType;
  title: string;
  description?: string;
  metadata?: {
    taskId?: string;
    taskTitle?: string;
    agent?: "implementation" | "test" | "review" | "fix" | "planning";
    previousAgent?: "implementation" | "test" | "review" | "fix" | "planning";
    gateName?: string;
    gateCmd?: string;
    gateOutput?: string;
    gateDuration?: number;
    signalType?: string;
    signalToken?: string;
    errorMessage?: string;
    errorStack?: string;
    sessionId?: string;
    duration?: number;
    [key: string]: unknown;
  };
}

export interface TimelineFilter {
  types?: TimelineEventType[];
  startTime?: string;
  endTime?: string;
  taskId?: string;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  hasMore: boolean;
  nextCursor?: string;
}

// API client
export const api = {
  // Health check
  health: () => request<{ status: string }>("/health"),

  // Projects
  projects: {
    list: async () => {
      const response = await request<{ projects: Project[]; total: number }>("/api/projects");
      return response.projects;
    },
    listWithStats: async () => {
      const response = await request<{ projects: ProjectWithStats[]; total: number }>("/api/projects?include_stats=true");
      // Map backend response to expected frontend format
      return response.projects.map(p => ({
        ...p,
        id: p.path, // Use path as ID
        currentBranch: (p as unknown as { git_branch?: string }).git_branch,
        taskCounts: {
          pending: (p as unknown as { tasks_pending?: number }).tasks_pending ?? 0,
          inProgress: 0,
          completed: (p as unknown as { tasks_completed?: number }).tasks_completed ?? 0,
          failed: 0,
        },
      }));
    },
    get: (id: string) => request<Project>(`/api/projects/${id}`),
    getWithStats: (id: string) => request<ProjectWithStats>(`/api/projects/${id}?include_stats=true`),
    create: (data: Omit<Project, "id" | "createdAt" | "updatedAt">) =>
      request<Project>("/api/projects", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, data: Partial<Project>) =>
      request<Project>(`/api/projects/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/api/projects/${id}`, {
        method: "DELETE",
      }),
  },

  // Tasks
  tasks: {
    list: async (projectId?: string) => {
      if (!projectId) {
        throw new Error("projectId is required to fetch tasks");
      }
      // Use the project-specific tasks endpoint
      const response = await request<{
        project: string;
        description: string;
        tasks: Array<{
          id: string;
          title: string;
          description: string;
          acceptance_criteria: string[];
          priority: number;
          passes: boolean;
          notes: string;
          requires_tests: boolean;
        }>;
        total: number;
        completed: number;
        pending: number;
      }>(`/api/projects/${encodeURIComponent(projectId)}/tasks`);
      
      // Map backend task format to frontend Task format
      return response.tasks.map((t): Task => ({
        id: t.id,
        projectId: projectId,
        title: t.title,
        description: t.description,
        status: t.passes ? "completed" : "pending",
        priority: t.priority,
        acceptanceCriteria: t.acceptance_criteria,
        currentAgent: null,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }));
    },
    listByProject: (projectId: string) =>
      request<Task[]>(`/api/projects/${encodeURIComponent(projectId)}/tasks`),
    get: (id: string) => request<Task>(`/api/tasks/${id}`),
    create: (data: Omit<Task, "id" | "createdAt" | "updatedAt">) =>
      request<Task>("/api/tasks", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, data: Partial<Task>) =>
      request<Task>(`/api/tasks/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/api/tasks/${id}`, {
        method: "DELETE",
      }),
    reorder: (projectId: string, taskIds: string[]) =>
      request<void>(`/api/projects/${projectId}/tasks/reorder`, {
        method: "POST",
        body: JSON.stringify({ taskIds }),
      }),
    skip: (id: string) =>
      request<Task>(`/api/tasks/${id}/skip`, {
        method: "POST",
      }),
  },

  // Sessions
  sessions: {
    list: (projectId?: string) =>
      request<Session[]>("/api/sessions", {
        params: projectId ? { projectId } : undefined,
      }),
    get: (id: string) => request<Session>(`/api/sessions/${id}`),
    start: (projectId: string) =>
      request<Session>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({ projectId }),
      }),
    pause: (id: string) =>
      request<Session>(`/api/sessions/${id}/pause`, {
        method: "POST",
      }),
    resume: (id: string) =>
      request<Session>(`/api/sessions/${id}/resume`, {
        method: "POST",
      }),
    stop: (id: string) =>
      request<Session>(`/api/sessions/${id}/stop`, {
        method: "POST",
      }),
  },

  // Orchestration
  orchestration: {
    run: (projectId: string, options?: { dryRun?: boolean }) =>
      request<{ sessionId: string }>("/api/orchestration/run", {
        method: "POST",
        body: JSON.stringify({ projectId, ...options }),
      }),
    status: (sessionId: string) =>
      request<{ status: string; progress: number }>(`/api/orchestration/status/${sessionId}`),
  },

  // Config
  config: {
    get: (projectId: string) =>
      request<RalphConfig>(`/api/projects/${projectId}/config`),
    update: (projectId: string, config: RalphConfig) =>
      request<RalphConfig>(`/api/projects/${projectId}/config`, {
        method: "PUT",
        body: JSON.stringify(config),
      }),
    validate: (projectId: string, config: RalphConfig) =>
      request<ConfigValidationResult>(`/api/projects/${projectId}/config/validate`, {
        method: "POST",
        body: JSON.stringify(config),
      }),
  },

  // Git operations
  git: {
    getStatus: (projectId: string) =>
      request<GitStatus>(`/api/projects/${projectId}/git/status`),
    getBranches: (projectId: string) =>
      request<Branch[]>(`/api/projects/${projectId}/git/branches`),
    createBranch: (projectId: string, data: CreateBranchRequest) =>
      request<Branch>(`/api/projects/${projectId}/git/branches`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    switchBranch: (projectId: string, branchName: string) =>
      request<GitStatus>(`/api/projects/${projectId}/git/checkout`, {
        method: "POST",
        body: JSON.stringify({ branch: branchName }),
      }),
    deleteBranch: (projectId: string, branchName: string) =>
      request<void>(`/api/projects/${projectId}/git/branches/${encodeURIComponent(branchName)}`, {
        method: "DELETE",
      }),
    createPR: (projectId: string, data: CreatePRRequest) =>
      request<PRResult>(`/api/projects/${projectId}/pr`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  // Logs
  logs: {
    list: (projectId: string, filter?: LogFilter, cursor?: string) =>
      request<LogsResponse>(`/api/projects/${projectId}/logs`, {
        params: {
          ...(filter?.levels ? { levels: filter.levels.join(",") } : {}),
          ...(filter?.sources ? { sources: filter.sources.join(",") } : {}),
          ...(filter?.search ? { search: filter.search } : {}),
          ...(filter?.startTime ? { startTime: filter.startTime } : {}),
          ...(filter?.endTime ? { endTime: filter.endTime } : {}),
          ...(cursor ? { cursor } : {}),
        },
      }),
    download: (projectId: string, filter?: LogFilter) =>
      `${API_BASE_URL}/api/projects/${projectId}/logs/download?${new URLSearchParams({
        ...(filter?.levels ? { levels: filter.levels.join(",") } : {}),
        ...(filter?.sources ? { sources: filter.sources.join(",") } : {}),
        ...(filter?.search ? { search: filter.search } : {}),
        ...(filter?.startTime ? { startTime: filter.startTime } : {}),
        ...(filter?.endTime ? { endTime: filter.endTime } : {}),
      }).toString()}`,
  },

  // Timeline
  timeline: {
    list: (projectId: string, filter?: TimelineFilter, cursor?: string) =>
      request<TimelineResponse>(`/api/projects/${projectId}/timeline`, {
        params: {
          ...(filter?.types ? { types: filter.types.join(",") } : {}),
          ...(filter?.startTime ? { startTime: filter.startTime } : {}),
          ...(filter?.endTime ? { endTime: filter.endTime } : {}),
          ...(filter?.taskId ? { taskId: filter.taskId } : {}),
          ...(cursor ? { cursor } : {}),
        },
      }),
    downloadJson: (projectId: string, filter?: TimelineFilter) =>
      `${API_BASE_URL}/api/projects/${projectId}/timeline/download?format=json&${new URLSearchParams({
        ...(filter?.types ? { types: filter.types.join(",") } : {}),
        ...(filter?.startTime ? { startTime: filter.startTime } : {}),
        ...(filter?.endTime ? { endTime: filter.endTime } : {}),
        ...(filter?.taskId ? { taskId: filter.taskId } : {}),
      }).toString()}`,
    downloadCsv: (projectId: string, filter?: TimelineFilter) =>
      `${API_BASE_URL}/api/projects/${projectId}/timeline/download?format=csv&${new URLSearchParams({
        ...(filter?.types ? { types: filter.types.join(",") } : {}),
        ...(filter?.startTime ? { startTime: filter.startTime } : {}),
        ...(filter?.endTime ? { endTime: filter.endTime } : {}),
        ...(filter?.taskId ? { taskId: filter.taskId } : {}),
      }).toString()}`,
  },
};

export { ApiError };
