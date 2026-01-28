"use client";

import * as React from "react";
import { useState, useMemo } from "react";
import Link from "next/link";
import { ProjectWithStats } from "@/services/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ConnectionStatus } from "@/components/ui/connection-status";
import { WebSocketStatus } from "@/hooks/use-websocket";
import { ProjectCard } from "./project-card";

type ViewMode = "grid" | "list";
type StatusFilter = "all" | "active" | "idle" | "error";

interface ProjectListProps {
  projects: ProjectWithStats[];
  isLoading: boolean;
  error: string | null;
  wsStatus?: WebSocketStatus;
  onStartAutopilot?: (projectId: string) => void;
}

// Icons as inline SVGs to avoid external dependencies
function GridIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}

function ListIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function getStatusBadgeVariant(status: ProjectWithStats["status"]) {
  switch (status) {
    case "active":
      return "success";
    case "idle":
      return "secondary";
    case "error":
      return "error";
    default:
      return "secondary";
  }
}

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Never";

  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return "Just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;

  return date.toLocaleDateString();
}

function ProjectListSkeleton({ viewMode }: { viewMode: ViewMode }) {
  const skeletonCount = 6;

  if (viewMode === "grid") {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <Skeleton className="h-5 w-32" />
                  <Skeleton className="h-3 w-24 mt-2" />
                </div>
                <Skeleton className="h-5 w-14" />
              </div>
            </CardHeader>
            <CardContent className="pb-3">
              <div className="grid grid-cols-3 gap-2">
                {[1, 2, 3].map((j) => (
                  <Skeleton key={j} className="h-14" />
                ))}
              </div>
              <Skeleton className="h-3 w-full mt-4" />
            </CardContent>
            <div className="flex gap-2 px-6 pb-6">
              <Skeleton className="h-8 flex-1" />
              <Skeleton className="h-8 flex-1" />
            </div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: skeletonCount }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-4 border rounded-lg">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-16 ml-auto" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-24" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ searchQuery, statusFilter }: { searchQuery: string; statusFilter: StatusFilter }) {
  const hasFilters = searchQuery || statusFilter !== "all";

  return (
    <Card className="py-12">
      <CardContent className="flex flex-col items-center justify-center text-center">
        <div className="rounded-full bg-muted p-4 mb-4">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-muted-foreground"
          >
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        {hasFilters ? (
          <>
            <h3 className="text-lg font-semibold mb-1">No matching projects</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              No projects match your current search or filters. Try adjusting your criteria.
            </p>
          </>
        ) : (
          <>
            <h3 className="text-lg font-semibold mb-1">No projects yet</h3>
            <p className="text-sm text-muted-foreground max-w-sm mb-4">
              Get started by creating your first project or initializing an existing directory.
            </p>
            <Button asChild>
              <Link href="/projects/new">Create Project</Link>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ProjectListView({
  project,
  onStartAutopilot,
}: {
  project: ProjectWithStats;
  onStartAutopilot?: (projectId: string) => void;
}) {
  const totalTasks =
    project.taskCounts.pending +
    project.taskCounts.inProgress +
    project.taskCounts.completed +
    project.taskCounts.failed;

  return (
    <div className="flex items-center gap-4 p-4 border rounded-lg hover:bg-muted/50 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{project.name}</span>
          {project.currentBranch && (
            <span className="text-xs text-muted-foreground font-mono truncate">
              {project.currentBranch}
            </span>
          )}
        </div>
      </div>

      <Badge variant={getStatusBadgeVariant(project.status)} className="shrink-0">
        {project.status}
      </Badge>

      <div className="hidden sm:flex items-center gap-4 text-sm text-muted-foreground shrink-0">
        <span className="text-yellow-600 dark:text-yellow-400">
          {project.taskCounts.pending} pending
        </span>
        <span className="text-blue-600 dark:text-blue-400">
          {project.taskCounts.inProgress} in progress
        </span>
        <span className="text-green-600 dark:text-green-400">
          {project.taskCounts.completed}/{totalTasks}
        </span>
      </div>

      <span className="hidden md:block text-xs text-muted-foreground shrink-0">
        {formatRelativeTime(project.lastActivity ?? project.updatedAt)}
      </span>

      <div className="flex items-center gap-2 shrink-0">
        <Button asChild variant="outline" size="sm">
          <Link href={`/projects/${project.id}`}>Open</Link>
        </Button>
        <Button
          variant="default"
          size="sm"
          onClick={() => onStartAutopilot?.(project.id)}
          disabled={project.status === "active"}
        >
          {project.status === "active" ? "Running" : "Autopilot"}
        </Button>
      </div>
    </div>
  );
}

export function ProjectList({
  projects,
  isLoading,
  error,
  wsStatus,
  onStartAutopilot,
}: ProjectListProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  // Filter projects based on search and status
  const filteredProjects = useMemo(() => {
    return projects.filter((project) => {
      // Search filter
      const matchesSearch =
        searchQuery === "" ||
        project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        project.path.toLowerCase().includes(searchQuery.toLowerCase());

      // Status filter
      const matchesStatus =
        statusFilter === "all" || project.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [projects, searchQuery, statusFilter]);

  // Status counts for filter badges
  const statusCounts = useMemo(() => {
    return {
      all: projects.length,
      active: projects.filter((p) => p.status === "active").length,
      idle: projects.filter((p) => p.status === "idle").length,
      error: projects.filter((p) => p.status === "error").length,
    };
  }, [projects]);

  if (error) {
    return (
      <Card className="py-12">
        <CardContent className="flex flex-col items-center justify-center text-center">
          <div className="rounded-full bg-red-100 dark:bg-red-900/30 p-4 mb-4">
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-red-600 dark:text-red-400"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold mb-1">Failed to load projects</h3>
          <p className="text-sm text-muted-foreground max-w-sm">{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Connection status and Search, Filters, and View Toggle */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
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
          {(["all", "active", "idle", "error"] as const).map((status) => (
            <Button
              key={status}
              variant={statusFilter === status ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter(status)}
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
            onClick={() => setViewMode("grid")}
            aria-label="Grid view"
            className="rounded-r-none"
          >
            <GridIcon />
          </Button>
          <Button
            variant={viewMode === "list" ? "secondary" : "ghost"}
            size="icon-sm"
            onClick={() => setViewMode("list")}
            aria-label="List view"
            className="rounded-l-none"
          >
            <ListIcon />
          </Button>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && <ProjectListSkeleton viewMode={viewMode} />}

      {/* Empty State */}
      {!isLoading && filteredProjects.length === 0 && (
        <EmptyState searchQuery={searchQuery} statusFilter={statusFilter} />
      )}

      {/* Project Grid/List */}
      {!isLoading && filteredProjects.length > 0 && (
        <>
          {viewMode === "grid" ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onStartAutopilot={onStartAutopilot}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {filteredProjects.map((project) => (
                <ProjectListView
                  key={project.id}
                  project={project}
                  onStartAutopilot={onStartAutopilot}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Results count */}
      {!isLoading && projects.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Showing {filteredProjects.length} of {projects.length} project
          {projects.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
